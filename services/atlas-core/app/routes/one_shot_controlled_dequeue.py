"""Guarded Core API for v0.45 one-shot controlled dequeue evidence."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from pydantic import WithJsonSchema

from app.core.exceptions import request_id_for
from app.one_shot_controlled_dequeue.contract import (
    MAX_CREATE_BYTES,
    OneShotControlledDequeueCollectionV1,
    OneShotControlledDequeueCreateV1,
    OneShotControlledDequeueRedactedErrorV1,
    OneShotControlledDequeueResultV1,
    opaque_fingerprint,
    parse_create_json,
)
from app.operator_auth.dependencies import (
    require_operator_mutation,
    require_operator_permission,
)
from app.operator_auth.models import (
    INSTALLATION_ONE_SHOT_CONTROLLED_DEQUEUE_READ,
    INSTALLATION_ONE_SHOT_CONTROLLED_DEQUEUE_RECORD,
)

_UUID4 = r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"
_UUID5 = r"^[0-9a-f]{8}-[0-9a-f]{4}-5[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"
_create_permission = require_operator_mutation(
    INSTALLATION_ONE_SHOT_CONTROLLED_DEQUEUE_RECORD
)
_read_permission = require_operator_permission(
    INSTALLATION_ONE_SHOT_CONTROLLED_DEQUEUE_READ
)

router = APIRouter(
    prefix="/installation/candidate-records",
    tags=["One-Shot Controlled Dequeues"],
)

_ERRORS = {
    code: {"model": OneShotControlledDequeueResultV1}
    for code in (401, 403, 404, 409, 413, 415, 422, 429, 503)
}


async def _body(request: Request) -> OneShotControlledDequeueCreateV1:
    if request.headers.get("content-type", "") != "application/json":
        raise HTTPException(415)
    lengths = request.headers.getlist("content-length")
    if len(lengths) > 1 or (
        lengths
        and (
            not lengths[0].isascii()
            or not lengths[0].isdecimal()
            or int(lengths[0]) > MAX_CREATE_BYTES
        )
    ):
        raise HTTPException(413)
    raw = await request.body()
    if len(raw) > MAX_CREATE_BYTES:
        raise HTTPException(413)
    try:
        return parse_create_json(raw)
    except Exception as error:
        raise HTTPException(422) from error


def _idempotency_key(value: str | None) -> str:
    if (
        value is None
        or not value.isascii()
        or not 16 <= len(value.encode("ascii")) <= 128
        or any(not 0x21 <= ord(character) <= 0x7E for character in value)
    ):
        raise HTTPException(422)
    return value


def _service(request: Request):
    value = getattr(request.app.state, "one_shot_controlled_dequeue_service", None)
    if value is None:
        raise HTTPException(503)
    return value


def _canonical_uuid(value: str, *, version: int) -> bool:
    try:
        parsed = uuid.UUID(value, version=version)
    except ValueError:
        return False
    return str(parsed) == value and parsed.version == version


def _correlation(value: str):
    safe = value if 0 < len(value) <= 128 else "redacted"
    return opaque_fingerprint("atlas:one-shot-controlled-dequeue-correlation:v1", safe)


def _error_result(
    error_code: str, correlation_id: str
) -> OneShotControlledDequeueResultV1:
    correlation = _correlation(correlation_id)
    return OneShotControlledDequeueResultV1(
        ok=False,
        outcome="failure",
        record=None,
        status=None,
        error=OneShotControlledDequeueRedactedErrorV1(
            error_code=error_code,
            correlation_fingerprint=correlation,
        ),
        correlation_fingerprint=correlation,
    )


def _json_error(error_code: str, status_code: int, correlation_id: str) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content=jsonable_encoder(_error_result(error_code, correlation_id)),
    )


def _service_response(result: OneShotControlledDequeueResultV1) -> JSONResponse:
    assert result.error is not None
    status_code = {
        "unauthenticated": 401,
        "forbidden": 403,
        "not_found": 404,
        "evidence_not_found": 404,
        "ownership_mismatch": 404,
        "permission_scope_missing": 403,
        "installation_capability_unsupported": 409,
        "v044_admission_not_active": 409,
        "v044_admission_not_recorded": 409,
        "v044_admission_not_eligible": 409,
        "v043_observation_not_active": 409,
        "v043_observation_not_recorded": 409,
        "v043_receipt_not_contract_eligible": 409,
        "v042_enqueue_not_active": 409,
        "v042_enqueue_not_recorded": 409,
        "linkage_mismatch": 409,
        "queue_identity_mismatch": 409,
        "item_identity_mismatch": 409,
        "observation_receipt_mismatch": 409,
        "fingerprint_mismatch": 409,
        "inherited_limits_mismatch": 409,
        "evidence_stale": 409,
        "evidence_expired": 409,
        "ambiguous_state": 409,
        "executable_payload": 409,
        "unsupported_authority": 409,
        "dequeue_adapter_unavailable": 503,
        "dequeue_receipt_mismatch": 503,
        "reservation_before_effect_failed": 409,
        "permanent_subject_reserved": 409,
        "idempotency_conflict": 409,
        "append_indeterminate": 503,
        "dequeue_indeterminate": 503,
        "quota_exceeded": 409,
        "conflict": 409,
        "record_too_large": 413,
        "store_corrupt": 503,
        "invalid_request": 422,
        "rate_limited": 429,
        "internal_error": 503,
    }.get(result.error.error_code, 503)
    return JSONResponse(status_code=status_code, content=jsonable_encoder(result))


def _authentication_error(error: HTTPException, correlation_id: str) -> JSONResponse:
    if error.status_code == 401:
        return _json_error("unauthenticated", 401, correlation_id)
    if error.status_code == 429:
        return _json_error("rate_limited", 429, correlation_id)
    if error.status_code == 503:
        return _json_error("internal_error", 503, correlation_id)
    return _json_error("forbidden", 403, correlation_id)


@router.post(
    "/{candidate_record_id}/one-shot-controlled-dequeues",
    response_model=OneShotControlledDequeueResultV1,
    status_code=201,
    responses=_ERRORS,
    summary="Record one bounded controlled dequeue receipt",
    openapi_extra={
        "parameters": [
            {
                "name": "Idempotency-Key",
                "in": "header",
                "required": True,
                "schema": {"type": "string", "minLength": 16, "maxLength": 128},
            }
        ],
        "requestBody": {
            "required": True,
            "content": {
                "application/json": {
                    "schema": OneShotControlledDequeueCreateV1.model_json_schema()
                }
            },
        },
    },
)
async def create_one_shot_controlled_dequeue(
    request: Request,
    response: Response,
    candidate_record_id: Annotated[
        str, WithJsonSchema({"type": "string", "pattern": _UUID4})
    ],
) -> OneShotControlledDequeueResultV1 | JSONResponse:
    correlation_id = request_id_for(request)
    if request.query_params or not _canonical_uuid(candidate_record_id, version=4):
        return _json_error("invalid_request", 422, correlation_id)
    try:
        principal = _create_permission(request)
    except HTTPException as error:
        return _authentication_error(error, correlation_id)
    try:
        payload = await _body(request)
        key = _idempotency_key(request.headers.get("Idempotency-Key"))
        result = _service(request).create(
            payload,
            authenticated_operator_id=principal.operator_id,
            permission_verified=True,
            candidate_record_id=candidate_record_id,
            idempotency_key=key,
            correlation_id=correlation_id,
        )
    except HTTPException as error:
        code = {
            413: "record_too_large",
            503: "internal_error",
        }.get(error.status_code, "invalid_request")
        return _json_error(code, error.status_code, correlation_id)
    except Exception:  # noqa: BLE001 - route failures remain redacted
        return _json_error("internal_error", 503, correlation_id)
    if result.error is not None:
        return _service_response(result)
    response.status_code = 201
    return result


@router.get(
    "/{candidate_record_id}/one-shot-controlled-dequeues",
    response_model=OneShotControlledDequeueCollectionV1,
    responses=_ERRORS,
    summary="List owned one-shot controlled dequeue evidence",
)
async def list_one_shot_controlled_dequeues(
    request: Request,
    candidate_record_id: Annotated[
        str, WithJsonSchema({"type": "string", "pattern": _UUID4})
    ],
) -> OneShotControlledDequeueCollectionV1 | JSONResponse:
    correlation_id = request_id_for(request)
    if (
        request.query_params
        or await request.body()
        or not _canonical_uuid(candidate_record_id, version=4)
    ):
        return _json_error("invalid_request", 422, correlation_id)
    try:
        principal = _read_permission(request)
        result = _service(request).list(
            authenticated_operator_id=principal.operator_id,
            permission_verified=True,
            candidate_record_id=candidate_record_id,
            correlation_id=correlation_id,
        )
    except HTTPException as error:
        return _authentication_error(error, correlation_id)
    except Exception:  # noqa: BLE001 - route failures remain redacted
        return _json_error("internal_error", 503, correlation_id)
    if isinstance(result, tuple):
        failure = next((item for item in result if item.error is not None), None)
        if failure is not None:
            return _service_response(failure)
        return _json_error("internal_error", 503, correlation_id)
    return result


@router.get(
    "/{candidate_record_id}/one-shot-controlled-dequeues/{dequeue_id}",
    response_model=OneShotControlledDequeueResultV1,
    responses=_ERRORS,
    summary="Read owned one-shot controlled dequeue evidence",
)
async def get_one_shot_controlled_dequeue(
    request: Request,
    candidate_record_id: Annotated[
        str, WithJsonSchema({"type": "string", "pattern": _UUID4})
    ],
    dequeue_id: Annotated[str, WithJsonSchema({"type": "string", "pattern": _UUID5})],
) -> OneShotControlledDequeueResultV1 | JSONResponse:
    correlation_id = request_id_for(request)
    if (
        request.query_params
        or await request.body()
        or not _canonical_uuid(candidate_record_id, version=4)
        or not _canonical_uuid(dequeue_id, version=5)
    ):
        return _json_error("invalid_request", 422, correlation_id)
    try:
        principal = _read_permission(request)
        result = _service(request).get(
            authenticated_operator_id=principal.operator_id,
            permission_verified=True,
            dequeue_id=dequeue_id,
            correlation_id=correlation_id,
        )
    except HTTPException as error:
        return _authentication_error(error, correlation_id)
    except Exception:  # noqa: BLE001 - route failures remain redacted
        return _json_error("internal_error", 503, correlation_id)
    if result.error is not None:
        return _service_response(result)
    if result.record is None or result.record.candidate_record_id != candidate_record_id:
        return _json_error("not_found", 404, correlation_id)
    return result


@router.api_route(
    "/{candidate_record_id}/one-shot-controlled-dequeues",
    methods=["DELETE", "HEAD", "OPTIONS", "PATCH", "PUT", "TRACE"],
    include_in_schema=False,
)
def reject_one_shot_controlled_dequeue_collection_method() -> None:
    raise HTTPException(405, headers={"Allow": "GET, POST"})


@router.api_route(
    "/{candidate_record_id}/one-shot-controlled-dequeues/{dequeue_id}",
    methods=["DELETE", "HEAD", "OPTIONS", "PATCH", "POST", "PUT", "TRACE"],
    include_in_schema=False,
)
def reject_one_shot_controlled_dequeue_item_method() -> None:
    raise HTTPException(405, headers={"Allow": "GET"})
