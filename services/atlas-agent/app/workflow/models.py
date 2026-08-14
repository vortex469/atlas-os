"""Immutable Atlas Agent workflow-state models."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import TYPE_CHECKING

from app.approval.models import ApprovalRequest
from app.context.models import AgentContext
from app.execution.models import ExecutionResult
from app.model_providers.models import ModelResponse
from app.planning.models import ImplementationPlan, RoadmapCheckpoint
from app.repository.models import CommitRequest, CommitResult
from app.review.models import ArchitectureAssessment, ReviewReport, TestEvidence
from app.verification.models import VerificationCheck, VerificationReport

if TYPE_CHECKING:
    from app.candidate_planning.models import (
        CandidateImplementationRequest,
        OperationalActionRequest,
    )
    from app.candidate_planning.verification import (
        CandidateReviewResult,
        CandidateVerificationEvidence,
        CandidateVerificationPlan,
    )


class SprintPhase(StrEnum):
    """Lifecycle phase of one Atlas Agent sprint."""

    PLANNED = "planned"
    AWAITING_APPROVAL = "awaiting_approval"
    IN_PROGRESS = "in_progress"
    AWAITING_VERIFICATION_APPROVAL = "awaiting_verification_approval"
    VERIFYING = "verifying"
    AWAITING_COMMIT_APPROVAL = "awaiting_commit_approval"
    COMMITTING = "committing"
    REVIEWING = "reviewing"
    COMPLETED = "completed"
    BLOCKED = "blocked"


class WorkflowSessionState(StrEnum):
    """Lifecycle state for one stored workflow session."""

    PLANNED = "planned"
    AWAITING_APPROVAL = "awaiting_approval"
    AWAITING_IMPLEMENTATION_APPROVAL = "awaiting_implementation_approval"
    EXECUTING = "executing"
    PATCH_APPLIED_PENDING_VERIFICATION = "patch_applied_pending_verification"
    AWAITING_VERIFICATION_APPROVAL = "awaiting_verification_approval"
    VERIFYING = "verifying"
    AWAITING_COMMIT_APPROVAL = "awaiting_commit_approval"
    COMMITTING = "committing"
    BLOCKED = "blocked"
    COMPLETED = "completed"


class WorkflowSource(StrEnum):
    """Authoritative origin of a workflow session."""

    ROADMAP = "roadmap"
    CANDIDATE = "candidate"
    MANUAL = "manual"


class WorkflowEffectKind(StrEnum):
    """Kind of side effect represented by a workflow."""

    REPOSITORY_CHANGE = "repository_change"
    OPERATIONAL_ACTION = "operational_action"


class OperationalExecutionStage(StrEnum):
    """Agent projection of one Core-owned operational lifecycle."""

    EXECUTION_BLOCKED = "execution_blocked"
    SUBMISSION_OUTCOME_UNKNOWN = "submission_outcome_unknown"
    DISPATCH_PENDING = "dispatch_pending"
    VERIFICATION_PENDING = "verification_pending"
    VERIFIED = "verified"
    FAILED = "failed"
    VERIFICATION_FAILED = "verification_failed"
    TARGET_REPLACED = "target_replaced"
    OUTCOME_UNKNOWN = "outcome_unknown"


@dataclass(frozen=True, slots=True)
class OperationalExecutionReference:
    """Minimal non-secret reference to a Core operational lifecycle."""

    request_id: str
    request_digest: str
    stage: OperationalExecutionStage
    dispatch_status: str | None
    ledger_state: str | None
    provider_operation_id: str | None
    verification_status: str | None
    submitted_at: datetime | None
    last_observed_at: datetime
    terminal: bool
    controlled_reason: str | None = None
    audit_events: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class CandidateWorkflowMetadata:
    """Immutable audit linkage for a candidate-derived workflow shell."""

    candidate_planning_session_id: str
    candidate_id: str
    candidate_fingerprint: str
    candidate_plan_id: str
    candidate_plan_fingerprint: str
    source_recommendation_id: str
    source_subsystem: str
    catalog_item_id: str | None
    target_id: str
    target_type: str
    execution_category: str
    execution_intent: str
    evidence_ids: tuple[str, ...]
    compatibility_assessment_id: str | None
    compatibility_status: str | None
    relationship_ids: tuple[str, ...]
    conversion_timestamp: datetime
    core_revalidation_status: str
    core_revalidation_fingerprint: str
    effect_kind: WorkflowEffectKind


@dataclass(frozen=True, slots=True)
class SprintStatus:
    """Current Atlas Agent sprint status."""

    checkpoint_id: str
    title: str
    goal: str
    phase: SprintPhase


@dataclass(frozen=True, slots=True)
class WorkflowRequest:
    """Immutable request to execute one Atlas Agent workflow."""

    checkpoint: RoadmapCheckpoint
    repository_root: Path
    execution_identifier: str
    execution_argv: tuple[str, ...]
    execution_workdir: Path
    verification_checks: tuple[VerificationCheck, ...]
    review_identifier: str
    architecture_assessments: tuple[ArchitectureAssessment, ...] = ()
    test_evidence: tuple[TestEvidence, ...] = ()


@dataclass(frozen=True, slots=True)
class WorkflowSession:
    """Immutable identity and artifacts for one planned workflow."""

    identifier: str
    request: WorkflowRequest | None
    plan: ImplementationPlan | None
    state: WorkflowSessionState
    effect_kind: WorkflowEffectKind
    source: WorkflowSource = WorkflowSource.ROADMAP
    candidate_metadata: CandidateWorkflowMetadata | None = None
    candidate_implementation_request: CandidateImplementationRequest | None = None
    operational_action_request: OperationalActionRequest | None = None
    candidate_implementation_approval_id: str | None = None
    operational_action_approval_id: str | None = None
    operational_execution_reference: OperationalExecutionReference | None = None
    planning_analysis: ModelResponse | None = None
    review_analysis: ModelResponse | None = None
    context: AgentContext | None = None
    execution_result: ExecutionResult | None = None
    worker_patch_applied: bool = False
    worker_baseline_status: tuple[tuple[str, str], ...] | None = None
    changed_files: tuple[Path, ...] = ()
    verification_report: VerificationReport | None = None
    candidate_verification_plan: CandidateVerificationPlan | None = None
    candidate_verification_evidence: CandidateVerificationEvidence | None = None
    review_report: ReviewReport | None = None
    candidate_review_result: CandidateReviewResult | None = None
    commit_request: CommitRequest | None = None
    commit_result: CommitResult | None = None
    reviewed_files: tuple[Path, ...] = ()
    expected_branch: str | None = None
    expected_head: str | None = None
    reviewed_content_fingerprint: str | None = None
    blocked_reason: str | None = None

    def __post_init__(self) -> None:
        if (
            self.candidate_metadata is not None
            and self.candidate_metadata.effect_kind is not self.effect_kind
        ):
            raise ValueError("workflow effect kind must match candidate metadata")
        if (
            self.effect_kind is WorkflowEffectKind.REPOSITORY_CHANGE
            and self.operational_action_request is not None
        ):
            raise ValueError("repository_change workflows cannot carry operational requests")
        if (
            self.effect_kind is WorkflowEffectKind.OPERATIONAL_ACTION
            and self.candidate_implementation_request is not None
        ):
            raise ValueError("operational_action workflows cannot carry repository requests")
        if (
            self.effect_kind is WorkflowEffectKind.REPOSITORY_CHANGE
            and self.operational_action_approval_id is not None
        ):
            raise ValueError("repository_change workflows cannot carry operational approvals")
        if self.operational_action_request is not None:
            request = self.operational_action_request
            metadata = self.candidate_metadata
            if metadata is None:
                raise ValueError("operational requests require candidate metadata")
            if (
                request.workflow_session_id != self.identifier
                or request.candidate_id != metadata.candidate_id
                or request.candidate_fingerprint != metadata.candidate_fingerprint
                or request.candidate_plan_fingerprint
                != metadata.candidate_plan_fingerprint
            ):
                raise ValueError("operational request does not match workflow identity")
        if self.operational_execution_reference is not None:
            request = self.operational_action_request
            reference = self.operational_execution_reference
            if request is None or (
                reference.request_id != request.request_id
                or reference.request_digest != request.request_digest
            ):
                raise ValueError("operational execution reference does not match request")


@dataclass(frozen=True, slots=True)
class WorkflowResult:
    """Immutable result of one Atlas Agent workflow."""

    sprint: SprintStatus
    plan: ImplementationPlan | None = None
    context: AgentContext | None = None
    planning_analysis: ModelResponse | None = None
    review_analysis: ModelResponse | None = None
    approval_request: ApprovalRequest | None = None
    execution_result: ExecutionResult | None = None
    verification_report: VerificationReport | None = None
    review_report: ReviewReport | None = None
    commit_result: CommitResult | None = None
    error_message: str | None = None
    EXECUTION_BLOCKED = "execution_blocked"
