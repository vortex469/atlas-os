"""Candidate-planning intake routes."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, Field

from app.candidate_planning.models import CandidatePlanRequest, CandidatePlanResponse
from app.candidate_planning.service import CandidatePlanningServiceError

router = APIRouter(prefix="/candidate-planning", tags=["candidate-planning"])


class CandidatePlanningRequest(BaseModel):
    """Validated request for a side-effect-free candidate-planning session."""

    model_config = ConfigDict(extra="forbid")

    candidate_id: str = Field(min_length=1)
    expected_candidate_fingerprint: str | None = None

    def to_domain(self) -> CandidatePlanRequest:
        return CandidatePlanRequest(
            candidate_id=self.candidate_id,
            expected_candidate_fingerprint=self.expected_candidate_fingerprint,
        )


class CandidatePlanningResponse(BaseModel):
    """Serialized candidate-planning session response."""

    model_config = ConfigDict(from_attributes=True)

    session_id: str | None
    candidate_id: str
    status: str
    planning_allowed: bool
    intake_status: str
    intake_reason_codes: tuple[str, ...] = ()
    candidate_fingerprint: str | None = None
    unsupported_reason: str | None = None


class CandidatePlanningErrorDetail(BaseModel):
    code: str
    message: str


class CandidatePlanningErrorResponse(BaseModel):
    detail: CandidatePlanningErrorDetail


def _to_response(response: CandidatePlanResponse) -> CandidatePlanningResponse:
    return CandidatePlanningResponse(
        session_id=response.session_id,
        candidate_id=response.candidate_id,
        status=response.status.value,
        planning_allowed=response.planning_allowed,
        intake_status=response.intake_status.value,
        intake_reason_codes=response.intake_reason_codes,
        candidate_fingerprint=response.candidate_fingerprint,
        unsupported_reason=response.unsupported_reason,
    )


@router.post(
    "",
    response_model=CandidatePlanningResponse,
    status_code=status.HTTP_202_ACCEPTED,
    responses={status.HTTP_503_SERVICE_UNAVAILABLE: {"model": CandidatePlanningErrorResponse}},
)
async def create_candidate_planning_session(
    request: Request,
    planning_request: CandidatePlanningRequest,
) -> CandidatePlanningResponse:
    """Create or reuse a planning-only session from an authoritative Core candidate."""

    try:
        response = await request.app.state.container.candidate_planning_service.create_planning_session(
            planning_request.to_domain()
        )
    except CandidatePlanningServiceError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"code": exc.code.value, "message": exc.message},
        ) from exc
    return _to_response(response)
