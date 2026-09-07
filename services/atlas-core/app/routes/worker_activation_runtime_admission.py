"""Guarded Core API for v0.54 worker activation runtime admission evidence."""

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
    INSTALLATION_WORKER_ACTIVATION_RUNTIME_ADMISSION_EVALUATE,
    INSTALLATION_WORKER_ACTIVATION_RUNTIME_ADMISSION_READ,
)
from app.worker_activation_runtime_admission.contract import (
    MAX_CREATE_BYTES,
    WorkerActivationRuntimeAdmissionCollectionV1,
    WorkerActivationRuntimeAdmissionCreateV1,
    WorkerActivationRuntimeAdmissionRedactedErrorV1,
    WorkerActivationRuntimeAdmissionResultV1,
    _plain,
    fingerprint,
    idempotency_key_fingerprint,
    parse_create_json,
)

_UUID4 = r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"
_UUID5 = r"^[0-9a-f]{8}-[0-9a-f]{4}-5[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"
_create_permission = require_operator_mutation(
    INSTALLATION_WORKER_ACTIVATION_RUNTIME_ADMISSION_EVALUATE
)
_read_permission = require_operator_permission(
    INSTALLATION_WORKER_ACTIVATION_RUNTIME_ADMISSION_READ
)

router = APIRouter(
    prefix="/installation/candidate-records",
    tags=["Worker Activation Runtime Admission"],
)

_ERRORS = {
    code: {"model": WorkerActivationRuntimeAdmissionRedactedErrorV1}
    for code in (401, 403, 404, 409, 413, 415, 422, 429, 503)
}


async def _body(
    request: Request,
) -> WorkerActivationRuntimeAdmissionCreateV1:
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
        "worker_activation_runtime_admission_service",
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
    safe = value if type(value) is str and 0 < len(value) <= 128 else "redacted"
    return fingerprint("correlation", safe)


def _json_error(error_code: str, status_code: int, correlation_id: str) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content=jsonable_encoder(
            WorkerActivationRuntimeAdmissionRedactedErrorV1(
                error_code=error_code,
                correlation_fingerprint=_correlation(correlation_id),
            )
        ),
    )


def _validated_result(result, operator_id: str, candidate_record_id: str):
    if isinstance(result, WorkerActivationRuntimeAdmissionRedactedErrorV1):
        return WorkerActivationRuntimeAdmissionRedactedErrorV1.model_validate(
            _plain(result)
        )
    result = WorkerActivationRuntimeAdmissionResultV1.model_validate(_plain(result))
    if (
        result.record.operator_id != operator_id
        or result.record.candidate_record_id != candidate_record_id
    ):
        raise HTTPException(404)
    return result


def _service_response(
    result: WorkerActivationRuntimeAdmissionRedactedErrorV1,
) -> JSONResponse:
    code = result.error_code
    status_code = {
        "unauthenticated": 401,
        "forbidden": 403,
        "evidence_not_found": 404,
        "record_too_large": 413,
        "invalid_request": 422,
        "store_corrupt": 503,
        "unavailable": 503,
        "append_indeterminate": 503,
    }.get(code, 409)
    return JSONResponse(status_code=status_code, content=jsonable_encoder(result))


def _authentication_error(error: HTTPException, correlation_id: str) -> JSONResponse:
    if error.status_code == 401:
        return _json_error("unauthenticated", 401, correlation_id)
    if error.status_code == 429:
        return _json_error("forbidden", 429, correlation_id)
    if error.status_code == 503:
        return _json_error("unavailable", 503, correlation_id)
    return _json_error("forbidden", 403, correlation_id)


@router.post(
    "/{candidate_record_id}/worker-activation-runtime-admissions",
    response_model=WorkerActivationRuntimeAdmissionResultV1,
    status_code=201,
    responses=_ERRORS,
    summary="Record bounded worker activation runtime admission evidence",
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
                        WorkerActivationRuntimeAdmissionCreateV1.model_json_schema()
                    )
                }
            },
        },
    },
)
async def create_worker_activation_runtime_admission(
    request: Request,
    response: Response,
    candidate_record_id: Annotated[
        str, WithJsonSchema({"type": "string", "pattern": _UUID4})
    ],
) -> WorkerActivationRuntimeAdmissionResultV1 | JSONResponse:
    correlation_id = request_id_for(request)
    if request.query_params or not _canonical_uuid(candidate_record_id, version=4):
        return _json_error("invalid_request", 422, correlation_id)
    try:
        if any(
            len(request.headers.getlist(name)) != 1
            for name in ("Origin", "X-Atlas-CSRF-Token")
        ):
            raise HTTPException(403)
        principal = _create_permission(request)
    except HTTPException as error:
        return _authentication_error(error, correlation_id)
    except Exception:  # noqa: BLE001 - authentication failures remain redacted
        return _json_error("unavailable", 503, correlation_id)
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
        if isinstance(result, WorkerActivationRuntimeAdmissionResultV1):
            record = result.record
            receipt = record.worker_activation_runtime_prerequisite
            status = record.worker_activation_runtime_prerequisite_status
            if (
                record.idempotency_key_fingerprint
                != idempotency_key_fingerprint(principal.operator_id, key)
                or record.prerequisite_id != payload.prerequisite_id
                or record.valid_until != payload.valid_until
                or receipt.prerequisite_record_fingerprint
                != payload.prerequisite_record_fingerprint
                or status.status_fingerprint != payload.status_fingerprint
            ):
                raise ValueError("unexpected admission response")

    except HTTPException as error:
        if error.status_code not in {404, 413, 415, 422, 503}:
            return _json_error("unavailable", 503, correlation_id)
        code = {
            404: "evidence_not_found",
            413: "record_too_large",
            503: "unavailable",
        }.get(error.status_code, "invalid_request")
        return _json_error(code, error.status_code, correlation_id)
    except Exception:  # noqa: BLE001 - route failures remain redacted
        return _json_error("unavailable", 503, correlation_id)
    if isinstance(result, WorkerActivationRuntimeAdmissionRedactedErrorV1):
        return _service_response(result)
    response.status_code = 201
    return result


@router.get(
    "/{candidate_record_id}/worker-activation-runtime-admissions",
    response_model=WorkerActivationRuntimeAdmissionCollectionV1,
    responses=_ERRORS,
    summary="List owned worker activation runtime admission evidence",
)
async def list_worker_activation_runtime_admissions(
    request: Request,
    candidate_record_id: Annotated[
        str, WithJsonSchema({"type": "string", "pattern": _UUID4})
    ],
) -> WorkerActivationRuntimeAdmissionCollectionV1 | JSONResponse:
    correlation_id = request_id_for(request)
    if request.query_params or not _canonical_uuid(candidate_record_id, version=4):
        return _json_error("invalid_request", 422, correlation_id)
    try:
        principal = _read_permission(request)
        if await _has_body(request):
            return _json_error("invalid_request", 422, correlation_id)
        result = _service(request).list(
            authenticated_operator_id=principal.operator_id,
            permission_verified=True,
            candidate_record_id=candidate_record_id,
            correlation_id=correlation_id,
        )
        if isinstance(result, WorkerActivationRuntimeAdmissionRedactedErrorV1):
            result = WorkerActivationRuntimeAdmissionRedactedErrorV1.model_validate(
                _plain(result)
            )
        else:
            result = WorkerActivationRuntimeAdmissionCollectionV1.model_validate(
                _plain(result)
            )
            if (
                result.operator_id != principal.operator_id
                or result.candidate_record_id != candidate_record_id
            ):
                raise HTTPException(404)
    except HTTPException as error:
        if error.status_code == 404:
            return _json_error("evidence_not_found", 404, correlation_id)
        return _authentication_error(error, correlation_id)
    except Exception:  # noqa: BLE001 - route failures remain redacted
        return _json_error("unavailable", 503, correlation_id)
    if isinstance(result, WorkerActivationRuntimeAdmissionRedactedErrorV1):
        return _service_response(result)
    return result


@router.get(
    "/{candidate_record_id}/worker-activation-runtime-admissions/{runtime_admission_id}",
    response_model=WorkerActivationRuntimeAdmissionResultV1,
    responses=_ERRORS,
    summary="Read owned worker activation runtime admission evidence",
)
async def get_worker_activation_runtime_admission(
    request: Request,
    candidate_record_id: Annotated[
        str, WithJsonSchema({"type": "string", "pattern": _UUID4})
    ],
    runtime_admission_id: Annotated[
        str, WithJsonSchema({"type": "string", "pattern": _UUID5})
    ],
) -> WorkerActivationRuntimeAdmissionResultV1 | JSONResponse:
    correlation_id = request_id_for(request)
    if (
        request.query_params
        or not _canonical_uuid(candidate_record_id, version=4)
        or not _canonical_uuid(runtime_admission_id, version=5)
    ):
        return _json_error("invalid_request", 422, correlation_id)
    try:
        principal = _read_permission(request)
        if await _has_body(request):
            return _json_error("invalid_request", 422, correlation_id)
        result = _service(request).get(
            authenticated_operator_id=principal.operator_id,
            permission_verified=True,
            candidate_record_id=candidate_record_id,
            runtime_admission_id=runtime_admission_id,
            correlation_id=correlation_id,
        )
        result = _validated_result(result, principal.operator_id, candidate_record_id)
        if (
            isinstance(result, WorkerActivationRuntimeAdmissionResultV1)
            and result.record.runtime_admission_id != runtime_admission_id
        ):
            raise HTTPException(404)
    except HTTPException as error:
        if error.status_code == 404:
            return _json_error("evidence_not_found", 404, correlation_id)
        return _authentication_error(error, correlation_id)
    except Exception:  # noqa: BLE001 - route failures remain redacted
        return _json_error("unavailable", 503, correlation_id)
    if isinstance(result, WorkerActivationRuntimeAdmissionRedactedErrorV1):
        return _service_response(result)
    return result
