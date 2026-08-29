"""Dormant test-only HTTP adapter for the frozen real-intake contract."""

from __future__ import annotations

import re
from collections.abc import Callable
from typing import Literal, Protocol

from fastapi import APIRouter, Request, Response
from pydantic import TypeAdapter

from .models import (
    MAX_REQUEST_BYTES,
    AgentInstallationIntakeAuthenticationContextV1,
    AgentInstallationIntakeRequestV1,
    AgentInstallationIntakeResultV1,
    CorrelationId,
    IdempotencyKey,
    parse_intake_request_json,
)
from .service import AgentRealIntakeEvidenceService

INTAKE_PATH = "/api/v1/internal/installation-intake"
_BEARER = re.compile(r"Bearer ([\x21-\x7e]{1,4096})")


class DormantIntakeAuthenticationError(ValueError):
    """Sanitized authentication failure from an injected test authenticator."""

    def __init__(self, code: Literal["unauthenticated", "unauthorized"]) -> None:
        self.code = code
        super().__init__(code)


class DormantIntakeAuthenticator(Protocol):
    """Authenticate only the dedicated Core intake credential."""

    def authenticate(
        self, bearer_credential: str
    ) -> AgentInstallationIntakeAuthenticationContextV1: ...


def _rejected(
    code: Literal[
        "unauthenticated", "unauthorized", "malformed", "unavailable"
    ],
) -> AgentInstallationIntakeResultV1:
    return AgentInstallationIntakeResultV1(
        intake_request_id=None,
        outcome="rejected",
        admission=None,
        reason_code=code,
    )


def _response(result: AgentInstallationIntakeResultV1) -> Response:
    return Response(
        content=result.model_dump_json(),
        status_code=200,
        media_type="application/json",
        headers={"Cache-Control": "no-store"},
    )


def create_dormant_real_intake_router(
    *,
    service: AgentRealIntakeEvidenceService,
    authenticator: DormantIntakeAuthenticator,
    correlation_id_factory: Callable[[], str],
    enabled: bool = False,
) -> APIRouter:
    """Build the isolated route; production Agent must never call this factory."""
    router = APIRouter()

    async def installation_intake(request: Request) -> Response:
        if not enabled:
            return _response(_rejected("unavailable"))
        if (
            request.url.scheme != "https"
            or request.query_params
            or "cookie" in request.headers
            or "transfer-encoding" in request.headers
            or "content-encoding" in request.headers
            or "forwarded" in request.headers
            or any(name.startswith("x-forwarded-") for name in request.headers)
            or any("operator" in name for name in request.headers if name.startswith("x-"))
        ):
            return _response(_rejected("malformed"))
        content_type = request.headers.get("content-type", "").split(";", 1)[0].strip().lower()
        if content_type != "application/json":
            return _response(_rejected("malformed"))
        try:
            content_length = int(request.headers["content-length"])
        except (KeyError, TypeError, ValueError):
            return _response(_rejected("malformed"))
        if not 0 < content_length <= MAX_REQUEST_BYTES:
            return _response(_rejected("malformed"))
        authorization = request.headers.get("authorization", "")
        match = _BEARER.fullmatch(authorization)
        if match is None:
            return _response(_rejected("unauthenticated"))
        try:
            authentication = AgentInstallationIntakeAuthenticationContextV1.model_validate(
                authenticator.authenticate(match.group(1)).model_dump(mode="python")
            )
        except DormantIntakeAuthenticationError as error:
            return _response(_rejected(error.code))
        except Exception:  # noqa: BLE001 - authentication failures are indistinguishable
            return _response(_rejected("unauthenticated"))
        try:
            idempotency_key = TypeAdapter(IdempotencyKey).validate_python(
                request.headers["idempotency-key"], strict=True
            )
            correlation_id = TypeAdapter(CorrelationId).validate_python(
                correlation_id_factory(), strict=True
            )
            body = await request.body()
            if len(body) != content_length or len(body) > MAX_REQUEST_BYTES:
                return _response(_rejected("malformed"))
            parsed = parse_intake_request_json(body)
            result = service.preserve(
                parsed,
                authentication=authentication,
                idempotency_key=idempotency_key,
                correlation_id=correlation_id,
            )
            return _response(AgentInstallationIntakeResultV1.model_validate(result))
        except Exception:  # noqa: BLE001 - adapter errors expose only closed codes
            return _response(_rejected("malformed"))

    router.add_api_route(
        INTAKE_PATH,
        installation_intake,
        methods=["POST"],
        name="dormant_agent_installation_intake",
        response_model=AgentInstallationIntakeResultV1,
        openapi_extra={
            "parameters": [
                {
                    "name": "Authorization",
                    "in": "header",
                    "required": True,
                    "schema": {
                        "type": "string",
                        "pattern": r"^Bearer [\x21-\x7e]{1,4096}$",
                    },
                },
                {
                    "name": "Idempotency-Key",
                    "in": "header",
                    "required": True,
                    "schema": {
                        "type": "string",
                        "minLength": 1,
                        "maxLength": 128,
                        "pattern": r"^[\x21-\x7e]+$",
                    },
                },
            ],
            "requestBody": {
                "required": True,
                "content": {
                    "application/json": {
                        "schema": AgentInstallationIntakeRequestV1.model_json_schema()
                    }
                },
            }
        },
    )
    return router
