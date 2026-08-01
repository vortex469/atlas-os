from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.execution_candidates.intake import (
    CandidatePlanningIntakeRequest,
    CandidatePlanningIntakeResult,
)
from app.models.contracts import APIError
from app.services.execution_candidate_intake import (
    ExecutionCandidatePlanningIntakeError,
    validate_candidate_planning_intake,
)

router = APIRouter(
    prefix="/execution-candidates",
    tags=["Execution Candidates"],
)


def _intake_unavailable(error: ExecutionCandidatePlanningIntakeError) -> HTTPException:
    return HTTPException(
        status_code=503,
        detail="Execution candidate planning intake is unavailable.",
    )


@router.post(
    "/{candidate_id}/planning-intake",
    response_model=CandidatePlanningIntakeResult,
    responses={503: {"model": APIError}},
    summary="Validate a current execution candidate for planning intake",
)
async def validate_execution_candidate_planning_intake(
    candidate_id: str,
    request: CandidatePlanningIntakeRequest,
) -> CandidatePlanningIntakeResult:
    try:
        return await validate_candidate_planning_intake(candidate_id, request)
    except ExecutionCandidatePlanningIntakeError as error:
        raise _intake_unavailable(error) from error
