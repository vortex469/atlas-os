"""Approval engine for Atlas Agent."""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from app.approval.exceptions import ApprovalValidationError
from app.approval.models import (
    ApprovalDecision,
    ApprovalPurpose,
    ApprovalRequest,
    ApprovalResult,
    ApprovalStatus,
    CommitApprovalMetadata,
    OperationalApprovalMetadata,
    VerificationApprovalCheck,
    VerificationApprovalEnvironment,
)

_SHA256_DIGEST = re.compile(r"[0-9a-f]{64}\Z")


@dataclass(frozen=True, slots=True)
class ApprovalEngine:
    """Engine for validating and normalizing approval decisions."""

    clock: Callable[[], datetime] = lambda: datetime.now(UTC)

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
        if (
            not request.requested_command
            and request.purpose
            not in {
                ApprovalPurpose.CANDIDATE_WORKFLOW_SHELL,
                ApprovalPurpose.OPERATIONAL_ACTION,
            }
        ):
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
            commit_metadata=self._normalize_commit_metadata(request),
            operational_metadata=self._normalize_operational_metadata(request),
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
            if (
                request.purpose is ApprovalPurpose.OPERATIONAL_ACTION
                and request.operational_metadata is not None
                and request.operational_metadata.expires_at <= self.clock()
            ):
                raise ApprovalValidationError("Operational approval request has expired")
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

    @staticmethod
    def _normalize_commit_metadata(
        request: ApprovalRequest,
    ) -> CommitApprovalMetadata | None:
        if request.purpose is not ApprovalPurpose.COMMIT:
            if request.commit_metadata is not None:
                raise ApprovalValidationError(
                    "Only commit approvals may contain commit metadata"
                )
            return None

        if request.workflow_id is None or not request.workflow_id.strip():
            raise ApprovalValidationError("Commit approvals require a workflow_id")
        if request.verification_checks:
            raise ApprovalValidationError(
                "Commit approvals must not contain verification checks"
            )
        metadata = request.commit_metadata
        if metadata is None:
            raise ApprovalValidationError(
                "Commit approvals require commit metadata"
            )
        if not metadata.reviewed_files:
            raise ApprovalValidationError(
                "Commit approval reviewed files must not be empty"
            )
        normalized_files = []
        for path in metadata.reviewed_files:
            if path.is_absolute() or path == Path(".") or ".." in path.parts:
                raise ApprovalValidationError(
                    "Commit approval reviewed files must be repository-relative"
                )
            if path in normalized_files:
                raise ApprovalValidationError(
                    "Commit approval reviewed files must be unique"
                )
            normalized_files.append(path)
        if _SHA256_DIGEST.fullmatch(metadata.reviewed_content_fingerprint) is None:
            raise ApprovalValidationError(
                "Commit approval fingerprints must be lowercase SHA-256 values"
            )
        commit_message = " ".join(metadata.commit_message.split())
        if not commit_message:
            raise ApprovalValidationError(
                "Commit approval commit message must not be blank"
            )
        if commit_message != metadata.commit_message:
            raise ApprovalValidationError(
                "Commit approval commit message must already be normalized"
            )

        return CommitApprovalMetadata(
            expected_branch=metadata.expected_branch,
            expected_head=metadata.expected_head,
            reviewed_files=tuple(sorted(normalized_files)),
            reviewed_content_fingerprint=metadata.reviewed_content_fingerprint,
            commit_message=commit_message,
        )

    @staticmethod
    def _normalize_operational_metadata(
        request: ApprovalRequest,
    ) -> OperationalApprovalMetadata | None:
        metadata = request.operational_metadata
        if request.purpose is not ApprovalPurpose.OPERATIONAL_ACTION:
            if metadata is not None:
                raise ApprovalValidationError(
                    "Only operational action approvals may contain operational metadata"
                )
            return None
        if request.commit_metadata is not None or request.verification_checks:
            raise ApprovalValidationError(
                "Operational action approvals cannot contain repository approval metadata"
            )
        if request.requested_command or request.requested_working_directory is not None:
            raise ApprovalValidationError(
                "Operational action approvals cannot contain executable fields"
            )
        if request.workflow_id is None or not request.workflow_id.strip():
            raise ApprovalValidationError(
                "Operational action approvals require a workflow_id"
            )
        if metadata is None:
            raise ApprovalValidationError(
                "Operational action approvals require operational metadata"
            )
        required = (
            metadata.action_request_id,
            metadata.action_request_digest,
            metadata.candidate_id,
            metadata.candidate_fingerprint,
            metadata.operational_plan_fingerprint,
            metadata.provider_id,
            metadata.resource_id,
            metadata.resource_type,
            metadata.target_fingerprint,
            metadata.operation_intent,
            metadata.disruption_scope,
            metadata.verification_digest,
        )
        if any(not value.strip() for value in required):
            raise ApprovalValidationError(
                "Operational approval metadata fields must not be blank"
            )
        if metadata.expires_at <= metadata.generated_at:
            raise ApprovalValidationError(
                "Operational approval expiry must follow generation time"
            )
        return metadata
