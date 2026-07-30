"""Immutable approval models."""

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path


class ApprovalStatus(StrEnum):
    """State of a human approval decision."""

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


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
