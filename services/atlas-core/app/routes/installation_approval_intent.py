"""Guarded API for immutable, non-authorizing installation approval evidence."""

from __future__ import annotations

import json
import re
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, HTTPException, Path, Request
from pydantic import BaseModel, ConfigDict, ValidationError

from app.installation_approval_intent.contract import InstallationApprovalIntentV1
from app.installation_approval_intent.store import (
    ApprovalIntentCandidateUnavailableError,
    ApprovalIntentIdempotencyConflictError,
    ApprovalIntentLimitError,
    ApprovalIntentNotFoundError,
    ApprovalIntentStoreError,
)
from app.models.contracts import APIError
from app.operator_auth.dependencies import (
    require_operator_mutation,
    require_operator_permission,
)
from app.operator_auth.models import INSTALLATION_DESTINATION_SELECT, OperatorPrincipal

MAX_BODY_BYTES = 8_192
router = APIRouter(
    prefix="/installation/candidate-approval-intents",
    tags=["Installation Approval Intents"],
)
_read = require_operator_permission(INSTALLATION_DESTINATION_SELECT)
_mutate = require_operator_mutation(INSTALLATION_DESTINATION_SELECT)
ReadPrincipal = Annotated[OperatorPrincipal, Depends(_read)]
MutationPrincipal = Annotated[OperatorPrincipal, Depends(_mutate)]
IdempotencyKey = Annotated[
    str, Header(alias="Idempotency-Key", min_length=1, max_length=128)
]
_UUID4 = r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"


class _Closed(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class RecordApprovalIntentRequest(_Closed):
    candidate_record_id: str


class ApprovalIntentCollection(_Closed):
    approval_intents: tuple[InstallationApprovalIntentV1, ...]


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


async def _body(request: Request) -> RecordApprovalIntentRequest:
    content_type = request.headers.get("content-type", "").split(";", 1)[0]
    if content_type.strip().lower() != "application/json":
        raise HTTPException(415, "Installation approval intent request must use application/json.")
    lengths = request.headers.getlist("content-length")
    if len(lengths) > 1 or (
        lengths
        and (
            not lengths[0].isascii()
            or not lengths[0].isdecimal()
            or int(lengths[0]) > MAX_BODY_BYTES
        )
    ):
        raise HTTPException(413, "Installation approval intent request is too large.")
    raw = await request.body()
    if len(raw) > MAX_BODY_BYTES:
        raise HTTPException(413, "Installation approval intent request is too large.")
    try:
        decoded = json.loads(raw, object_pairs_hook=_pairs)
        if _depth(decoded) > 4:
            raise ValueError("nesting")
        value = RecordApprovalIntentRequest.model_validate(decoded)
        if re.fullmatch(_UUID4, value.candidate_record_id, re.ASCII) is None:
            raise ValueError("candidate record id")
        return value
    except (
        UnicodeDecodeError,
        json.JSONDecodeError,
        ValidationError,
        ValueError,
        RecursionError,
    ) as error:
        raise HTTPException(422, "Installation approval intent request is invalid.") from error


def _key(value: str) -> str:
    if (
        not value.isascii()
        or not 1 <= len(value.encode("ascii")) <= 128
        or any(not 0x21 <= ord(character) <= 0x7E for character in value)
    ):
        raise HTTPException(422, "Installation approval intent request is invalid.")
    return value


_ERRORS = {
    code: {"model": APIError}
    for code in (401, 403, 404, 409, 413, 415, 422, 429, 503)
}


@router.post("", response_model=InstallationApprovalIntentV1, responses=_ERRORS)
async def record_approval_intent(
    request: Request,
    principal: MutationPrincipal,
    idempotency_key: IdempotencyKey,
) -> InstallationApprovalIntentV1:
    payload = await _body(request)
    key = _key(idempotency_key)
    try:
        return request.app.state.installation_approval_intent_service.record(
            operator_id=principal.operator_id,
            candidate_record_id=payload.candidate_record_id,
            idempotency_key=key,
        )
    except ApprovalIntentCandidateUnavailableError as error:
        raise HTTPException(404, "Installation candidate record was not found.") from error
    except (ApprovalIntentIdempotencyConflictError, ApprovalIntentLimitError, ValueError) as error:
        raise HTTPException(409, "Installation approval intent request conflicts with current state.") from error
    except ApprovalIntentStoreError as error:
        raise HTTPException(503, "Installation approval intent dependency is unavailable.") from error
    except Exception as error:
        raise HTTPException(503, "Installation approval intent dependency is unavailable.") from error


@router.get("", response_model=ApprovalIntentCollection, responses=_ERRORS)
def list_approval_intents(
    request: Request, principal: ReadPrincipal
) -> ApprovalIntentCollection:
    try:
        values = request.app.state.installation_approval_intent_service.list_for_operator(
            operator_id=principal.operator_id
        )
        return ApprovalIntentCollection(approval_intents=values)
    except Exception as error:
        raise HTTPException(503, "Installation approval intent dependency is unavailable.") from error


@router.get("/{approval_intent_id}", response_model=InstallationApprovalIntentV1, responses=_ERRORS)
def get_approval_intent(
    request: Request,
    principal: ReadPrincipal,
    approval_intent_id: Annotated[str, Path(pattern=_UUID4)],
) -> InstallationApprovalIntentV1:
    try:
        return request.app.state.installation_approval_intent_service.get(
            operator_id=principal.operator_id,
            approval_intent_id=approval_intent_id,
        )
    except ApprovalIntentNotFoundError as error:
        raise HTTPException(404, "Installation approval intent was not found.") from error
    except Exception as error:
        raise HTTPException(503, "Installation approval intent dependency is unavailable.") from error


@router.api_route(
    "", methods=["DELETE", "HEAD", "OPTIONS", "PATCH", "PUT", "TRACE"], include_in_schema=False
)
def reject_collection_method() -> None:
    raise HTTPException(405, headers={"Allow": "GET, POST"})


@router.api_route(
    "/{approval_intent_id}",
    methods=["DELETE", "HEAD", "OPTIONS", "PATCH", "POST", "PUT", "TRACE"],
    include_in_schema=False,
)
def reject_item_method() -> None:
    raise HTTPException(405, headers={"Allow": "GET"})
