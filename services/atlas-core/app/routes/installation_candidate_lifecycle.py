"""Guarded API for durable, inert installation candidate records."""

from __future__ import annotations

import json
import re
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Header, HTTPException, Path, Request, Response
from pydantic import BaseModel, ConfigDict, ValidationError

from app.installation_candidate_admission.assembly import (
    InstallationCandidateAdmissionInputMissing,
    InstallationCandidateAdmissionInputUnavailable,
)
from app.installation_candidate_admission.contract import InstallationCandidateRecordV1
from app.installation_candidate_lifecycle.contract import LifecycleState
from app.installation_candidate_lifecycle.store import (
    CandidateRecordIdempotencyConflictError,
    CandidateRecordIdempotencyDeletedError,
    CandidateRecordLimitError,
    CandidateRecordNotFoundError,
    CandidateRecordStoreError,
)
from app.installation_plan.contract import LowerHex64, UtcSecond
from app.installation_targets.contract import CanonicalUuid4
from app.models.contracts import APIError
from app.operator_auth.dependencies import (
    require_operator_mutation,
    require_operator_permission,
)
from app.operator_auth.models import INSTALLATION_DESTINATION_SELECT, OperatorPrincipal

MAX_BODY_BYTES = 8_192
router = APIRouter(prefix="/installation/candidate-records", tags=["Installation Candidate Records"])
_read = require_operator_permission(INSTALLATION_DESTINATION_SELECT)
_mutate = require_operator_mutation(INSTALLATION_DESTINATION_SELECT)
ReadPrincipal = Annotated[OperatorPrincipal, Depends(_read)]
MutationPrincipal = Annotated[OperatorPrincipal, Depends(_mutate)]
IdempotencyKey = Annotated[str, Header(alias="Idempotency-Key", min_length=1, max_length=128)]
_ITEM_ID = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*", re.ASCII)
_UUID4 = r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"


class _Closed(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class PreserveCandidateRecordRequest(_Closed):
    item_id: str
    selection_id: str


class CandidateRecordResponse(_Closed):
    schema: Literal["installation-candidate-record-envelope-v1"]
    candidate_record_id: CanonicalUuid4
    created_at: UtcSecond
    admission_fingerprint: LowerHex64
    candidate_record: InstallationCandidateRecordV1
    envelope_fingerprint: LowerHex64
    lifecycle_state: LifecycleState


class CandidateRecordCollection(_Closed):
    records: tuple[CandidateRecordResponse, ...]


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
        if depth > 4:
            return depth
        if isinstance(current, dict):
            pending.extend((child, depth + 1) for child in current.values())
        elif isinstance(current, list):
            pending.extend((child, depth + 1) for child in current)
    return maximum


async def _body(request: Request) -> PreserveCandidateRecordRequest:
    if request.headers.get("content-type", "").split(";", 1)[0].strip().lower() != "application/json":
        raise HTTPException(415, "Installation candidate record request must use application/json.")
    lengths = request.headers.getlist("content-length")
    if len(lengths) > 1 or (lengths and (not lengths[0].isascii() or not lengths[0].isdecimal() or int(lengths[0]) > MAX_BODY_BYTES)):
        raise HTTPException(413, "Installation candidate record request is too large.")
    raw = await request.body()
    if len(raw) > MAX_BODY_BYTES:
        raise HTTPException(413, "Installation candidate record request is too large.")
    try:
        decoded = json.loads(raw, object_pairs_hook=_pairs)
        if _depth(decoded) > 4:
            raise ValueError("nesting")
        value = PreserveCandidateRecordRequest.model_validate(decoded)
        if len(value.item_id.encode("ascii")) > 64 or _ITEM_ID.fullmatch(value.item_id) is None:
            raise ValueError("item")
        if re.fullmatch(_UUID4, value.selection_id, re.ASCII) is None:
            raise ValueError("selection")
        return value
    except (UnicodeDecodeError, json.JSONDecodeError, ValidationError, ValueError, RecursionError, UnicodeEncodeError) as error:
        raise HTTPException(422, "Installation candidate record request is invalid.") from error


def _key(value: str) -> str:
    if not value.isascii() or not 1 <= len(value.encode("ascii")) <= 128 or any(not 0x21 <= ord(char) <= 0x7e for char in value):
        raise HTTPException(422, "Installation candidate record request is invalid.")
    return value


def _project(service: Any, owner_id: str, envelope: Any) -> CandidateRecordResponse:
    return CandidateRecordResponse(
        **envelope.model_dump(exclude={"owner_id"}),
        lifecycle_state=service.state(owner_id=owner_id, candidate_record_id=envelope.candidate_record_id),
    )


_ERRORS = {code: {"model": APIError} for code in (401, 403, 404, 409, 413, 415, 422, 429, 503)}


@router.post("", response_model=CandidateRecordResponse, responses=_ERRORS)
async def preserve_candidate_record(request: Request, principal: MutationPrincipal, idempotency_key: IdempotencyKey) -> CandidateRecordResponse:
    payload = await _body(request)
    key = _key(idempotency_key)
    service = request.app.state.installation_candidate_lifecycle_service
    try:
        envelope = await service.preserve(owner_id=principal.operator_id, item_id=payload.item_id, selection_id=payload.selection_id, idempotency_key=key)
        return _project(service, principal.operator_id, envelope)
    except InstallationCandidateAdmissionInputMissing as error:
        raise HTTPException(404, "Installation candidate admission input was not found.") from error
    except (CandidateRecordIdempotencyConflictError, CandidateRecordIdempotencyDeletedError, CandidateRecordLimitError, ValueError) as error:
        raise HTTPException(409, "Installation candidate record request conflicts with current state.") from error
    except (InstallationCandidateAdmissionInputUnavailable, CandidateRecordStoreError) as error:
        raise HTTPException(503, "Installation candidate record dependency is unavailable.") from error
    except Exception as error:
        raise HTTPException(503, "Installation candidate record dependency is unavailable.") from error


@router.get("", response_model=CandidateRecordCollection, responses=_ERRORS)
def list_candidate_records(request: Request, principal: ReadPrincipal) -> CandidateRecordCollection:
    service = request.app.state.installation_candidate_lifecycle_service
    try:
        return CandidateRecordCollection(records=tuple(_project(service, principal.operator_id, item) for item in service.list_for_operator(owner_id=principal.operator_id)))
    except Exception as error:
        raise HTTPException(503, "Installation candidate record dependency is unavailable.") from error


@router.get("/{candidate_record_id}", response_model=CandidateRecordResponse, responses=_ERRORS)
def get_candidate_record(request: Request, principal: ReadPrincipal, candidate_record_id: Annotated[str, Path(pattern=_UUID4)]) -> CandidateRecordResponse:
    service = request.app.state.installation_candidate_lifecycle_service
    try:
        return _project(service, principal.operator_id, service.get(owner_id=principal.operator_id, candidate_record_id=candidate_record_id))
    except CandidateRecordNotFoundError as error:
        raise HTTPException(404, "Installation candidate record was not found.") from error
    except Exception as error:
        raise HTTPException(503, "Installation candidate record dependency is unavailable.") from error


@router.delete("/{candidate_record_id}", status_code=204, response_class=Response, responses=_ERRORS)
def delete_candidate_record(request: Request, principal: MutationPrincipal, candidate_record_id: Annotated[str, Path(pattern=_UUID4)]) -> Response:
    try:
        request.app.state.installation_candidate_lifecycle_service.delete(owner_id=principal.operator_id, candidate_record_id=candidate_record_id)
        return Response(status_code=204)
    except CandidateRecordNotFoundError as error:
        raise HTTPException(404, "Installation candidate record was not found.") from error
    except Exception as error:
        raise HTTPException(503, "Installation candidate record dependency is unavailable.") from error


@router.api_route("", methods=["DELETE", "HEAD", "OPTIONS", "PATCH", "PUT", "TRACE"], include_in_schema=False)
def reject_collection_method() -> None:
    raise HTTPException(405, headers={"Allow": "GET, POST"})


@router.api_route("/{candidate_record_id}", methods=["HEAD", "OPTIONS", "PATCH", "POST", "PUT", "TRACE"], include_in_schema=False)
def reject_item_method() -> None:
    raise HTTPException(405, headers={"Allow": "DELETE, GET"})
