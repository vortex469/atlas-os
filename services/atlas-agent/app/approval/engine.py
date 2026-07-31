"""Approval engine for Atlas Agent."""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.approval.exceptions import ApprovalValidationError
from app.approval.models import (
    ApprovalDecision,
    ApprovalPurpose,
    ApprovalRequest,
    ApprovalResult,
    ApprovalStatus,
    VerificationApprovalCheck,
    VerificationApprovalEnvironment,
)

_SHA256_DIGEST = re.compile(r"[0-9a-f]{64}\Z")


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
            workflow_id=(
                request.workflow_id.strip()
                if request.workflow_id is not None
                else None
            ),
            requested_working_directory=request.requested_working_directory,
            purpose=request.purpose,
            verification_checks=self._normalize_verification_checks(request),
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

    @staticmethod
    def _normalize_verification_checks(
        request: ApprovalRequest,
    ) -> tuple[VerificationApprovalCheck, ...]:
        if request.purpose is not ApprovalPurpose.VERIFICATION:
            if request.verification_checks:
                raise ApprovalValidationError(
                    "Only verification approvals may contain verification checks"
                )
            return ()

        if request.workflow_id is None or not request.workflow_id.strip():
            raise ApprovalValidationError(
                "Verification approvals require a workflow_id"
            )
        if not request.verification_checks:
            raise ApprovalValidationError(
                "Verification approvals require at least one check"
            )

        normalized: list[VerificationApprovalCheck] = []
        identifiers: set[str] = set()
        for check in request.verification_checks:
            identifier = check.identifier.strip()
            if not identifier:
                raise ApprovalValidationError(
                    "Verification approval check identifier cannot be blank"
                )
            if identifier in identifiers:
                raise ApprovalValidationError(
                    "Verification approval check identifiers must be unique"
                )
            if not check.command or any(
                not argument.strip() for argument in check.command
            ):
                raise ApprovalValidationError(
                    "Verification approval commands must contain nonblank items"
                )
            if (
                check.timeout_seconds is not None
                and check.timeout_seconds <= 0
            ):
                raise ApprovalValidationError(
                    "Verification approval timeout must be positive"
                )

            environment: list[VerificationApprovalEnvironment] = []
            environment_names: set[str] = set()
            for variable in check.environment:
                name = variable.name.strip()
                if not name or name in environment_names:
                    raise ApprovalValidationError(
                        "Verification approval environment names must be "
                        "nonblank and unique"
                    )
                if _SHA256_DIGEST.fullmatch(variable.value_digest) is None:
                    raise ApprovalValidationError(
                        "Verification approval environment digests must be "
                        "lowercase SHA-256 values"
                    )
                environment_names.add(name)
                environment.append(
                    VerificationApprovalEnvironment(
                        name=name,
                        value_digest=variable.value_digest,
                    )
                )

            identifiers.add(identifier)
            normalized.append(
                VerificationApprovalCheck(
                    identifier=identifier,
                    command=tuple(argument.strip() for argument in check.command),
                    working_directory=check.working_directory,
                    timeout_seconds=check.timeout_seconds,
                    environment=tuple(environment),
                )
            )

        return tuple(normalized)
