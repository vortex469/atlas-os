"""Closed, read-only HTTP surface for InstallationPlan v1."""

from __future__ import annotations

import re
from typing import Annotated

from fastapi import APIRouter, Path, Request
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute
from starlette.routing import Match
from starlette.types import Scope

from app.core.exceptions import error_response
from app.installation_plan.assembly import (
    InstallationPlanClockUnavailable,
    InstallationPlanContractFailure,
    InstallationPlanItemNotFound,
    InstallationPlanSourceUnavailable,
)
from app.installation_plan.contract import InstallationPlan
from app.models.contracts import APIError
from app.services.installation_plan import get_installation_plan_read_dependency


class _InstallationPlanRoute(APIRoute):
    """Route malformed InstallationPlan-shaped paths to sanitized validation."""

    def matches(self, scope: Scope) -> tuple[Match, Scope]:
        match, child_scope = super().matches(scope)
        path = scope.get("path", "")
        if match is not Match.NONE:
            return match, child_scope
        prefix, marker, suffix = self.path.partition("{item_id}")
        namespace_at = path.find(prefix)
        if not marker or namespace_at < 0:
            return match, child_scope
        configured_prefix = path[:namespace_at] + prefix
        remainder = path[len(configured_prefix) :]
        if remainder.rstrip("/").endswith(suffix):
            malformed = dict(scope)
            malformed["path"] = f"{configured_prefix}INVALID!{suffix}"
            malformed["raw_path"] = malformed["path"].encode("ascii")
            return super().matches(malformed)
        return match, child_scope


router = APIRouter(
    prefix="/discovery",
    tags=["Discovery"],
    route_class=_InstallationPlanRoute,
)
_ITEM_ID = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*", re.ASCII)
_INVALID_REQUEST = "Installation plan request is invalid."


def _valid_item_id(value: str) -> bool:
    try:
        encoded = value.encode("ascii")
    except UnicodeEncodeError:
        return False
    return len(encoded) <= 64 and _ITEM_ID.fullmatch(value) is not None


def _declares_body(request: Request) -> bool:
    content_lengths = request.headers.getlist("content-length")
    if content_lengths:
        if len(content_lengths) != 1:
            return True
        value = content_lengths[0]
        if not value.isascii() or not value.isdecimal():
            return True
        try:
            if int(value) != 0:
                return True
        except ValueError:
            return True
    return bool(request.headers.getlist("transfer-encoding"))


def _failure(
    request: Request, *, status_code: int, code: str, message: str
) -> JSONResponse:
    return error_response(
        request,
        status_code=status_code,
        code=code,
        message=message,
        details={},
    )


@router.get(
    "/items/{item_id}/installation-plan",
    response_model=InstallationPlan,
    responses={404: {"model": APIError}, 503: {"model": APIError}},
    summary="Read the InstallationPlan for a Discovery catalog item",
)
async def get_discovery_item_installation_plan(
    request: Request,
    item_id: Annotated[str, Path()],
) -> InstallationPlan:
    if request.url.path.rstrip("/") != request.url.path:
        return _failure(
            request,
            status_code=422,
            code="validation_error",
            message=_INVALID_REQUEST,
        )
    if request.query_params or _declares_body(request) or await request.body():
        return _failure(
            request,
            status_code=422,
            code="validation_error",
            message=_INVALID_REQUEST,
        )
    if not _valid_item_id(item_id):
        return _failure(
            request,
            status_code=422,
            code="validation_error",
            message=_INVALID_REQUEST,
        )
    validated_item_id = item_id

    try:
        return get_installation_plan_read_dependency().assemble(validated_item_id)
    except InstallationPlanItemNotFound:
        return _failure(
            request,
            status_code=404,
            code="installation_plan_item_not_found",
            message="Installation plan item was not found.",
        )
    except InstallationPlanSourceUnavailable:
        return _failure(
            request,
            status_code=503,
            code="service_unavailable",
            message="Installation plan sources are unavailable.",
        )
    except InstallationPlanClockUnavailable:
        return _failure(
            request,
            status_code=503,
            code="service_unavailable",
            message="Installation plan clock is unavailable.",
        )
    except InstallationPlanContractFailure:
        return _failure(
            request,
            status_code=503,
            code="service_unavailable",
            message="Installation plan contract is unavailable.",
        )
    except Exception:  # noqa: BLE001 - the HTTP trust boundary must sanitize all faults
        return _failure(
            request,
            status_code=500,
            code="internal_server_error",
            message="An unexpected internal error occurred.",
        )
