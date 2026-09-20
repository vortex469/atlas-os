"""Guarded Core API for v0.64 reference-only runtime definitions."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from pydantic import WithJsonSchema

from app.core.exceptions import request_id_for
from app.operator_auth.dependencies import require_operator_mutation, require_operator_permission
from app.operator_auth.models import (
    INSTALLATION_WORKER_ACTIVATION_RUNTIME_DEFINITION_EVALUATE,
    INSTALLATION_WORKER_ACTIVATION_RUNTIME_DEFINITION_READ,
)
from app.worker_activation_runtime_definition.contract import (
    MAX_CREATE_BYTES,
    WorkerActivationRuntimeDefinitionCollectionV1,
    WorkerActivationRuntimeDefinitionCreateV1,
    WorkerActivationRuntimeDefinitionErrorV1,
    WorkerActivationRuntimeDefinitionResultV1,
    _plain,
    fingerprint,
    idempotency_key_fingerprint,
    parse_create_json,
)

_UUID4 = r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"
_UUID5 = r"^[0-9a-f]{8}-[0-9a-f]{4}-5[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"
_create_permission = require_operator_mutation(INSTALLATION_WORKER_ACTIVATION_RUNTIME_DEFINITION_EVALUATE)
_read_permission = require_operator_permission(INSTALLATION_WORKER_ACTIVATION_RUNTIME_DEFINITION_READ)

router = APIRouter(prefix="/installation/candidate-records", tags=["Worker Activation Runtime Definition"])
_ERRORS = {code: {"model": WorkerActivationRuntimeDefinitionErrorV1} for code in (401, 403, 404, 409, 413, 415, 422, 429, 503)}


async def _body(request: Request) -> WorkerActivationRuntimeDefinitionCreateV1:
    if request.headers.getlist("content-type") != ["application/json"]:
        raise HTTPException(415)
    lengths = request.headers.getlist("content-length")
    if len(lengths) > 1 or (lengths and (not lengths[0].isascii() or not lengths[0].isdecimal() or len(lengths[0]) > 10 or int(lengths[0]) > MAX_CREATE_BYTES)):
        raise HTTPException(413)
    if request.headers.getlist("transfer-encoding") and (lengths or request.headers.getlist("transfer-encoding") != ["chunked"]):
        raise HTTPException(422)
    raw = bytearray()
    async for chunk in request.stream():
        if len(raw) + len(chunk) > MAX_CREATE_BYTES:
            raise HTTPException(413)
        raw.extend(chunk)
    if lengths and len(raw) != int(lengths[0]):
        raise HTTPException(422)
    try:
        return parse_create_json(bytes(raw))
    except Exception as error:
        raise HTTPException(422) from error


async def _has_body(request: Request) -> bool:
    lengths = request.headers.getlist("content-length")
    if request.headers.getlist("transfer-encoding") or len(lengths) > 1 or (lengths and (not lengths[0].isascii() or not lengths[0].isdecimal() or len(lengths[0]) > 10 or int(lengths[0]) != 0)):
        return True
    async for chunk in request.stream():
        if chunk:
            return True
    return False


def _idempotency_key(value: str | None) -> str:
    if value is None or not value.isascii() or not 16 <= len(value.encode("ascii")) <= 128 or any(not 0x21 <= ord(char) <= 0x7E for char in value):
        raise HTTPException(422)
    return value


def _canonical_uuid(value: str, version: int) -> bool:
    try:
        parsed = uuid.UUID(value, version=version)
    except ValueError:
        return False
    return str(parsed) == value and parsed.version == version


def _correlation(value: str) -> str:
    return fingerprint("correlation", value if type(value) is str and 0 < len(value) <= 128 else "redacted")


def _error(code: str, status: int, correlation: str) -> JSONResponse:
    return JSONResponse(status_code=status, headers={"Cache-Control": "no-store"}, content=jsonable_encoder(WorkerActivationRuntimeDefinitionErrorV1(error_code=code, correlation_fingerprint=_correlation(correlation))))


def _auth_error(error: HTTPException, correlation: str) -> JSONResponse:
    return _error("unauthenticated" if error.status_code == 401 else "unavailable" if error.status_code == 503 else "forbidden", error.status_code if error.status_code in {401, 503} else 403, correlation)


def _service(request: Request):
    service = getattr(request.app.state, "worker_activation_runtime_definition_service", None)
    if service is None:
        raise HTTPException(503)
    return service


def _validated(result, operator: str, candidate: str):
    if isinstance(result, WorkerActivationRuntimeDefinitionErrorV1):
        return WorkerActivationRuntimeDefinitionErrorV1.model_validate(_plain(result))
    value = WorkerActivationRuntimeDefinitionResultV1.model_validate(_plain(result))
    if value.record.operator_id != operator or value.record.candidate_record_id != candidate:
        raise HTTPException(404)
    return value


def _service_error(result: WorkerActivationRuntimeDefinitionErrorV1) -> JSONResponse:
    status = {"unauthenticated": 401, "forbidden": 403, "definition_not_found": 404, "record_too_large": 413, "invalid_request": 422, "store_corrupt": 503, "unavailable": 503, "installation_capability_unsupported": 503, "append_indeterminate": 503}.get(result.error_code, 409)
    return JSONResponse(status_code=status, headers={"Cache-Control": "no-store"}, content=jsonable_encoder(result))


@router.post("/{candidate_record_id}/worker-activation-runtime-definitions", response_model=WorkerActivationRuntimeDefinitionResultV1, status_code=201, responses=_ERRORS, summary="Record bounded worker activation runtime definition evidence", openapi_extra={"parameters": [{"name": "Idempotency-Key", "in": "header", "required": True, "schema": {"type": "string", "minLength": 16, "maxLength": 128}}], "requestBody": {"required": True, "content": {"application/json": {"schema": WorkerActivationRuntimeDefinitionCreateV1.model_json_schema()}}}})
async def create_worker_activation_runtime_definition(request: Request, response: Response, candidate_record_id: Annotated[str, WithJsonSchema({"type": "string", "pattern": _UUID4})]):
    correlation = request_id_for(request)
    if request.query_params or not _canonical_uuid(candidate_record_id, 4):
        return _error("invalid_request", 422, correlation)
    try:
        if any(len(request.headers.getlist(name)) != 1 for name in ("Origin", "X-Atlas-CSRF-Token")):
            raise HTTPException(403)
        principal = _create_permission(request)
        payload = await _body(request)
        keys = request.headers.getlist("Idempotency-Key")
        if len(keys) != 1:
            raise HTTPException(422)
        key = _idempotency_key(keys[0])
        result = _validated(_service(request).create(payload, authenticated_operator_id=principal.operator_id, permission_verified=True, candidate_record_id=candidate_record_id, idempotency_key=key, correlation_id=correlation), principal.operator_id, candidate_record_id)
        if isinstance(result, WorkerActivationRuntimeDefinitionResultV1):
            record = result.record
            if record.idempotency_key_fingerprint != idempotency_key_fingerprint(principal.operator_id, key) or record.definition_id != payload.definition_id or record.valid_until != payload.valid_until or record.definition.definition_fingerprint != payload.definition_fingerprint:
                raise ValueError("unexpected definition response")
    except HTTPException as error:
        if error.status_code in {404, 413, 415, 422}:
            return _error({404: "definition_not_found", 413: "record_too_large", 415: "invalid_request", 422: "invalid_request"}[error.status_code], error.status_code, correlation)
        return _auth_error(error, correlation)
    except Exception:
        return _error("unavailable", 503, correlation)
    if isinstance(result, WorkerActivationRuntimeDefinitionErrorV1):
        return _service_error(result)
    response.status_code = 201
    return result


@router.get("/{candidate_record_id}/worker-activation-runtime-definitions", response_model=WorkerActivationRuntimeDefinitionCollectionV1, responses=_ERRORS, summary="List owned worker activation runtime definition evidence")
async def list_worker_activation_runtime_definitions(request: Request, candidate_record_id: Annotated[str, WithJsonSchema({"type": "string", "pattern": _UUID4})]):
    correlation = request_id_for(request)
    if request.query_params or not _canonical_uuid(candidate_record_id, 4):
        return _error("invalid_request", 422, correlation)
    try:
        principal = _read_permission(request)
        if await _has_body(request):
            return _error("invalid_request", 422, correlation)
        result = _service(request).list(authenticated_operator_id=principal.operator_id, permission_verified=True, candidate_record_id=candidate_record_id, correlation_id=correlation)
        if isinstance(result, WorkerActivationRuntimeDefinitionErrorV1):
            result = WorkerActivationRuntimeDefinitionErrorV1.model_validate(_plain(result))
        else:
            result = WorkerActivationRuntimeDefinitionCollectionV1.model_validate(_plain(result))
            if result.operator_id != principal.operator_id or result.candidate_record_id != candidate_record_id:
                raise HTTPException(404)
    except HTTPException as error:
        if error.status_code == 404:
            return _error("definition_not_found", 404, correlation)
        return _auth_error(error, correlation)
    except Exception:
        return _error("unavailable", 503, correlation)
    return _service_error(result) if isinstance(result, WorkerActivationRuntimeDefinitionErrorV1) else result


@router.get("/{candidate_record_id}/worker-activation-runtime-definitions/{definition_id}", response_model=WorkerActivationRuntimeDefinitionResultV1, responses=_ERRORS, summary="Read owned worker activation runtime definition evidence")
async def get_worker_activation_runtime_definition(request: Request, candidate_record_id: Annotated[str, WithJsonSchema({"type": "string", "pattern": _UUID4})], definition_id: Annotated[str, WithJsonSchema({"type": "string", "pattern": _UUID5})]):
    correlation = request_id_for(request)
    if request.query_params or not _canonical_uuid(candidate_record_id, 4) or not _canonical_uuid(definition_id, 5):
        return _error("invalid_request", 422, correlation)
    try:
        principal = _read_permission(request)
        if await _has_body(request):
            return _error("invalid_request", 422, correlation)
        result = _validated(_service(request).get(authenticated_operator_id=principal.operator_id, permission_verified=True, candidate_record_id=candidate_record_id, definition_id=definition_id, correlation_id=correlation), principal.operator_id, candidate_record_id)
        if isinstance(result, WorkerActivationRuntimeDefinitionResultV1) and result.record.definition_id != definition_id:
            raise HTTPException(404)
    except HTTPException as error:
        if error.status_code == 404:
            return _error("definition_not_found", 404, correlation)
        return _auth_error(error, correlation)
    except Exception:
        return _error("unavailable", 503, correlation)
    return _service_error(result) if isinstance(result, WorkerActivationRuntimeDefinitionErrorV1) else result
