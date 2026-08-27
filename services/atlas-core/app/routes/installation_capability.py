"""Authenticated, read-only installation capability assessment projection."""

from __future__ import annotations

import re
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Request

from app.installation_capability.assessment import (
    InstallationCapabilityAssessmentV1,
    assess_installation_capability,
)
from app.installation_capability.provider_facts import (
    adapt_proxmox_qemu_capability_facts,
)
from app.installation_plan.assembly import (
    InstallationPlanClockUnavailable,
    InstallationPlanContractFailure,
    InstallationPlanItemNotFound,
    InstallationPlanSourceUnavailable,
)
from app.installation_targets.resolver import (
    DestinationResolutionError,
    project_destination,
)
from app.installation_targets.service import SelectionClockError
from app.installation_targets.store import SelectionNotFoundError, SelectionStoreError
from app.models.contracts import APIError
from app.operator_auth.dependencies import require_operator_permission
from app.operator_auth.models import (
    INSTALLATION_DESTINATION_SELECT,
    OperatorPrincipal,
)

router = APIRouter(prefix="/installation", tags=["Installation Capability"])
_read = require_operator_permission(INSTALLATION_DESTINATION_SELECT)
ReadPrincipal = Annotated[OperatorPrincipal, Depends(_read)]
_ITEM_ID = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*", re.ASCII)
_SELECTION_ID = re.compile(
    r"[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}",
    re.ASCII,
)
_ERRORS = {
    401: {"model": APIError},
    403: {"model": APIError},
    404: {"model": APIError},
    422: {"model": APIError},
    500: {"model": APIError},
    503: {"model": APIError},
}


def _valid_ascii(value: str, pattern: re.Pattern[str], maximum: int) -> bool:
    try:
        encoded = value.encode("ascii")
    except UnicodeEncodeError:
        return False
    return len(encoded) <= maximum and pattern.fullmatch(value) is not None


def _declares_body(request: Request) -> bool:
    lengths = request.headers.getlist("content-length")
    if lengths:
        if len(lengths) != 1 or not lengths[0].isascii() or not lengths[0].isdecimal():
            return True
        if int(lengths[0]) != 0:
            return True
    return bool(request.headers.getlist("transfer-encoding"))


def _unavailable(error: Exception) -> HTTPException:
    return HTTPException(503, "Installation capability assessment is unavailable.")


@router.get(
    "/capability-assessments/{item_id}/{selection_id}",
    response_model=InstallationCapabilityAssessmentV1,
    responses=_ERRORS,
    summary="Read a server-assembled installation capability assessment",
)
async def read_installation_capability_assessment(
    request: Request,
    principal: ReadPrincipal,
    item_id: Annotated[str, Path()],
    selection_id: Annotated[str, Path()],
) -> InstallationCapabilityAssessmentV1:
    if (
        request.url.path.rstrip("/") != request.url.path
        or request.query_params
        or _declares_body(request)
        or await request.body()
        or not _valid_ascii(item_id, _ITEM_ID, 64)
        or not _valid_ascii(selection_id, _SELECTION_ID, 36)
    ):
        raise HTTPException(422, "Installation capability request is invalid.")

    try:
        plan = request.app.state.installation_plan_read_dependency.assemble(item_id)
        service = request.app.state.installation_destination_selection_service
        selection = service.get_for_assessment(
            selection_id=selection_id,
            selected_by=principal.operator_id,
        )
        resolved = await request.app.state.installation_capability_target_resolver(
            "proxmox", selection.resource_id, "qemu"
        )
        current_destination = project_destination(resolved)
        evaluated_at = request.app.state.installation_capability_clock()
        provider_facts = adapt_proxmox_qemu_capability_facts(
            resolved,
            expected_destination_fingerprint=(
                current_destination.destination_fingerprint
            ),
            observed_at=evaluated_at,
        )
        return assess_installation_capability(
            plan=plan,
            selection=selection,
            current_destination=current_destination,
            provider_facts=provider_facts,
            evaluated_at=evaluated_at,
        )
    except SelectionNotFoundError as error:
        raise HTTPException(404, "Installation selection was not found.") from error
    except InstallationPlanItemNotFound as error:
        raise HTTPException(404, "Installation plan item was not found.") from error
    except (
        InstallationPlanSourceUnavailable,
        InstallationPlanClockUnavailable,
        InstallationPlanContractFailure,
        DestinationResolutionError,
        SelectionClockError,
        SelectionStoreError,
        ValueError,
    ) as error:
        raise _unavailable(error) from error
    except Exception as error:
        raise HTTPException(500, "An unexpected internal error occurred.") from error


@router.api_route(
    "/capability-assessments/{item_id}/{selection_id}",
    methods=["DELETE", "HEAD", "OPTIONS", "PATCH", "POST", "PUT", "TRACE"],
    include_in_schema=False,
)
def reject_installation_capability_mutation() -> None:
    raise HTTPException(405, headers={"Allow": "GET"})
