"""Guarded Core API for v0.43 queue observation evidence."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from pydantic import WithJsonSchema

from app.core.exceptions import request_id_for
from app.operator_auth.dependencies import (
    require_operator_mutation,
    require_operator_permission,
)
from app.operator_auth.models import (
    INSTALLATION_QUEUE_OBSERVATION_READ,
    INSTALLATION_QUEUE_OBSERVATION_RECORD,
)
from app.queue_observation_receipt.contract import (
    MAX_CREATE_BYTES,
    QueueObservationReceiptCollectionV1,
    QueueObservationReceiptCreateV1,
    QueueObservationReceiptRedactedErrorV1,
    QueueObservationReceiptResultV1,
    opaque_fingerprint,
    parse_create_json,
)

_UUID4 = r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"
_UUID5 = r"^[0-9a-f]{8}-[0-9a-f]{4}-5[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"
_create_permission = require_operator_mutation(INSTALLATION_QUEUE_OBSERVATION_RECORD)
_read_permission = require_operator_permission(INSTALLATION_QUEUE_OBSERVATION_READ)

router = APIRouter(
    prefix="/installation/candidate-records",
    tags=["Queue Observations"],
)

_ERRORS = {
    code: {"model": QueueObservationReceiptResultV1}
    for code in (401, 403, 404, 409, 413, 415, 422, 429, 503)
}


async def _body(request: Request) -> QueueObservationReceiptCreateV1:
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
    value = getattr(request.app.state, "queue_observation_service", None)
    if value is None:
        value = getattr(request.app.state, "queue_observation_receipt_service", None)
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
    return opaque_fingerprint("atlas:queue-observation-correlation:v1", safe)


def _error_result(error_code: str, correlation_id: str) -> QueueObservationReceiptResultV1:
    correlation = _correlation(correlation_id)
    return QueueObservationReceiptResultV1(
        ok=False,
        outcome="failure",
        record=None,
        status=None,
        error=QueueObservationReceiptRedactedErrorV1(
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


def _service_response(result: QueueObservationReceiptResultV1) -> JSONResponse:
    assert result.error is not None
    status_code = {
        "unauthenticated": 401,
        "forbidden": 403,
        "not_found": 404,
        "evidence_not_found": 404,
        "ownership_mismatch": 404,
        "permission_scope_missing": 403,
        "installation_capability_unsupported": 409,
        "linkage_mismatch": 409,
        "fingerprint_mismatch": 409,
        "evidence_stale": 409,
        "evidence_expired": 409,
        "v042_enqueue_not_active": 409,
        "v042_enqueue_not_recorded": 409,
        "queue_identity_mismatch": 409,
        "item_identity_mismatch": 409,
        "receipt_evidence_invalid": 409,
        "observation_malformed": 409,
        "ambiguous_state": 409,
        "executable_payload": 409,
        "unsupported_authority": 409,
        "reservation_before_effect_failed": 409,
        "append_indeterminate": 503,
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
    "/{candidate_record_id}/queue-observations",
    response_model=QueueObservationReceiptResultV1,
    status_code=201,
    responses=_ERRORS,
    summary="Record bounded queue observation evidence",
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
                    "schema": QueueObservationReceiptCreateV1.model_json_schema()
                }
            },
        },
    },
)
async def create_queue_observation(
    request: Request,
    response: Response,
    candidate_record_id: Annotated[
        str, WithJsonSchema({"type": "string", "pattern": _UUID4})
    ],
) -> QueueObservationReceiptResultV1 | JSONResponse:
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
    "/{candidate_record_id}/queue-observations",
    response_model=QueueObservationReceiptCollectionV1,
    responses=_ERRORS,
    summary="List owned queue observation evidence",
)
async def list_queue_observations(
    request: Request,
    candidate_record_id: Annotated[
        str, WithJsonSchema({"type": "string", "pattern": _UUID4})
    ],
) -> QueueObservationReceiptCollectionV1 | JSONResponse:
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
    "/{candidate_record_id}/queue-observations/{observation_id}",
    response_model=QueueObservationReceiptResultV1,
    responses=_ERRORS,
    summary="Read owned queue observation evidence",
)
async def get_queue_observation(
    request: Request,
    candidate_record_id: Annotated[
        str, WithJsonSchema({"type": "string", "pattern": _UUID4})
    ],
    observation_id: Annotated[str, WithJsonSchema({"type": "string", "pattern": _UUID5})],
) -> QueueObservationReceiptResultV1 | JSONResponse:
    correlation_id = request_id_for(request)
    if (
        request.query_params
        or await request.body()
        or not _canonical_uuid(candidate_record_id, version=4)
        or not _canonical_uuid(observation_id, version=5)
    ):
        return _json_error("invalid_request", 422, correlation_id)
    try:
        principal = _read_permission(request)
        result = _service(request).get(
            authenticated_operator_id=principal.operator_id,
            permission_verified=True,
            receipt_id=observation_id,
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
    "/{candidate_record_id}/queue-observations",
    methods=["DELETE", "HEAD", "OPTIONS", "PATCH", "PUT", "TRACE"],
    include_in_schema=False,
)
def reject_queue_observation_collection_method() -> None:
    raise HTTPException(405, headers={"Allow": "GET, POST"})


@router.api_route(
    "/{candidate_record_id}/queue-observations/{observation_id}",
    methods=["DELETE", "HEAD", "OPTIONS", "PATCH", "POST", "PUT", "TRACE"],
    include_in_schema=False,
)
def reject_queue_observation_item_method() -> None:
    raise HTTPException(405, headers={"Allow": "GET"})
