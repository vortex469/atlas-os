"""Guarded transport for prospective installation destination assessment."""

from __future__ import annotations

import json
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, HTTPException, Path, Request
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.installation_assessment.cache import AssessmentIdempotencyConflictError
from app.installation_assessment.contract import InstallationAdmissionAssessmentV1
from app.installation_assessment.service import assess_installation_request
from app.installation_plan.assembly import (
    InstallationPlanClockUnavailable,
    InstallationPlanContractFailure,
    InstallationPlanItemNotFound,
    InstallationPlanSourceUnavailable,
)
from app.installation_plan.contract import Id64, LowerHex64
from app.installation_targets.contract import (
    InstallationDestinationSelectionV1,
    ProspectiveInstallationDestinationV1,
)
from app.installation_targets.resolver import DestinationResolutionError
from app.installation_targets.service import (
    SelectionClockError,
    SelectionDestinationStaleError,
)
from app.installation_targets.store import (
    SelectionActiveLimitError,
    SelectionIdempotencyConflictError,
    SelectionNotFoundError,
    SelectionStoreError,
)
from app.models.contracts import APIError
from app.operator_auth.dependencies import (
    require_operator_mutation,
    require_operator_permission,
)
from app.operator_auth.models import (
    INSTALLATION_DESTINATION_SELECT,
    OperatorPrincipal,
)

MAX_INSTALLATION_BODY_BYTES = 8_192
router = APIRouter(prefix="/installation", tags=["Installation Destinations"])

_read = require_operator_permission(INSTALLATION_DESTINATION_SELECT)
_mutate = require_operator_mutation(INSTALLATION_DESTINATION_SELECT)
ReadPrincipal = Annotated[OperatorPrincipal, Depends(_read)]
MutationPrincipal = Annotated[OperatorPrincipal, Depends(_mutate)]
IdempotencyKey = Annotated[
    str, Header(alias="Idempotency-Key", min_length=16, max_length=128)
]


class _RequestModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class DestinationSelectionRequest(_RequestModel):
    resource_id: str = Field(pattern=r"^[1-9][0-9]*$", max_length=20)
    enumeration_token: str = Field(pattern=r"^[0-9a-f]{64}$")


class AdmissionAssessmentRequest(_RequestModel):
    item_id: Id64
    catalog_entry_id: Id64
    plan_fingerprint: LowerHex64
    selection_id: str = Field(
        pattern=r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"
    )


class DestinationCollection(_RequestModel):
    destinations: tuple[ProspectiveInstallationDestinationV1, ...]


def _reject_duplicate_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def _depth(value: Any) -> int:
    maximum = 1
    pending: list[tuple[Any, int]] = [(value, 1)]
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


async def _read_body(request: Request, model: type[_RequestModel]) -> _RequestModel:
    if (
        request.headers.get("content-type", "").split(";", 1)[0].strip().lower()
        != "application/json"
    ):
        raise HTTPException(415, "Installation request must use application/json.")
    lengths = request.headers.getlist("content-length")
    if len(lengths) > 1:
        raise HTTPException(413, "Installation request is too large.")
    if lengths:
        try:
            if (
                not lengths[0].isascii()
                or not lengths[0].isdecimal()
                or int(lengths[0]) > MAX_INSTALLATION_BODY_BYTES
            ):
                raise ValueError
        except ValueError as error:
            raise HTTPException(413, "Installation request is too large.") from error
    body = await request.body()
    if len(body) > MAX_INSTALLATION_BODY_BYTES:
        raise HTTPException(413, "Installation request is too large.")
    try:
        decoded = json.loads(body, object_pairs_hook=_reject_duplicate_pairs)
        if _depth(decoded) > 4:
            raise ValueError("JSON nesting exceeds limit")
        return model.model_validate(decoded)
    except (
        UnicodeDecodeError,
        json.JSONDecodeError,
        ValidationError,
        ValueError,
        RecursionError,
    ) as error:
        raise HTTPException(422, "Installation request is invalid.") from error


def _validate_key(value: str) -> str:
    if (
        not value.isascii()
        or not 16 <= len(value.encode("ascii")) <= 128
        or any(not 0x21 <= ord(character) <= 0x7E for character in value)
    ):
        raise HTTPException(422, "Installation request is invalid.")
    return value


def _unavailable(error: Exception) -> HTTPException:
    return HTTPException(503, "Installation dependency is unavailable.")


_ERRORS = {
    401: {"model": APIError},
    403: {"model": APIError},
    404: {"model": APIError},
    409: {"model": APIError},
    413: {"model": APIError},
    415: {"model": APIError},
    422: {"model": APIError},
    429: {"model": APIError},
    503: {"model": APIError},
}


@router.get("/destinations", response_model=DestinationCollection, responses=_ERRORS)
async def list_destinations(
    request: Request, principal: ReadPrincipal
) -> DestinationCollection:
    del principal
    try:
        values = await request.app.state.installation_destination_enumerator()
        return DestinationCollection(destinations=tuple(values))
    except Exception as error:
        raise _unavailable(error) from error


@router.post(
    "/destination-selections",
    response_model=InstallationDestinationSelectionV1,
    responses=_ERRORS,
)
async def create_destination_selection(
    request: Request, principal: MutationPrincipal, idempotency_key: IdempotencyKey
) -> InstallationDestinationSelectionV1:
    payload = await _read_body(request, DestinationSelectionRequest)
    key = _validate_key(idempotency_key)
    service = request.app.state.installation_destination_selection_service
    try:
        current = await service.enumerate_one(payload.resource_id)
        if current.enumeration_token != payload.enumeration_token:
            raise SelectionDestinationStaleError("stale enumeration")
        return await service.create(
            selected_by=principal.operator_id, destination=current, idempotency_key=key
        )
    except (
        SelectionDestinationStaleError,
        SelectionIdempotencyConflictError,
        SelectionActiveLimitError,
    ) as error:
        raise HTTPException(
            409, "Installation selection request conflicts with current state."
        ) from error
    except (
        DestinationResolutionError,
        SelectionClockError,
        SelectionStoreError,
    ) as error:
        raise _unavailable(error) from error


@router.get(
    "/destination-selections/{selection_id}",
    response_model=InstallationDestinationSelectionV1,
    responses=_ERRORS,
)
async def read_destination_selection(
    request: Request,
    principal: ReadPrincipal,
    selection_id: Annotated[
        str,
        Path(
            pattern=r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"
        ),
    ],
) -> InstallationDestinationSelectionV1:
    try:
        return await request.app.state.installation_destination_selection_service.get(
            selection_id=selection_id, selected_by=principal.operator_id
        )
    except SelectionNotFoundError as error:
        raise HTTPException(404, "Installation selection was not found.") from error
    except (
        DestinationResolutionError,
        SelectionClockError,
        SelectionStoreError,
    ) as error:
        raise _unavailable(error) from error


@router.delete(
    "/destination-selections/{selection_id}",
    response_model=InstallationDestinationSelectionV1,
    responses=_ERRORS,
)
def cancel_destination_selection(
    request: Request,
    principal: MutationPrincipal,
    selection_id: Annotated[
        str,
        Path(
            pattern=r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"
        ),
    ],
) -> InstallationDestinationSelectionV1:
    try:
        return request.app.state.installation_destination_selection_service.cancel(
            selection_id=selection_id, selected_by=principal.operator_id
        )
    except SelectionNotFoundError as error:
        raise HTTPException(404, "Installation selection was not found.") from error
    except (SelectionClockError, SelectionStoreError) as error:
        raise _unavailable(error) from error


@router.api_route(
    "/destination-selections/{selection_id}",
    methods=["HEAD", "OPTIONS", "PATCH", "POST", "PUT", "TRACE"],
    include_in_schema=False,
)
def reject_unsupported_destination_selection_method() -> None:
    raise HTTPException(405, headers={"Allow": "DELETE, GET"})


@router.post(
    "/admission-assessments",
    response_model=InstallationAdmissionAssessmentV1,
    responses=_ERRORS,
)
async def create_admission_assessment(
    request: Request, principal: MutationPrincipal, idempotency_key: IdempotencyKey
) -> InstallationAdmissionAssessmentV1:
    payload = await _read_body(request, AdmissionAssessmentRequest)
    key = _validate_key(idempotency_key)
    try:
        plan = request.app.state.installation_plan_read_dependency.assemble(
            payload.item_id
        )
        if (
            plan.application.catalog_entry_id != payload.catalog_entry_id
            or plan.fingerprint.value != payload.plan_fingerprint
        ):
            raise HTTPException(409, "Installation plan fingerprint is not current.")
        service = request.app.state.installation_destination_selection_service
        selection = service.get_for_assessment(
            selection_id=payload.selection_id, selected_by=principal.operator_id
        )
        current = await service.observe_current_identity(selection.resource_id)
        now = request.app.state.installation_assessment_clock()
        assessment, _, _ = assess_installation_request(
            plan=plan,
            plan_fingerprint=payload.plan_fingerprint,
            selection=selection,
            principal_id=principal.operator_id,
            idempotency_key=key,
            requested_at=now,
            destination_available=current.destination_available,
            destination_identity_available=current.destination_identity_available,
            current_destination_fingerprint=current.current_destination_fingerprint,
            retry_cache=request.app.state.installation_assessment_retry_cache,
        )
        return assessment
    except HTTPException:
        raise
    except SelectionNotFoundError as error:
        raise HTTPException(404, "Installation selection was not found.") from error
    except (
        AssessmentIdempotencyConflictError,
        SelectionIdempotencyConflictError,
    ) as error:
        raise HTTPException(
            409, "Installation assessment idempotency conflict."
        ) from error
    except InstallationPlanItemNotFound as error:
        raise HTTPException(404, "Installation plan item was not found.") from error
    except (
        InstallationPlanSourceUnavailable,
        InstallationPlanClockUnavailable,
        InstallationPlanContractFailure,
        DestinationResolutionError,
        SelectionClockError,
        SelectionStoreError,
    ) as error:
        raise _unavailable(error) from error
    except ValueError as error:
        raise HTTPException(422, "Installation request is invalid.") from error
