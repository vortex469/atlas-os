"""Guarded Core API for v0.39 worker-queue reservation evidence."""

from __future__ import annotations

import json
import re
from typing import Annotated, Any

from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from pydantic import ValidationError, WithJsonSchema

from app.core.exceptions import request_id_for
from app.operator_auth.dependencies import (
    require_operator_mutation,
    require_operator_permission,
)
from app.operator_auth.models import (
    INSTALLATION_WORKER_QUEUE_RESERVATION_READ,
    INSTALLATION_WORKER_QUEUE_RESERVATION_RECORD,
)
from app.worker_queue_reservation.contract import (
    MAX_CREATE_BYTES,
    MAX_CREATE_NESTING,
    WorkerQueueReservationCollectionV1,
    WorkerQueueReservationCreateV1,
    WorkerQueueReservationRedactedErrorV1,
    WorkerQueueReservationResultV1,
    opaque_fingerprint,
)

_UUID4 = r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"
_create_permission = require_operator_mutation(
    INSTALLATION_WORKER_QUEUE_RESERVATION_RECORD
)
_read_permission = require_operator_permission(INSTALLATION_WORKER_QUEUE_RESERVATION_READ)

router = APIRouter(
    prefix="/installation/candidate-records",
    tags=["Worker Queue Reservations"],
)

_ERRORS = {
    code: {"model": WorkerQueueReservationResultV1}
    for code in (401, 403, 404, 409, 413, 415, 422, 429, 503)
}


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
        if depth > MAX_CREATE_NESTING:
            return depth
        if isinstance(current, dict):
            pending.extend((child, depth + 1) for child in current.values())
        elif isinstance(current, list):
            pending.extend((child, depth + 1) for child in current)
    return maximum


async def _body(request: Request) -> WorkerQueueReservationCreateV1:
    media_type = request.headers.get("content-type", "").split(";", 1)[0]
    if media_type.strip().lower() != "application/json":
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
        decoded = json.loads(raw, object_pairs_hook=_pairs)
        if not isinstance(decoded, dict) or _depth(decoded) > MAX_CREATE_NESTING:
            raise ValueError("invalid JSON shape")
        return WorkerQueueReservationCreateV1.model_validate(decoded)
    except (
        UnicodeDecodeError,
        json.JSONDecodeError,
        ValidationError,
        ValueError,
        RecursionError,
    ) as error:
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
    value = getattr(request.app.state, "worker_queue_reservation_service", None)
    if value is None:
        raise HTTPException(503)
    return value


def _correlation(value: str):
    safe = value if 0 < len(value) <= 128 else "redacted"
    return opaque_fingerprint("atlas:worker-queue-reservation-correlation:v1", safe)


def _error_result(error_code: str, correlation_id: str) -> WorkerQueueReservationResultV1:
    return WorkerQueueReservationResultV1(
        disposition="blocked",
        reservation=None,
        status=None,
        audit_evidence=None,
        error=WorkerQueueReservationRedactedErrorV1(
            error_code=error_code,
            correlation_fingerprint=_correlation(correlation_id),
        ),
    )


def _json_error(error_code: str, status_code: int, correlation_id: str) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content=jsonable_encoder(_error_result(error_code, correlation_id)),
    )


def _service_response(result: WorkerQueueReservationResultV1) -> JSONResponse:
    assert result.error is not None
    status_code = {
        "unauthenticated": 401,
        "forbidden": 403,
        "not_found": 404,
        "not_eligible": 409,
        "expired": 409,
        "conflict": 409,
        "quota_exceeded": 409,
        "malformed": 422,
        "invalid_request": 422,
        "record_too_large": 413,
        "rate_limited": 429,
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
    "/{candidate_record_id}/worker-queue-reservations",
    response_model=WorkerQueueReservationResultV1,
    status_code=201,
    responses=_ERRORS,
    summary="Record worker queue reservation evidence",
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
                    "schema": WorkerQueueReservationCreateV1.model_json_schema()
                }
            },
        },
    },
)
async def create_worker_queue_reservation(
    request: Request,
    response: Response,
    candidate_record_id: Annotated[
        str, WithJsonSchema({"type": "string", "pattern": _UUID4})
    ],
) -> WorkerQueueReservationResultV1 | JSONResponse:
    correlation_id = request_id_for(request)
    if request.query_params or re.fullmatch(_UUID4, candidate_record_id, re.ASCII) is None:
        return _json_error("malformed", 422, correlation_id)
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
        code = "internal_error" if error.status_code == 503 else "malformed"
        return _json_error(code, error.status_code, correlation_id)
    except Exception:  # noqa: BLE001 - route failures remain redacted
        return _json_error("internal_error", 503, correlation_id)
    if result.error is not None:
        return _service_response(result)
    if result.disposition == "exact_duplicate":
        response.status_code = 200
    return result


@router.get(
    "/{candidate_record_id}/worker-queue-reservations",
    response_model=WorkerQueueReservationCollectionV1,
    responses=_ERRORS,
    summary="List owned worker queue reservation evidence",
)
async def list_worker_queue_reservations(
    request: Request,
    candidate_record_id: Annotated[
        str, WithJsonSchema({"type": "string", "pattern": _UUID4})
    ],
) -> WorkerQueueReservationCollectionV1 | JSONResponse:
    correlation_id = request_id_for(request)
    if (
        request.query_params
        or await request.body()
        or re.fullmatch(_UUID4, candidate_record_id, re.ASCII) is None
    ):
        return _json_error("malformed", 422, correlation_id)
    try:
        principal = _read_permission(request)
        results = _service(request).list(
            authenticated_operator_id=principal.operator_id,
            permission_verified=True,
            correlation_id=correlation_id,
        )
    except HTTPException as error:
        return _authentication_error(error, correlation_id)
    except Exception:  # noqa: BLE001 - route failures remain redacted
        return _json_error("internal_error", 503, correlation_id)
    failure = next((item for item in results if item.error is not None), None)
    if failure is not None:
        return _service_response(failure)
    owned = tuple(
        item
        for item in results
        if item.reservation is not None
        and item.reservation.candidate_record_id == candidate_record_id
    )
    return WorkerQueueReservationCollectionV1(items=owned, count=len(owned))


@router.get(
    "/{candidate_record_id}/worker-queue-reservations/{reservation_id}",
    response_model=WorkerQueueReservationResultV1,
    responses=_ERRORS,
    summary="Read owned worker queue reservation evidence",
)
async def get_worker_queue_reservation(
    request: Request,
    candidate_record_id: Annotated[
        str, WithJsonSchema({"type": "string", "pattern": _UUID4})
    ],
    reservation_id: Annotated[str, WithJsonSchema({"type": "string", "pattern": _UUID4})],
) -> WorkerQueueReservationResultV1 | JSONResponse:
    correlation_id = request_id_for(request)
    if (
        request.query_params
        or await request.body()
        or re.fullmatch(_UUID4, candidate_record_id, re.ASCII) is None
        or re.fullmatch(_UUID4, reservation_id, re.ASCII) is None
    ):
        return _json_error("malformed", 422, correlation_id)
    try:
        principal = _read_permission(request)
        result = _service(request).get(
            authenticated_operator_id=principal.operator_id,
            permission_verified=True,
            reservation_id=reservation_id,
            correlation_id=correlation_id,
        )
    except HTTPException as error:
        return _authentication_error(error, correlation_id)
    except Exception:  # noqa: BLE001 - route failures remain redacted
        return _json_error("internal_error", 503, correlation_id)
    if result.error is not None:
        return _service_response(result)
    if result.reservation is None or result.reservation.candidate_record_id != candidate_record_id:
        return _json_error("not_found", 404, correlation_id)
    return result


@router.api_route(
    "/{candidate_record_id}/worker-queue-reservations",
    methods=["DELETE", "HEAD", "OPTIONS", "PATCH", "PUT", "TRACE"],
    include_in_schema=False,
)
def reject_worker_queue_reservation_collection_method() -> None:
    raise HTTPException(405, headers={"Allow": "GET, POST"})


@router.api_route(
    "/{candidate_record_id}/worker-queue-reservations/{reservation_id}",
    methods=["DELETE", "HEAD", "OPTIONS", "PATCH", "POST", "PUT", "TRACE"],
    include_in_schema=False,
)
def reject_worker_queue_reservation_item_method() -> None:
    raise HTTPException(405, headers={"Allow": "GET"})
