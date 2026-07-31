"""Immutable Atlas Agent workflow-state models."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from app.approval.models import ApprovalRequest
from app.context.models import AgentContext
from app.execution.models import ExecutionResult
from app.model_providers.models import ModelResponse
from app.planning.models import ImplementationPlan, RoadmapCheckpoint
from app.repository.models import CommitRequest, CommitResult
from app.review.models import ArchitectureAssessment, ReviewReport, TestEvidence
from app.verification.models import VerificationCheck, VerificationReport


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
    EXECUTING = "executing"
    AWAITING_VERIFICATION_APPROVAL = "awaiting_verification_approval"
    VERIFYING = "verifying"
    AWAITING_COMMIT_APPROVAL = "awaiting_commit_approval"
    COMMITTING = "committing"
    BLOCKED = "blocked"
    COMPLETED = "completed"


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
    request: WorkflowRequest
    plan: ImplementationPlan
    state: WorkflowSessionState
    planning_analysis: ModelResponse | None = None
    context: AgentContext | None = None
    execution_result: ExecutionResult | None = None
    changed_files: tuple[Path, ...] = ()
    verification_report: VerificationReport | None = None
    review_report: ReviewReport | None = None
    commit_request: CommitRequest | None = None
    reviewed_files: tuple[Path, ...] = ()
    expected_branch: str | None = None
    expected_head: str | None = None
    reviewed_content_fingerprint: str | None = None


@dataclass(frozen=True, slots=True)
class WorkflowResult:
    """Immutable result of one Atlas Agent workflow."""

    sprint: SprintStatus
    plan: ImplementationPlan | None = None
    context: AgentContext | None = None
    planning_analysis: ModelResponse | None = None
    approval_request: ApprovalRequest | None = None
    execution_result: ExecutionResult | None = None
    verification_report: VerificationReport | None = None
    review_report: ReviewReport | None = None
    commit_result: CommitResult | None = None
    error_message: str | None = None
