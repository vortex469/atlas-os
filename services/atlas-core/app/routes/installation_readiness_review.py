"""Exact read-only HTTP surface for installation readiness review v1."""

from __future__ import annotations

import re
from typing import Annotated

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import WithJsonSchema

from app.core.exceptions import request_id_for
from app.installation_readiness_review.contract import (
    InstallationReadinessReviewRedactedErrorV1,
    InstallationReadinessReviewResponseV1,
)
from app.operator_auth.dependencies import require_operator_permission
from app.operator_auth.models import INSTALLATION_DESTINATION_SELECT

_UUID4 = r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"
_read = require_operator_permission(INSTALLATION_DESTINATION_SELECT)
router = APIRouter(
    prefix="/installation/candidate-records",
    tags=["Installation Readiness Review"],
)

_ERRORS = {
    code: {"model": InstallationReadinessReviewRedactedErrorV1}
    for code in (401, 403, 404, 422, 503)
}
_STATUS = {
    "unauthenticated": 401,
    "unauthorized": 403,
    "not_found": 404,
    "malformed": 422,
    "unavailable": 503,
}


@router.get(
    "/{candidate_record_id}/readiness-review",
    response_model=InstallationReadinessReviewResponseV1,
    responses=_ERRORS,
    summary="Review installation readiness evidence",
)
async def get_installation_readiness_review(
    request: Request,
    candidate_record_id: Annotated[
        str,
        WithJsonSchema({"type": "string", "pattern": _UUID4}),
    ],
) -> InstallationReadinessReviewResponseV1 | JSONResponse:
    correlation_id = request_id_for(request)
    if (
        re.fullmatch(_UUID4, candidate_record_id, re.ASCII) is None
        or request.query_params
        or await request.body()
    ):
        return _error("malformed", correlation_id)
    try:
        principal = _read(request)
    except HTTPException as error:
        code = "unauthenticated" if error.status_code == 401 else "unauthorized"
        return _error(code, correlation_id)
    try:
        result = request.app.state.installation_readiness_review_service.review(
            candidate_record_id=candidate_record_id,
            authenticated_operator_id=principal.operator_id,
            read_permission_verified=True,
            correlation_id=correlation_id,
        )
    except Exception:  # noqa: BLE001 - service failures are always redacted
        return _error("unavailable", correlation_id)
    if result.response is not None:
        return result.response
    if result.error is None:
        return _error("unavailable", correlation_id)
    return JSONResponse(
        status_code=_STATUS[result.error.error_code],
        content=result.error.model_dump(mode="json"),
    )


def _error(error_code: str, correlation_id: str) -> JSONResponse:
    error = InstallationReadinessReviewRedactedErrorV1(
        error_code=error_code,
        correlation_id=correlation_id,
    )
    return JSONResponse(
        status_code=_STATUS[error.error_code],
        content=error.model_dump(mode="json"),
    )


@router.api_route(
    "/{candidate_record_id}/readiness-review",
    methods=["DELETE", "HEAD", "OPTIONS", "PATCH", "POST", "PUT", "TRACE"],
    include_in_schema=False,
)
def reject_installation_readiness_review_mutation() -> None:
    raise HTTPException(405, headers={"Allow": "GET"})
