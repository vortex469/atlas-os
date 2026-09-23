"""Guarded, default-off Core API for reference-only control-plane evidence."""

from __future__ import annotations

import json
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, TypeAdapter, ValidationError

from app.control_plane.contract import (
    MAX_BYTES,
    ControlPlaneEvidenceCreateV1,
    ControlPlaneEvidenceErrorV1,
    ControlPlaneEvidenceRecordV1,
    Identity,
)
from app.core.exceptions import request_id_for
from app.operator_auth.dependencies import (
    require_operator_mutation,
    require_operator_permission,
)
from app.operator_auth.models import (
    CONTROL_PLANE_EVIDENCE_READ,
    CONTROL_PLANE_EVIDENCE_RECORD,
    OperatorPrincipal,
)

router = APIRouter(prefix="/control-plane-evidence", tags=["Control Plane Evidence"])
_read = require_operator_permission(CONTROL_PLANE_EVIDENCE_READ)
_create = require_operator_mutation(CONTROL_PLANE_EVIDENCE_RECORD)
ReadPrincipal = Annotated[OperatorPrincipal, Depends(_read)]
CreatePrincipal = Annotated[OperatorPrincipal, Depends(_create)]
IdempotencyKey = Annotated[str, Header(alias="Idempotency-Key", min_length=1, max_length=128)]
MAX_NESTING = 16


class _Closed(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class ControlPlaneEvidenceCollectionV1(_Closed):
    records: tuple[ControlPlaneEvidenceRecordV1, ...]


def _pairs(values: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in values:
        if key in result:
            raise ValueError("duplicate JSON member")
        result[key] = value
    return result


def _depth(value: Any) -> int:
    pending = [(value, 1)]
    maximum = 1
    while pending:
        current, depth = pending.pop()
        maximum = max(maximum, depth)
        if depth > MAX_NESTING:
            return depth
        if isinstance(current, dict):
            pending.extend((child, depth + 1) for child in current.values())
        elif isinstance(current, list):
            pending.extend((child, depth + 1) for child in current)
    return maximum


async def _body(request: Request) -> ControlPlaneEvidenceCreateV1:
    media_type = request.headers.get("content-type", "").split(";", 1)[0]
    if media_type.strip().lower() != "application/json":
        raise HTTPException(415)
    lengths = request.headers.getlist("content-length")
    if len(lengths) > 1 or (
        lengths and (not lengths[0].isascii() or not lengths[0].isdecimal() or int(lengths[0]) > MAX_BYTES)
    ):
        raise HTTPException(413)
    raw = await request.body()
    if len(raw) > MAX_BYTES:
        raise HTTPException(413)
    try:
        decoded = json.loads(raw, object_pairs_hook=_pairs)
        if not isinstance(decoded, dict) or _depth(decoded) > MAX_NESTING:
            raise ValueError("invalid JSON shape")
        return ControlPlaneEvidenceCreateV1.model_validate(decoded)
    except (UnicodeDecodeError, json.JSONDecodeError, ValidationError, ValueError, RecursionError) as error:
        raise HTTPException(422) from error


def _key(value: str) -> str:
    if not value.isascii() or not 1 <= len(value.encode("ascii")) <= 128 or any(
        not 0x21 <= ord(character) <= 0x7E for character in value
    ):
        raise HTTPException(422)
    return value


def _correlation(value: str) -> str:
    from app.control_plane.contract import fingerprint

    safe = value if type(value) is str and 0 < len(value) <= 128 else "redacted"
    return fingerprint("control-plane-correlation", safe)


def _error(code: str, status_code: int, correlation_id: str) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content=jsonable_encoder(
            ControlPlaneEvidenceErrorV1(error_code=code, correlation_fingerprint=_correlation(correlation_id))
        ),
    )


def _service(request: Request):
    return getattr(request.app.state, "control_plane_evidence_service", None)


def _service_error(result: ControlPlaneEvidenceErrorV1, correlation_id: str) -> JSONResponse:
    status = {
        "unauthenticated": 401,
        "forbidden": 403,
        "evidence_not_found": 404,
        "invalid_request": 422,
        "idempotency_conflict": 409,
        "permanent_subject_reserved": 409,
        "quota_exceeded": 409,
        "disabled": 503,
        "unavailable": 503,
        "store_corrupt": 503,
        "append_indeterminate": 503,
    }.get(result.error_code, 409)
    return _error(result.error_code, status, correlation_id)


@router.post("", response_model=ControlPlaneEvidenceRecordV1, status_code=201,
             responses={code: {"model": ControlPlaneEvidenceErrorV1} for code in (401, 403, 409, 413, 415, 422, 429, 503)},
             summary="Record reference-only control-plane evidence")
async def create_control_plane_evidence(
    request: Request, response: Response, principal: CreatePrincipal, idempotency_key: IdempotencyKey
) -> ControlPlaneEvidenceRecordV1 | JSONResponse:
    correlation_id = request_id_for(request)
    try:
        payload = await _body(request)
        result = _service(request)
        if result is None:
            return _error("disabled", 503, correlation_id)
        key = _key(idempotency_key)
        payload = payload.model_copy(update={"idempotency_key": key})
        value = result.create(payload, authenticated_owner_id=principal.operator_id,
                              permission_verified=True, correlation_id=correlation_id)
        if isinstance(value, ControlPlaneEvidenceErrorV1):
            return _service_error(value, correlation_id)
        # The header is authoritative for idempotency; a body key cannot be
        # substituted without changing the P2 request fingerprint.
        if value.idempotency_key_fingerprint != _idempotency_fingerprint(principal.operator_id, key):
            return _error("invalid_request", 422, correlation_id)
        return value
    except HTTPException as error:
        return _error({415: "invalid_request", 413: "invalid_request", 422: "invalid_request"}.get(error.status_code, "unavailable"), error.status_code, correlation_id)
    except Exception:  # noqa: BLE001 - never expose store or request details
        return _error("unavailable", 503, correlation_id)


def _idempotency_fingerprint(owner: str, key: str) -> str:
    from app.control_plane.contract import idempotency_fingerprint

    return idempotency_fingerprint(owner, key)


@router.get("", response_model=ControlPlaneEvidenceCollectionV1,
            responses={code: {"model": ControlPlaneEvidenceErrorV1} for code in (401, 403, 422, 503)},
            summary="List owned control-plane evidence")
async def list_control_plane_evidence(request: Request, principal: ReadPrincipal) -> ControlPlaneEvidenceCollectionV1 | JSONResponse:
    correlation_id = request_id_for(request)
    if request.query_params or await request.body():
        return _error("invalid_request", 422, correlation_id)
    service = _service(request)
    if service is None:
        return _error("disabled", 503, correlation_id)
    result = service.list(authenticated_owner_id=principal.operator_id, permission_verified=True, correlation_id=correlation_id)
    if isinstance(result, ControlPlaneEvidenceErrorV1):
        return _service_error(result, correlation_id)
    return ControlPlaneEvidenceCollectionV1(records=tuple(result))


@router.get("/{subject_id}", response_model=ControlPlaneEvidenceRecordV1,
            responses={code: {"model": ControlPlaneEvidenceErrorV1} for code in (401, 403, 404, 422, 503)},
            summary="Read owned control-plane evidence")
async def get_control_plane_evidence(request: Request, subject_id: str, principal: ReadPrincipal) -> ControlPlaneEvidenceRecordV1 | JSONResponse:
    correlation_id = request_id_for(request)
    if request.query_params or await request.body():
        return _error("invalid_request", 422, correlation_id)
    try:
        TypeAdapter(Identity).validate_python(subject_id, strict=True)
    except (ValueError, TypeError):
        return _error("invalid_request", 422, correlation_id)
    service = _service(request)
    if service is None:
        return _error("disabled", 503, correlation_id)
    result = service.get(authenticated_owner_id=principal.operator_id, permission_verified=True,
                         subject_id=subject_id, correlation_id=correlation_id)
    if isinstance(result, ControlPlaneEvidenceErrorV1):
        return _service_error(result, correlation_id)
    return result


@router.api_route("", methods=["DELETE", "HEAD", "OPTIONS", "PATCH", "PUT", "TRACE"], include_in_schema=False)
def reject_collection_methods() -> None:
    raise HTTPException(405, headers={"Allow": "GET, POST"})


@router.api_route("/{subject_id}", methods=["DELETE", "HEAD", "OPTIONS", "PATCH", "POST", "PUT", "TRACE"], include_in_schema=False)
def reject_item_methods() -> None:
    raise HTTPException(405, headers={"Allow": "GET"})
