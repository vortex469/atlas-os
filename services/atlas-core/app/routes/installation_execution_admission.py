"""Guarded Core API for v0.36 installation execution admission evidence."""

from __future__ import annotations

import json
import re
from typing import Annotated, Any, Literal

from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, ValidationError, WithJsonSchema

from app.core.exceptions import request_id_for
from app.installation_execution_admission.contract import (
    MAX_CREATE_BYTES,
    MAX_CREATE_NESTING,
    InstallationExecutionAdmissionCreateV1,
    InstallationExecutionAdmissionRedactedErrorV1,
    InstallationExecutionAdmissionResultV1,
)
from app.operator_auth.dependencies import (
    require_operator_mutation,
    require_operator_permission,
)
from app.operator_auth.models import (
    INSTALLATION_EXECUTION_ADMISSION_READ,
    INSTALLATION_EXECUTION_ADMISSION_RECORD,
)

_UUID4 = r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"
_create_permission = require_operator_mutation(
    INSTALLATION_EXECUTION_ADMISSION_RECORD
)
_read_permission = require_operator_permission(INSTALLATION_EXECUTION_ADMISSION_READ)

router = APIRouter(
    prefix="/installation/candidate-records",
    tags=["Installation Execution Admissions"],
)


class _Closed(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class InstallationExecutionAdmissionCollectionV1(_Closed):
    admissions: tuple[InstallationExecutionAdmissionResultV1, ...]
    evidence_only: Literal[True] = True
    execution_start_allowed: Literal[False] = False
    runner_binding_allowed: Literal[False] = False
    execution_authorized: Literal[False] = False
    installation_allowed: Literal[False] = False
    dispatch_allowed: Literal[False] = False
    mutation_allowed: Literal[False] = False
    replay_allowed: Literal[False] = False


_ERRORS = {
    code: {"model": InstallationExecutionAdmissionResultV1}
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


async def _body(request: Request) -> InstallationExecutionAdmissionCreateV1:
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
        return InstallationExecutionAdmissionCreateV1.model_validate(decoded)
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
        or not 1 <= len(value.encode("ascii")) <= 128
        or any(not 0x21 <= ord(character) <= 0x7E for character in value)
    ):
        raise HTTPException(422)
    return value


def _service(request: Request):
    value = getattr(
        request.app.state, "installation_execution_admission_service", None
    )
    if value is None:
        raise HTTPException(503)
    return value


def _error_result(
    error_code: str, correlation_id: str
) -> InstallationExecutionAdmissionResultV1:
    return InstallationExecutionAdmissionResultV1(
        disposition="unavailable" if error_code == "unavailable" else "rejected",
        admission=None,
        status=None,
        audit_evidence=None,
        error=InstallationExecutionAdmissionRedactedErrorV1(
            error_code=error_code,
            blocker_codes=(),
            correlation_id=correlation_id,
        ),
    )


def _json_error(error_code: str, status_code: int, correlation_id: str) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content=jsonable_encoder(_error_result(error_code, correlation_id)),
    )


def _service_response(result: InstallationExecutionAdmissionResultV1) -> JSONResponse:
    assert result.error is not None
    status_code = {
        "unauthenticated": 401,
        "unauthorized": 403,
        "not_found": 404,
        "not_eligible": 409,
        "expired": 409,
        "conflict": 409,
        "quota_exceeded": 409,
        "malformed": 422,
    }.get(result.error.error_code, 503)
    return JSONResponse(status_code=status_code, content=jsonable_encoder(result))


def _authentication_error(error: HTTPException, correlation_id: str) -> JSONResponse:
    if error.status_code == 401:
        return _json_error("unauthenticated", 401, correlation_id)
    if error.status_code == 429:
        return _json_error("quota_exceeded", 429, correlation_id)
    if error.status_code == 503:
        return _json_error("unavailable", 503, correlation_id)
    return _json_error("unauthorized", 403, correlation_id)


@router.post(
    "/{candidate_record_id}/execution-admissions",
    response_model=InstallationExecutionAdmissionResultV1,
    status_code=201,
    responses=_ERRORS,
    summary="Record installation execution admission evidence",
    openapi_extra={
        "parameters": [
            {
                "name": "Idempotency-Key",
                "in": "header",
                "required": True,
                "schema": {"type": "string", "minLength": 1, "maxLength": 128},
            }
        ],
        "requestBody": {
            "required": True,
            "content": {
                "application/json": {
                    "schema": InstallationExecutionAdmissionCreateV1.model_json_schema()
                }
            },
        },
    },
)
async def create_installation_execution_admission(
    request: Request,
    response: Response,
    candidate_record_id: Annotated[
        str, WithJsonSchema({"type": "string", "pattern": _UUID4})
    ],
) -> InstallationExecutionAdmissionResultV1 | JSONResponse:
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
        code = "unavailable" if error.status_code == 503 else "malformed"
        return _json_error(code, error.status_code, correlation_id)
    except Exception:  # noqa: BLE001 - route failures are redacted
        return _json_error("unavailable", 503, correlation_id)
    if result.error is not None:
        return _service_response(result)
    if result.disposition == "exact_duplicate":
        response.status_code = 200
    return result


@router.get(
    "/{candidate_record_id}/execution-admissions",
    response_model=InstallationExecutionAdmissionCollectionV1,
    responses=_ERRORS,
    summary="List owned installation execution admission evidence",
)
async def list_installation_execution_admissions(
    request: Request,
    candidate_record_id: Annotated[
        str, WithJsonSchema({"type": "string", "pattern": _UUID4})
    ],
) -> InstallationExecutionAdmissionCollectionV1 | JSONResponse:
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
    except Exception:  # noqa: BLE001 - route failures are redacted
        return _json_error("unavailable", 503, correlation_id)
    failure = next((item for item in results if item.error is not None), None)
    if failure is not None:
        return _service_response(failure)
    owned = tuple(
        item
        for item in results
        if item.admission is not None
        and item.admission.candidate_record_id == candidate_record_id
    )
    return InstallationExecutionAdmissionCollectionV1(admissions=owned)


@router.get(
    "/{candidate_record_id}/execution-admissions/{admission_id}",
    response_model=InstallationExecutionAdmissionResultV1,
    responses=_ERRORS,
    summary="Read owned installation execution admission evidence",
)
async def get_installation_execution_admission(
    request: Request,
    candidate_record_id: Annotated[
        str, WithJsonSchema({"type": "string", "pattern": _UUID4})
    ],
    admission_id: Annotated[
        str, WithJsonSchema({"type": "string", "pattern": _UUID4})
    ],
) -> InstallationExecutionAdmissionResultV1 | JSONResponse:
    correlation_id = request_id_for(request)
    if (
        request.query_params
        or await request.body()
        or re.fullmatch(_UUID4, candidate_record_id, re.ASCII) is None
        or re.fullmatch(_UUID4, admission_id, re.ASCII) is None
    ):
        return _json_error("malformed", 422, correlation_id)
    try:
        principal = _read_permission(request)
        result = _service(request).get(
            authenticated_operator_id=principal.operator_id,
            permission_verified=True,
            admission_id=admission_id,
            correlation_id=correlation_id,
        )
    except HTTPException as error:
        return _authentication_error(error, correlation_id)
    except Exception:  # noqa: BLE001 - route failures are redacted
        return _json_error("unavailable", 503, correlation_id)
    if result.error is not None:
        return _service_response(result)
    if (
        result.admission is None
        or result.admission.candidate_record_id != candidate_record_id
    ):
        return _json_error("not_found", 404, correlation_id)
    return result


@router.api_route(
    "/{candidate_record_id}/execution-admissions",
    methods=["DELETE", "HEAD", "OPTIONS", "PATCH", "PUT", "TRACE"],
    include_in_schema=False,
)
def reject_installation_execution_admission_collection_method() -> None:
    raise HTTPException(405, headers={"Allow": "GET, POST"})


@router.api_route(
    "/{candidate_record_id}/execution-admissions/{admission_id}",
    methods=["DELETE", "HEAD", "OPTIONS", "PATCH", "POST", "PUT", "TRACE"],
    include_in_schema=False,
)
def reject_installation_execution_admission_item_method() -> None:
    raise HTTPException(405, headers={"Allow": "GET"})
