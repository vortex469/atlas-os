"""Authenticated, read-only installation candidate admission projection."""

from __future__ import annotations

import re
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Request

from app.installation_candidate_admission.assembly import (
    InstallationCandidateAdmissionInputMissing,
    InstallationCandidateAdmissionInputUnavailable,
)
from app.installation_candidate_admission.contract import (
    InstallationCandidateAdmissionV1,
)
from app.models.contracts import APIError
from app.operator_auth.dependencies import require_operator_permission
from app.operator_auth.models import (
    INSTALLATION_DESTINATION_SELECT,
    OperatorPrincipal,
)

router = APIRouter(prefix="/installation", tags=["Installation Candidate Admission"])
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


@router.get(
    "/candidate-admissions/{item_id}/{selection_id}",
    response_model=InstallationCandidateAdmissionV1,
    responses=_ERRORS,
    summary="Read a server-assembled installation candidate admission",
)
async def read_installation_candidate_admission(
    request: Request,
    principal: ReadPrincipal,
    item_id: Annotated[str, Path()],
    selection_id: Annotated[str, Path()],
) -> InstallationCandidateAdmissionV1:
    if (
        request.url.path.rstrip("/") != request.url.path
        or request.query_params
        or _declares_body(request)
        or await request.body()
        or not _valid_ascii(item_id, _ITEM_ID, 64)
        or not _valid_ascii(selection_id, _SELECTION_ID, 36)
    ):
        raise HTTPException(422, "Installation candidate admission request is invalid.")

    try:
        dependency = request.app.state.installation_candidate_admission_read_dependency
        return await dependency.assemble(
            item_id=item_id,
            selection_id=selection_id,
            principal_id=principal.operator_id,
        )
    except InstallationCandidateAdmissionInputMissing as error:
        raise HTTPException(
            404, "Installation candidate admission input was not found."
        ) from error
    except InstallationCandidateAdmissionInputUnavailable as error:
        raise HTTPException(
            503, "Installation candidate admission input is unavailable."
        ) from error
    except Exception as error:
        raise HTTPException(
            503, "Installation candidate admission input is unavailable."
        ) from error


@router.api_route(
    "/candidate-admissions/{item_id}/{selection_id}",
    methods=["DELETE", "HEAD", "OPTIONS", "PATCH", "POST", "PUT", "TRACE"],
    include_in_schema=False,
)
def reject_installation_candidate_admission_mutation() -> None:
    raise HTTPException(405, headers={"Allow": "GET"})
