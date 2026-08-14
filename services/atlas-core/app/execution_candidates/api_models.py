from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from app.execution_candidates.models import (
    ApprovalLevel,
    ComposeMutationSpecification,
    ExecutionCandidate,
    ExecutionCandidateEffectKind,
    ExecutionCandidateStatus,
    ExecutionCategory,
    ExecutionConstraint,
    ExecutionIntent,
    OperationalTargetReference,
)


class ExecutionCandidateResponse(BaseModel):
    """Public read-only DTO for an execution candidate."""

    id: str
    source_recommendation_id: str
    source_subsystem: str
    recommendation_class: str
    catalog_item_id: str | None = None
    target_id: str
    target_type: str
    execution_category: ExecutionCategory
    execution_intent: ExecutionIntent
    effect_kind: ExecutionCandidateEffectKind
    status: ExecutionCandidateStatus
    required_approval_level: ApprovalLevel
    rationale: str
    constraints: tuple[ExecutionConstraint, ...] = ()
    evidence_ids: tuple[str, ...] = ()
    compatibility_assessment_id: str | None = None
    compatibility_status: str | None = None
    relationship_ids: tuple[str, ...] = ()
    created_at: datetime
    expires_at: datetime | None = None


class CandidatePlanningExecutionCandidateResponse(ExecutionCandidateResponse):
    """Planning-intake DTO carrying actionable mutation evidence."""

    mutation: ComposeMutationSpecification | None = None
    operational_target: OperationalTargetReference | None = None


class ExecutionCandidatePageResponse(BaseModel):
    """Paginated read-only collection of current execution candidates."""

    candidates: tuple[ExecutionCandidateResponse, ...] = ()
    total: int = Field(ge=0)
    limit: int = Field(ge=1, le=100)
    offset: int = Field(ge=0)
    has_more: bool


def candidate_to_response(candidate: ExecutionCandidate) -> ExecutionCandidateResponse:
    """Convert an internal candidate to the public API DTO."""

    return ExecutionCandidateResponse(
        id=candidate.id,
        source_recommendation_id=candidate.source_recommendation_id,
        source_subsystem=candidate.source_subsystem,
        recommendation_class=candidate.recommendation_class,
        catalog_item_id=candidate.catalog_item_id,
        target_id=candidate.target_id,
        target_type=candidate.target_type,
        execution_category=candidate.execution_category,
        execution_intent=candidate.execution_intent,
        effect_kind=candidate.effect_kind,
        status=candidate.status,
        required_approval_level=candidate.required_approval_level,
        rationale=candidate.rationale,
        constraints=candidate.constraints,
        evidence_ids=candidate.evidence_ids,
        compatibility_assessment_id=candidate.compatibility_assessment_id,
        compatibility_status=candidate.compatibility_status,
        relationship_ids=candidate.relationship_ids,
        created_at=candidate.created_at,
        expires_at=candidate.expires_at,
    )


def candidate_to_planning_response(
    candidate: ExecutionCandidate,
) -> CandidatePlanningExecutionCandidateResponse:
    """Convert an internal candidate to the planning-intake API DTO."""

    return CandidatePlanningExecutionCandidateResponse(
        **candidate_to_response(candidate).model_dump(),
        mutation=candidate.mutation,
        operational_target=candidate.operational_target,
    )
