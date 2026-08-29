"""Guarded production HTTP adapter for v0.32 evidence-only admission."""

from __future__ import annotations

import hmac
import os
import re
import stat
from collections.abc import Callable
from typing import Literal, Protocol

from fastapi import APIRouter, Request, Response
from pydantic import TypeAdapter

from .contract import (
    AUTHENTICATED_CORE_PERMISSION,
    AUTHENTICATED_CORE_PRINCIPAL,
    INTAKE_PATH,
    MAX_ENVELOPE_BYTES,
    AgentLiveIntakeAuthenticationContextV1,
    AgentLiveIntakeAuthenticationReferenceV1,
    AgentLiveIntakeEnvelopeV1,
    AgentLiveIntakeResultV1,
    AgentLiveIntakeSourceV1,
    CorrelationId,
    IdempotencyKey,
    parse_envelope_json,
)
from .service import AgentLiveIntakeAdmissionService

MAX_JSON_NESTING = 32
_BEARER = re.compile(r"Bearer ([\x21-\x7e]{1,4096})")


class LiveIntakeAuthenticationError(ValueError):
    """Closed authentication failure safe for route translation."""

    def __init__(self, code: Literal["unauthenticated", "unauthorized"]) -> None:
        self.code = code
        super().__init__(code)


class LiveIntakeAuthenticator(Protocol):
    def authenticate(
        self, bearer_credential: str
    ) -> AgentLiveIntakeAuthenticationContextV1: ...


class Mode0400FileLiveIntakeAuthenticator:
    """Resolve one dedicated credential without persisting or disclosing it."""

    def __init__(
        self,
        *,
        reference: AgentLiveIntakeAuthenticationReferenceV1,
        source: AgentLiveIntakeSourceV1,
    ) -> None:
        self._reference = reference
        self._source = source

    def authenticate(
        self, bearer_credential: str
    ) -> AgentLiveIntakeAuthenticationContextV1:
        descriptor = -1
        material = b""
        try:
            descriptor = os.open(
                self._reference.credential_file,
                os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0),
            )
            before = os.fstat(descriptor)
            if (
                not stat.S_ISREG(before.st_mode)
                or before.st_uid != os.geteuid()
                or stat.S_IMODE(before.st_mode) != 0o400
                or not 0 < before.st_size <= self._reference.maximum_credential_bytes
            ):
                raise LiveIntakeAuthenticationError("unauthenticated")
            material = os.read(descriptor, self._reference.maximum_credential_bytes + 1)
            after = os.fstat(descriptor)
            if (
                len(material) != before.st_size
                or len(material) > self._reference.maximum_credential_bytes
                or (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns)
                != (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns)
                or b"\x00" in material
                or b"\n" in material
                or b"\r" in material
            ):
                raise LiveIntakeAuthenticationError("unauthenticated")
            try:
                expected = material.decode("ascii")
            except UnicodeDecodeError as error:
                raise LiveIntakeAuthenticationError("unauthenticated") from error
            if not hmac.compare_digest(expected, bearer_credential):
                raise LiveIntakeAuthenticationError("unauthenticated")
            return AgentLiveIntakeAuthenticationContextV1(
                source=self._source,
                credential_reference=self._reference,
            )
        except LiveIntakeAuthenticationError:
            raise
        except Exception as error:
            raise LiveIntakeAuthenticationError("unauthenticated") from error
        finally:
            material = b""
            if descriptor >= 0:
                os.close(descriptor)


def _rejected(
    code: Literal["unauthenticated", "unauthorized", "malformed", "unavailable"],
) -> AgentLiveIntakeResultV1:
    return AgentLiveIntakeResultV1(
        send_attempt_id=None,
        intake_request_id=None,
        outcome="rejected",
        admission=None,
        acknowledgement=None,
        reason_code=code,
    )


def _response(result: AgentLiveIntakeResultV1) -> Response:
    return Response(
        content=result.model_dump_json(),
        status_code=200,
        media_type="application/json",
        headers={"Cache-Control": "no-store"},
    )


def _nesting_within_bound(body: bytes) -> bool:
    depth = 0
    quoted = False
    escaped = False
    for byte in body:
        if quoted:
            if escaped:
                escaped = False
            elif byte == 0x5C:
                escaped = True
            elif byte == 0x22:
                quoted = False
        elif byte == 0x22:
            quoted = True
        elif byte in (0x7B, 0x5B):
            depth += 1
            if depth > MAX_JSON_NESTING:
                return False
        elif byte in (0x7D, 0x5D):
            depth -= 1
            if depth < 0:
                return False
    return depth == 0 and not quoted


def create_agent_live_intake_router(
    *,
    service: AgentLiveIntakeAdmissionService,
    authenticator: LiveIntakeAuthenticator,
    expected_source: AgentLiveIntakeSourceV1,
    correlation_id_factory: Callable[[], str],
) -> APIRouter:
    """Create exactly one guarded POST; caller controls production registration."""
    router = APIRouter()

    async def installation_intake(request: Request) -> Response:
        if (
            request.url.scheme != "https"
            or request.url.hostname != expected_source.host
            or request.url.path != INTAKE_PATH
            or request.query_params
            or "cookie" in request.headers
            or "transfer-encoding" in request.headers
            or "content-encoding" in request.headers
            or "forwarded" in request.headers
            or any(name.startswith("x-forwarded-") for name in request.headers)
            or any("operator" in name for name in request.headers if name.startswith("x-"))
        ):
            return _response(_rejected("malformed"))
        content_type = request.headers.get("content-type", "").strip().lower()
        if content_type != "application/json":
            return _response(_rejected("malformed"))
        try:
            content_length = int(request.headers["content-length"])
        except (KeyError, TypeError, ValueError):
            return _response(_rejected("malformed"))
        if not 0 < content_length <= MAX_ENVELOPE_BYTES:
            return _response(_rejected("malformed"))
        authorization = request.headers.get("authorization", "")
        match = _BEARER.fullmatch(authorization)
        if match is None:
            return _response(_rejected("unauthenticated"))
        try:
            authentication = AgentLiveIntakeAuthenticationContextV1.model_validate(
                authenticator.authenticate(match.group(1)).model_dump(mode="python")
            )
            if authentication.source != expected_source:
                return _response(_rejected("unauthenticated"))
        except LiveIntakeAuthenticationError as error:
            return _response(_rejected(error.code))
        except Exception:  # noqa: BLE001 - authentication details remain redacted
            return _response(_rejected("unauthenticated"))
        try:
            idempotency_key = TypeAdapter(IdempotencyKey).validate_python(
                request.headers["idempotency-key"], strict=True
            )
            correlation_id = TypeAdapter(CorrelationId).validate_python(
                correlation_id_factory(), strict=True
            )
            buffered = bytearray()
            async for chunk in request.stream():
                buffered.extend(chunk)
                if len(buffered) > MAX_ENVELOPE_BYTES:
                    return _response(_rejected("malformed"))
            body = bytes(buffered)
            if (
                len(body) != content_length
                or len(body) > MAX_ENVELOPE_BYTES
                or not _nesting_within_bound(body)
            ):
                return _response(_rejected("malformed"))
            envelope = parse_envelope_json(body)
            result = service.admit(
                envelope,
                authentication=authentication,
                idempotency_key=idempotency_key,
                correlation_id=correlation_id,
            )
            return _response(AgentLiveIntakeResultV1.model_validate(result))
        except Exception:  # noqa: BLE001 - parsing and adapter failures stay closed
            return _response(_rejected("malformed"))

    router.add_api_route(
        INTAKE_PATH,
        installation_intake,
        methods=["POST"],
        name="agent_live_intake_admission",
        response_model=AgentLiveIntakeResultV1,
        openapi_extra={
            "parameters": [
                {
                    "name": "Authorization",
                    "in": "header",
                    "required": True,
                    "schema": {"type": "string", "pattern": r"^Bearer [\x21-\x7e]{1,4096}$"},
                },
                {
                    "name": "Idempotency-Key",
                    "in": "header",
                    "required": True,
                    "schema": {"type": "string", "minLength": 1, "maxLength": 128, "pattern": r"^[\x21-\x7e]+$"},
                },
            ],
            "requestBody": {
                "required": True,
                "content": {"application/json": {"schema": AgentLiveIntakeEnvelopeV1.model_json_schema()}},
            },
        },
    )
    return router


assert AUTHENTICATED_CORE_PRINCIPAL == "atlas-core/install-intake-v1"
assert AUTHENTICATED_CORE_PERMISSION == "installation_intake:create"
