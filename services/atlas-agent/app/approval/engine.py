"""Approval engine for Atlas Agent."""

from __future__ import annotations

from dataclasses import dataclass

from app.approval.exceptions import ApprovalValidationError
from app.approval.models import (
    ApprovalDecision,
    ApprovalRequest,
    ApprovalResult,
    ApprovalStatus,
)


@dataclass(frozen=True, slots=True)
class ApprovalEngine:
    """Engine for validating and normalizing approval decisions."""

    def evaluate(
        self,
        decision: ApprovalDecision,
    ) -> ApprovalResult:
        """Validate and normalize an approval decision.

        Args:
            decision: The approval decision to evaluate.

        Returns:
            Normalized approval result.

        Raises:
            ApprovalValidationError: If the decision is invalid.
        """
        # Validate and normalize the embedded ApprovalRequest
        request = decision.request

        # Validate request fields are nonblank after stripping
        if not (identifier := request.identifier.strip()):
            raise ApprovalValidationError("Approval request identifier cannot be blank")

        if not (checkpoint_id := request.checkpoint_id.strip()):
            raise ApprovalValidationError("Approval request checkpoint_id cannot be blank")

        if not (title := request.title.strip()):
            raise ApprovalValidationError("Approval request title cannot be blank")

        if not (requested_tool := request.requested_tool.strip()):
            raise ApprovalValidationError("Approval request requested_tool cannot be blank")

        if not (rationale := request.rationale.strip()):
            raise ApprovalValidationError("Approval request rationale cannot be blank")

        # Validate requested_command
        if not request.requested_command:
            raise ApprovalValidationError("Approval request requested_command must contain at least one item")

        # Check each command item is nonblank after stripping
        normalized_requested_command = []
        for cmd_item in request.requested_command:
            if not (cmd_item_stripped := cmd_item.strip()):
                raise ApprovalValidationError("Approval request requested_command items cannot be blank")
            normalized_requested_command.append(cmd_item_stripped)

        # Create normalized request
        normalized_request = ApprovalRequest(
            identifier=identifier,
            checkpoint_id=checkpoint_id,
            title=title,
            requested_tool=requested_tool,
            requested_command=tuple(normalized_requested_command),
            rationale=rationale,
        )

        # Validate the ApprovalDecision
        status = decision.status
        reviewer = decision.reviewer
        reason = decision.reason

        # PENDING validation
        if status == ApprovalStatus.PENDING:
            if reviewer is not None:
                raise ApprovalValidationError("Pending decisions must not have a reviewer")
        # APPROVED validation
        elif status == ApprovalStatus.APPROVED:
            if reviewer is None or not reviewer.strip():
                raise ApprovalValidationError("Approved decisions must have a nonblank reviewer")
        # REJECTED validation
        elif status == ApprovalStatus.REJECTED:
            if reviewer is None or not reviewer.strip():
                raise ApprovalValidationError("Rejected decisions must have a nonblank reviewer")
            if reason is None or not reason.strip():
                raise ApprovalValidationError("Rejected decisions must have a nonblank reason")

        # Normalize reviewer and reason
        normalized_reviewer = reviewer.strip() if reviewer is not None else None
        normalized_reason = reason.strip() if reason is not None else None

        # Create normalized decision
        normalized_decision = ApprovalDecision(
            request=normalized_request,
            status=status,
            reviewer=normalized_reviewer,
            reason=normalized_reason,
        )

        return ApprovalResult(decision=normalized_decision)
