from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, Request

from app.execution_candidates.intake import (
    CandidatePlanningIntakeRequest,
    CandidatePlanningIntakeResult,
)
from app.models.contracts import APIError
from app.services.execution_candidate_intake import (
    ExecutionCandidatePlanningIntakeError,
    validate_candidate_planning_intake,
)
from app.services.execution_candidates import get_current_execution_candidate

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
    intake_request: CandidatePlanningIntakeRequest,
    request: Request,
) -> CandidatePlanningIntakeResult:
    store = getattr(request.app.state, "operator_intent_store", None)

    try:
        if store is None:
            result = await validate_candidate_planning_intake(candidate_id, intake_request)
        else:
            async def candidate_resolver(current_candidate_id: str, **kwargs):
                return await get_current_execution_candidate(
                    current_candidate_id,
                    operator_intent_store=store,
                    **kwargs,
                )

            result = await validate_candidate_planning_intake(
                candidate_id,
                intake_request,
                candidate_resolver=candidate_resolver,
            )
        if store is not None and candidate_id.startswith("candidate-operator-intent-"):
            store.append_audit(
                event=(
                    "planning_intake_accepted"
                    if result.planning_allowed
                    else "planning_intake_rejected"
                ),
                reason=result.status.value,
                occurred_at=datetime.now(UTC),
                candidate_id=candidate_id,
            )
        return result
    except ExecutionCandidatePlanningIntakeError as error:
        raise _intake_unavailable(error) from error
