"""Guarded Core API for v0.52 queue claim/lease/ack receipt evidence."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from pydantic import WithJsonSchema

from app.controlled_worker_queue_claim_lease_acknowledgement.contract import (
    MAX_CREATE_BYTES,
    ControlledWorkerQueueClaimLeaseAcknowledgementCollectionV1,
    ControlledWorkerQueueClaimLeaseAcknowledgementCreateV1,
    ControlledWorkerQueueClaimLeaseAcknowledgementRedactedErrorV1,
    ControlledWorkerQueueClaimLeaseAcknowledgementResultV1,
    opaque_fingerprint,
    parse_create_json,
)
from app.core.exceptions import request_id_for
from app.operator_auth.dependencies import (
    require_operator_mutation,
    require_operator_permission,
)
from app.operator_auth.models import (
    INSTALLATION_CONTROLLED_WORKER_QUEUE_CLAIM_LEASE_ACK_EVALUATE,
    INSTALLATION_CONTROLLED_WORKER_QUEUE_CLAIM_LEASE_ACK_READ,
)

_UUID4 = r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"
_UUID5 = r"^[0-9a-f]{8}-[0-9a-f]{4}-5[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"
_create_permission = require_operator_mutation(
    INSTALLATION_CONTROLLED_WORKER_QUEUE_CLAIM_LEASE_ACK_EVALUATE
)
_read_permission = require_operator_permission(
    INSTALLATION_CONTROLLED_WORKER_QUEUE_CLAIM_LEASE_ACK_READ
)

router = APIRouter(
    prefix="/installation/candidate-records",
    tags=["Controlled Worker Queue Claim Lease Acknowledgement"],
)

_ERRORS = {
    code: {"model": ControlledWorkerQueueClaimLeaseAcknowledgementResultV1}
    for code in (401, 403, 404, 409, 413, 415, 422, 429, 503)
}


async def _body(
    request: Request,
) -> ControlledWorkerQueueClaimLeaseAcknowledgementCreateV1:
    if request.headers.getlist("content-type") != ["application/json"]:
        raise HTTPException(415)
    lengths = request.headers.getlist("content-length")
    if len(lengths) > 1 or (
        lengths
        and (
            not lengths[0].isascii()
            or not lengths[0].isdecimal()
            or len(lengths[0]) > 10
            or int(lengths[0]) > MAX_CREATE_BYTES
        )
    ):
        raise HTTPException(413)
    raw = bytearray()
    async for chunk in request.stream():
        if len(raw) + len(chunk) > MAX_CREATE_BYTES:
            raise HTTPException(413)
        raw.extend(chunk)
    try:
        return parse_create_json(bytes(raw))
    except Exception as error:
        raise HTTPException(422) from error


async def _has_body(request: Request) -> bool:
    async for chunk in request.stream():
        if chunk:
            return True
    return False


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
    value = getattr(
        request.app.state,
        "controlled_worker_queue_claim_lease_acknowledgement_service",
        None,
    )
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
    return opaque_fingerprint(
        "atlas:controlled-worker-queue-claim-lease-acknowledgement-correlation:v1",
        safe,
    )


def _error_result(
    error_code: str, correlation_id: str
) -> ControlledWorkerQueueClaimLeaseAcknowledgementResultV1:
    correlation = _correlation(correlation_id)
    return ControlledWorkerQueueClaimLeaseAcknowledgementResultV1(
        ok=False,
        outcome="failure",
        record=None,
        status=None,
        error=ControlledWorkerQueueClaimLeaseAcknowledgementRedactedErrorV1(
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


def _validated_result(result, operator_id: str, candidate_record_id: str):
    result = ControlledWorkerQueueClaimLeaseAcknowledgementResultV1.model_validate(
        result.model_dump(mode="python")
    )
    if result.record is not None and (
        result.record.operator_id != operator_id
        or result.record.candidate_record_id != candidate_record_id
    ):
        raise HTTPException(404)
    return result


def _service_response(
    result: ControlledWorkerQueueClaimLeaseAcknowledgementResultV1,
) -> JSONResponse:
    assert result.error is not None
    status_code = {
        "unauthenticated": 401,
        "forbidden": 403,
        "not_found": 404,
        "evidence_not_found": 404,
        "ownership_mismatch": 404,
        "permission_scope_missing": 403,
        "installation_capability_unsupported": 409,
        "v051_admission_not_active": 409,
        "v051_admission_not_recorded": 409,
        "linkage_mismatch": 409,
        "fingerprint_mismatch": 409,
        "inherited_limits_mismatch": 409,
        "evidence_stale": 409,
        "evidence_expired": 409,
        "ambiguous_state": 409,
        "caller_supplied_credential": 409,
        "caller_supplied_endpoint": 409,
        "caller_supplied_command": 409,
        "caller_supplied_queue_selector": 409,
        "caller_supplied_claim_token": 409,
        "caller_supplied_lease_token": 409,
        "caller_supplied_acknowledgement_handle": 409,
        "unsupported_authority": 409,
        "reservation_before_effect_failed": 409,
        "permanent_subject_reserved": 409,
        "idempotency_conflict": 409,
        "append_indeterminate": 503,
        "quota_exceeded": 409,
        "adapter_identity_mismatch": 409,
        "reservation_before_effect_missing": 409,
        "claim_receipt_mismatch": 409,
        "lease_receipt_mismatch": 409,
        "acknowledgement_receipt_mismatch": 409,
        "replay_detected": 409,
        "corrupt_adapter_evidence": 409,
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
    "/{candidate_record_id}/controlled-worker-queue-claim-lease-acknowledgements",
    response_model=ControlledWorkerQueueClaimLeaseAcknowledgementResultV1,
    status_code=201,
    responses=_ERRORS,
    summary="Record bounded queue claim/lease/ack receipt evidence",
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
                    "schema": (
                        ControlledWorkerQueueClaimLeaseAcknowledgementCreateV1.model_json_schema()
                    )
                }
            },
        },
    },
)
async def create_controlled_worker_queue_claim_lease_acknowledgement(
    request: Request,
    response: Response,
    candidate_record_id: Annotated[
        str, WithJsonSchema({"type": "string", "pattern": _UUID4})
    ],
) -> ControlledWorkerQueueClaimLeaseAcknowledgementResultV1 | JSONResponse:
    correlation_id = request_id_for(request)
    if request.query_params or not _canonical_uuid(candidate_record_id, version=4):
        return _json_error("invalid_request", 422, correlation_id)
    try:
        principal = _create_permission(request)
    except HTTPException as error:
        return _authentication_error(error, correlation_id)
    except Exception:  # noqa: BLE001 - authentication failures remain redacted
        return _json_error("internal_error", 503, correlation_id)
    try:
        payload = await _body(request)
        keys = request.headers.getlist("Idempotency-Key")
        if len(keys) != 1:
            raise HTTPException(422)
        key = _idempotency_key(keys[0])
        result = _service(request).create(
            payload,
            authenticated_operator_id=principal.operator_id,
            permission_verified=True,
            candidate_record_id=candidate_record_id,
            idempotency_key=key,
            correlation_id=correlation_id,
        )
        result = _validated_result(result, principal.operator_id, candidate_record_id)
    except HTTPException as error:
        code = {
            404: "not_found",
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
    "/{candidate_record_id}/controlled-worker-queue-claim-lease-acknowledgements",
    response_model=ControlledWorkerQueueClaimLeaseAcknowledgementCollectionV1,
    responses=_ERRORS,
    summary="List owned queue claim/lease/ack receipt evidence",
)
async def list_controlled_worker_queue_claim_lease_acknowledgements(
    request: Request,
    candidate_record_id: Annotated[
        str, WithJsonSchema({"type": "string", "pattern": _UUID4})
    ],
) -> ControlledWorkerQueueClaimLeaseAcknowledgementCollectionV1 | JSONResponse:
    correlation_id = request_id_for(request)
    if (
        request.query_params
        or await _has_body(request)
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
        if isinstance(result, tuple):
            if len(result) != 1:
                raise ValueError("unexpected failure response")
            result = tuple(
                _validated_result(item, principal.operator_id, candidate_record_id)
                for item in result
            )
        elif isinstance(
            result, ControlledWorkerQueueClaimLeaseAcknowledgementCollectionV1
        ):
            result = ControlledWorkerQueueClaimLeaseAcknowledgementCollectionV1.model_validate(
                result.model_dump(mode="python")
            )
            if (
                result.operator_id != principal.operator_id
                or result.candidate_record_id != candidate_record_id
            ):
                raise HTTPException(404)
        else:
            raise TypeError("unexpected collection response")
    except HTTPException as error:
        if error.status_code == 404:
            return _json_error("not_found", 404, correlation_id)
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
    "/{candidate_record_id}/controlled-worker-queue-claim-lease-acknowledgements/{admission_id}",
    response_model=ControlledWorkerQueueClaimLeaseAcknowledgementResultV1,
    responses=_ERRORS,
    summary="Read owned queue claim/lease/ack receipt evidence",
)
async def get_controlled_worker_queue_claim_lease_acknowledgement(
    request: Request,
    candidate_record_id: Annotated[
        str, WithJsonSchema({"type": "string", "pattern": _UUID4})
    ],
    admission_id: Annotated[str, WithJsonSchema({"type": "string", "pattern": _UUID5})],
) -> ControlledWorkerQueueClaimLeaseAcknowledgementResultV1 | JSONResponse:
    correlation_id = request_id_for(request)
    if (
        request.query_params
        or await _has_body(request)
        or not _canonical_uuid(candidate_record_id, version=4)
        or not _canonical_uuid(admission_id, version=5)
    ):
        return _json_error("invalid_request", 422, correlation_id)
    try:
        principal = _read_permission(request)
        result = _service(request).get(
            authenticated_operator_id=principal.operator_id,
            permission_verified=True,
            admission_id=admission_id,
            correlation_id=correlation_id,
        )
        result = _validated_result(result, principal.operator_id, candidate_record_id)
        if result.record is not None and result.record.admission_id != admission_id:
            raise HTTPException(404)
    except HTTPException as error:
        if error.status_code == 404:
            return _json_error("not_found", 404, correlation_id)
        return _authentication_error(error, correlation_id)
    except Exception:  # noqa: BLE001 - route failures remain redacted
        return _json_error("internal_error", 503, correlation_id)
    if result.error is not None:
        return _service_response(result)
    return result
