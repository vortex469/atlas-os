"""Candidate-planning intake routes."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, Field

from app.candidate_planning.models import (
    CandidatePlan,
    CandidatePlanningFailure,
    CandidatePlanRequest,
    CandidatePlanResponse,
)
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


class CandidatePlanningFailureResponse(BaseModel):
    code: str
    message: str


class CandidatePlanApiResponse(BaseModel):
    identifier: str
    session_id: str
    candidate_id: str
    candidate_fingerprint: str
    title: str
    objective: str
    assumptions: tuple[str, ...]
    constraints: tuple[str, ...]
    proposed_steps: tuple[str, ...]
    likely_affected_components: tuple[str, ...]
    likely_affected_files: tuple[str, ...]
    verification_strategy: tuple[str, ...]
    rollback_considerations: tuple[str, ...]
    unresolved_questions: tuple[str, ...]
    evidence_ids: tuple[str, ...]
    created_at: str
    repository_branch: str | None
    repository_head: str | None
    revalidated_candidate_fingerprint: str


class CandidatePlanningResponse(BaseModel):
    """Serialized candidate-planning session response."""

    session_id: str | None
    candidate_id: str
    status: str
    planning_allowed: bool
    intake_status: str
    intake_reason_codes: tuple[str, ...] = ()
    candidate_fingerprint: str | None = None
    unsupported_reason: str | None = None
    plan: CandidatePlanApiResponse | None = None
    planning_failure: CandidatePlanningFailureResponse | None = None


class CandidatePlanningErrorDetail(BaseModel):
    code: str
    message: str


class CandidatePlanningErrorResponse(BaseModel):
    detail: CandidatePlanningErrorDetail


def _path(value: Path) -> str:
    return str(value)


def _plan_response(plan: CandidatePlan | None) -> CandidatePlanApiResponse | None:
    if plan is None:
        return None
    return CandidatePlanApiResponse(
        identifier=plan.identifier,
        session_id=plan.session_id,
        candidate_id=plan.candidate_id,
        candidate_fingerprint=plan.candidate_fingerprint,
        title=plan.title,
        objective=plan.objective,
        assumptions=plan.assumptions,
        constraints=plan.constraints,
        proposed_steps=plan.proposed_steps,
        likely_affected_components=plan.likely_affected_components,
        likely_affected_files=tuple(_path(path) for path in plan.likely_affected_files),
        verification_strategy=plan.verification_strategy,
        rollback_considerations=plan.rollback_considerations,
        unresolved_questions=plan.unresolved_questions,
        evidence_ids=plan.evidence_ids,
        created_at=plan.created_at.isoformat(),
        repository_branch=plan.repository_branch,
        repository_head=plan.repository_head,
        revalidated_candidate_fingerprint=plan.revalidated_candidate_fingerprint,
    )


def _failure_response(
    failure: CandidatePlanningFailure | None,
) -> CandidatePlanningFailureResponse | None:
    if failure is None:
        return None
    return CandidatePlanningFailureResponse(
        code=failure.code.value,
        message=failure.message,
    )


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
        plan=_plan_response(response.plan),
        planning_failure=_failure_response(response.planning_failure),
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


@router.get("/{session_id}", response_model=CandidatePlanningResponse)
async def get_candidate_planning_session(
    request: Request,
    session_id: str,
) -> CandidatePlanningResponse:
    """Return a current candidate-planning session without side effects."""

    session = request.app.state.container.candidate_planning_service.get_session(session_id)
    if session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    return _to_response(
        CandidatePlanResponse(
            session_id=session.identifier,
            candidate_id=session.candidate_id,
            status=session.planning_status,
            planning_allowed=session.status.value == "ready_for_planning",
            intake_status=session.snapshot.intake_status,
            intake_reason_codes=session.snapshot.intake_reason_codes,
            candidate_fingerprint=session.candidate_fingerprint,
            unsupported_reason=session.unsupported_reason,
            plan=session.plan,
            planning_failure=session.planning_failure,
        )
    )


@router.post(
    "/{session_id}/plan",
    response_model=CandidatePlanningResponse,
    status_code=status.HTTP_202_ACCEPTED,
    responses={status.HTTP_503_SERVICE_UNAVAILABLE: {"model": CandidatePlanningErrorResponse}},
)
async def generate_candidate_plan(
    request: Request,
    session_id: str,
) -> CandidatePlanningResponse:
    """Generate or return one deterministic read-only plan for a candidate session."""

    try:
        response = await request.app.state.container.candidate_planning_service.generate_plan(
            session_id
        )
    except CandidatePlanningServiceError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"code": exc.code.value, "message": exc.message},
        ) from exc
    if response.session_id is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    return _to_response(response)


@router.get("/{session_id}/plan", response_model=CandidatePlanApiResponse)
async def get_candidate_plan(
    request: Request,
    session_id: str,
) -> CandidatePlanApiResponse:
    """Return an existing candidate plan without generating a new one."""

    plan = request.app.state.container.candidate_planning_service.get_plan(session_id)
    if plan is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plan not found")
    return _plan_response(plan)
