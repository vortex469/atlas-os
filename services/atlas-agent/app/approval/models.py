"""Immutable approval models."""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from pathlib import Path


class ApprovalStatus(StrEnum):
    """State of a human approval decision."""

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class ApprovalPurpose(StrEnum):
    """Purpose of one human approval boundary."""

    IMPLEMENTATION = "implementation"
    CANDIDATE_WORKFLOW_SHELL = "candidate_workflow_shell"
    VERIFICATION = "verification"
    COMMIT = "commit"
    OPERATIONAL_ACTION = "operational_action"


@dataclass(frozen=True, slots=True)
class VerificationApprovalEnvironment:
    """Non-secret environment metadata bound to a verification approval."""

    name: str
    value_digest: str


@dataclass(frozen=True, slots=True)
class VerificationApprovalCheck:
    """Exact non-secret verification check metadata requiring approval."""

    identifier: str
    command: tuple[str, ...]
    working_directory: Path
    timeout_seconds: float | None
    environment: tuple[VerificationApprovalEnvironment, ...] = ()


@dataclass(frozen=True, slots=True)
class CommitApprovalMetadata:
    """Exact non-secret metadata bound to a commit approval."""

    expected_branch: str | None
    expected_head: str | None
    reviewed_files: tuple[Path, ...]
    reviewed_content_fingerprint: str
    commit_message: str


@dataclass(frozen=True, slots=True)
class OperationalApprovalMetadata:
    """Exact semantic binding for one non-executable operational request."""

    action_request_id: str
    action_request_digest: str
    candidate_id: str
    candidate_fingerprint: str
    operational_plan_fingerprint: str
    provider_id: str
    resource_id: str
    resource_type: str
    target_fingerprint: str
    target_version: str | None
    operation_intent: str
    disruption_scope: str
    verification_digest: str
    generated_at: datetime
    expires_at: datetime

    def __post_init__(self) -> None:
        if self.expires_at <= self.generated_at:
            raise ValueError("operational approval expiry must follow generation time")


@dataclass(frozen=True, slots=True)
class ApprovalRequest:
    """One tool-execution request requiring human approval."""

    identifier: str
    checkpoint_id: str
    title: str
    requested_tool: str
    requested_command: tuple[str, ...]
    rationale: str
    workflow_id: str | None = None
    requested_working_directory: Path | None = None
    purpose: ApprovalPurpose = ApprovalPurpose.IMPLEMENTATION
    verification_checks: tuple[VerificationApprovalCheck, ...] = ()
    commit_metadata: CommitApprovalMetadata | None = None
    operational_metadata: OperationalApprovalMetadata | None = None


@dataclass(frozen=True, slots=True)
class ApprovalDecision:
    """Human decision for one approval request."""

    request: ApprovalRequest
    status: ApprovalStatus
    reviewer: str | None = None
    reason: str | None = None


@dataclass(frozen=True, slots=True)
class ApprovalResult:
    """Immutable result derived from an approval decision."""

    decision: ApprovalDecision

    @property
    def approved(self) -> bool:
        """Return whether the request was approved."""

        return self.decision.status is ApprovalStatus.APPROVED
