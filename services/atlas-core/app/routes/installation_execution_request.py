"""Guarded API for inert installation execution request records."""

from __future__ import annotations

import json
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Header, HTTPException, Path, Request
from pydantic import BaseModel, ConfigDict, ValidationError

from app.installation_execution_request.contract import (
    MAX_CREATE_BYTES,
    InstallationExecutionRequestCreateV1,
    InstallationExecutionRequestV1,
)
from app.installation_execution_request.store import (
    ExecutionRequestEvidenceRejectedError,
    ExecutionRequestMalformedError,
    ExecutionRequestNotCurrentError,
    ExecutionRequestNotFoundError,
    ExecutionRequestOwnershipError,
    ExecutionRequestProofMismatchError,
    ExecutionRequestQuotaError,
    ExecutionRequestRecordLimitError,
    ExecutionRequestReplayConflictError,
    InstallationExecutionRequestStoreError,
)
from app.models.contracts import APIError
from app.operator_auth.dependencies import (
    require_operator_mutation,
    require_operator_permission,
)
from app.operator_auth.models import INSTALLATION_DESTINATION_SELECT, OperatorPrincipal

router = APIRouter(
    prefix="/installation/execution-requests",
    tags=["Installation Execution Requests"],
)
_read = require_operator_permission(INSTALLATION_DESTINATION_SELECT)
_mutate = require_operator_mutation(INSTALLATION_DESTINATION_SELECT)
ReadPrincipal = Annotated[OperatorPrincipal, Depends(_read)]
MutationPrincipal = Annotated[OperatorPrincipal, Depends(_mutate)]
IdempotencyKey = Annotated[
    str, Header(alias="Idempotency-Key", min_length=1, max_length=128)
]
_UUID4 = r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"
_MAX_JSON_DEPTH = 16


class _Closed(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class InstallationExecutionRequestResponse(InstallationExecutionRequestV1):
    lifecycle_state: Literal["recorded", "expired"]
    evidence_provenance: Literal["operator_submitted_agent_validation_evidence"] = (
        "operator_submitted_agent_validation_evidence"
    )


class InstallationExecutionRequestCollection(_Closed):
    execution_requests: tuple[InstallationExecutionRequestResponse, ...]


def _pairs(values: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in values:
        if key in result:
            raise ValueError("duplicate key")
        result[key] = value
    return result


def _depth(value: Any) -> int:
    pending = [(value, 1)]
    maximum = 1
    while pending:
        current, depth = pending.pop()
        maximum = max(maximum, depth)
        if depth > _MAX_JSON_DEPTH:
            return depth
        if isinstance(current, dict):
            pending.extend((child, depth + 1) for child in current.values())
        elif isinstance(current, list):
            pending.extend((child, depth + 1) for child in current)
    return maximum


async def _body(request: Request) -> InstallationExecutionRequestCreateV1:
    content_type = request.headers.get("content-type", "").split(";", 1)[0]
    if content_type.strip().lower() != "application/json":
        raise HTTPException(
            415, "Installation execution request must use application/json."
        )
    lengths = request.headers.getlist("content-length")
    if len(lengths) > 1 or (
        lengths
        and (
            not lengths[0].isascii()
            or not lengths[0].isdecimal()
            or int(lengths[0]) > MAX_CREATE_BYTES
        )
    ):
        raise HTTPException(413, "Installation execution request is too large.")
    raw = await request.body()
    if len(raw) > MAX_CREATE_BYTES:
        raise HTTPException(413, "Installation execution request is too large.")
    try:
        decoded = json.loads(raw, object_pairs_hook=_pairs)
        if not isinstance(decoded, dict) or _depth(decoded) > _MAX_JSON_DEPTH:
            raise ValueError("invalid JSON shape")
        return InstallationExecutionRequestCreateV1.model_validate(decoded)
    except (
        UnicodeDecodeError,
        json.JSONDecodeError,
        ValidationError,
        ValueError,
        RecursionError,
    ) as error:
        raise HTTPException(422, "Installation execution request is invalid.") from error


def _key(value: str) -> str:
    if (
        not value.isascii()
        or not 1 <= len(value.encode("ascii")) <= 128
        or any(not 0x21 <= ord(character) <= 0x7E for character in value)
    ):
        raise HTTPException(422, "Installation execution request is invalid.")
    return value


def _project(
    service: Any, operator_id: str, value: InstallationExecutionRequestV1
) -> InstallationExecutionRequestResponse:
    return InstallationExecutionRequestResponse(
        **value.model_dump(mode="python"),
        lifecycle_state=service.state(
            operator_id=operator_id,
            execution_request_id=value.execution_request_id,
        ),
    )


def _closed_error(error: InstallationExecutionRequestStoreError) -> HTTPException:
    if isinstance(error, (ExecutionRequestNotFoundError, ExecutionRequestOwnershipError)):
        return HTTPException(404, "Installation execution request was not found.")
    if isinstance(error, ExecutionRequestMalformedError):
        return HTTPException(422, "Installation execution request is invalid.")
    if isinstance(
        error,
        (
            ExecutionRequestNotCurrentError,
            ExecutionRequestProofMismatchError,
            ExecutionRequestEvidenceRejectedError,
            ExecutionRequestReplayConflictError,
            ExecutionRequestQuotaError,
            ExecutionRequestRecordLimitError,
        ),
    ):
        return HTTPException(
            409, "Installation execution request conflicts with current state."
        )
    return HTTPException(503, "Installation execution request dependency is unavailable.")


_ERRORS = {
    code: {"model": APIError}
    for code in (401, 403, 404, 409, 413, 415, 422, 429, 503)
}


@router.post("", response_model=InstallationExecutionRequestResponse, responses=_ERRORS)
async def record_installation_execution_request(
    request: Request,
    principal: MutationPrincipal,
    idempotency_key: IdempotencyKey,
) -> InstallationExecutionRequestResponse:
    payload = await _body(request)
    key = _key(idempotency_key)
    service = request.app.state.installation_execution_request_service
    try:
        value = service.record(
            operator_id=principal.operator_id,
            idempotency_key=key,
            create=payload,
        )
        return _project(service, principal.operator_id, value)
    except InstallationExecutionRequestStoreError as error:
        raise _closed_error(error) from error
    except Exception as error:
        raise HTTPException(
            503, "Installation execution request dependency is unavailable."
        ) from error


@router.get("", response_model=InstallationExecutionRequestCollection, responses=_ERRORS)
def list_installation_execution_requests(
    request: Request, principal: ReadPrincipal
) -> InstallationExecutionRequestCollection:
    service = request.app.state.installation_execution_request_service
    try:
        values = service.list_for_operator(operator_id=principal.operator_id)
        return InstallationExecutionRequestCollection(
            execution_requests=tuple(
                _project(service, principal.operator_id, value) for value in values
            )
        )
    except InstallationExecutionRequestStoreError as error:
        raise _closed_error(error) from error
    except Exception as error:
        raise HTTPException(
            503, "Installation execution request dependency is unavailable."
        ) from error


@router.get(
    "/{execution_request_id}",
    response_model=InstallationExecutionRequestResponse,
    responses=_ERRORS,
)
def get_installation_execution_request(
    request: Request,
    principal: ReadPrincipal,
    execution_request_id: Annotated[str, Path(pattern=_UUID4)],
) -> InstallationExecutionRequestResponse:
    service = request.app.state.installation_execution_request_service
    try:
        value = service.get(
            operator_id=principal.operator_id,
            execution_request_id=execution_request_id,
        )
        return _project(service, principal.operator_id, value)
    except InstallationExecutionRequestStoreError as error:
        raise _closed_error(error) from error
    except Exception as error:
        raise HTTPException(
            503, "Installation execution request dependency is unavailable."
        ) from error


@router.api_route(
    "",
    methods=["DELETE", "HEAD", "OPTIONS", "PATCH", "PUT", "TRACE"],
    include_in_schema=False,
)
def reject_collection_method() -> None:
    raise HTTPException(405, headers={"Allow": "GET, POST"})


@router.api_route(
    "/{execution_request_id}",
    methods=["DELETE", "HEAD", "OPTIONS", "PATCH", "POST", "PUT", "TRACE"],
    include_in_schema=False,
)
def reject_item_method() -> None:
    raise HTTPException(405, headers={"Allow": "GET"})
