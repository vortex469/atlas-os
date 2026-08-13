"""Machine-readable audit-chain validation for candidate workflows."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from app.approval.models import ApprovalPurpose, ApprovalResult, ApprovalStatus
from app.candidate_planning.models import CandidatePlanningSession
from app.repository.models import CommitResult
from app.workflow.models import WorkflowSession, WorkflowSessionState, WorkflowSource


class CandidateAuditFailureCode(StrEnum):
    """Stable candidate audit-chain validation failure codes."""

    NOT_CANDIDATE_WORKFLOW = "not_candidate_workflow"
    MISSING_CANDIDATE_METADATA = "missing_candidate_metadata"
    MISSING_PLANNING_SESSION = "missing_planning_session"
    MISSING_CANDIDATE_PLAN = "missing_candidate_plan"
    MISSING_IMPLEMENTATION_REQUEST = "missing_implementation_request"
    MISSING_IMPLEMENTATION_APPROVAL = "missing_implementation_approval"
    MISSING_EXECUTION_RESULT = "missing_execution_result"
    MISSING_VERIFICATION_PLAN = "missing_verification_plan"
    MISSING_VERIFICATION_APPROVAL = "missing_verification_approval"
    MISSING_VERIFICATION_EVIDENCE = "missing_verification_evidence"
    MISSING_REVIEW_RESULT = "missing_review_result"
    MISSING_REVIEW_REPORT = "missing_review_report"
    MISSING_COMMIT_REQUEST = "missing_commit_request"
    MISSING_COMMIT_APPROVAL = "missing_commit_approval"
    MISSING_COMMIT_RESULT = "missing_commit_result"
    IDENTITY_MISMATCH = "identity_mismatch"
    FINGERPRINT_MISMATCH = "fingerprint_mismatch"
    APPROVAL_MISMATCH = "approval_mismatch"
    EXECUTION_MISMATCH = "execution_mismatch"
    VERIFICATION_MISMATCH = "verification_mismatch"
    REVIEW_MISMATCH = "review_mismatch"
    COMMIT_MISMATCH = "commit_mismatch"
    DUPLICATE_IDENTIFIER = "duplicate_identifier"


@dataclass(frozen=True, slots=True)
class CandidateAuditChain:
    """Machine-readable candidate workflow audit identity chain."""

    candidate_id: str
    candidate_fingerprint: str
    source_recommendation_id: str
    candidate_planning_session_id: str
    candidate_plan_id: str
    candidate_plan_fingerprint: str
    workflow_id: str
    implementation_request_id: str | None = None
    implementation_approval_id: str | None = None
    execution_result_id: str | None = None
    verification_plan_id: str | None = None
    verification_approval_id: str | None = None
    verification_evidence_id: str | None = None
    review_result_id: str | None = None
    review_report_id: str | None = None
    commit_approval_id: str | None = None
    commit_sha: str | None = None
    committed_files: tuple[Path, ...] = ()


@dataclass(frozen=True, slots=True)
class CandidateAuditValidationResult:
    """Result of deterministic candidate audit-chain validation."""

    valid: bool
    chain: CandidateAuditChain | None = None
    failure_code: CandidateAuditFailureCode | None = None


@dataclass(frozen=True, slots=True)
class CandidateAuditApprovals:
    """Approval decisions bound to one candidate workflow audit chain."""

    implementation: ApprovalResult | None = None
    verification: ApprovalResult | None = None
    commit: ApprovalResult | None = None


class CandidateAuditChainValidator:
    """Validate candidate workflow artifacts using only structured identifiers."""

    def validate(
        self,
        *,
        planning_session: CandidatePlanningSession | None,
        workflow: WorkflowSession,
        approvals: CandidateAuditApprovals | None = None,
        require_complete: bool | None = None,
    ) -> CandidateAuditValidationResult:
        approvals = approvals or CandidateAuditApprovals()
        if workflow.source is not WorkflowSource.CANDIDATE:
            return _failure(CandidateAuditFailureCode.NOT_CANDIDATE_WORKFLOW)
        metadata = workflow.candidate_metadata
        if metadata is None:
            return _failure(CandidateAuditFailureCode.MISSING_CANDIDATE_METADATA)
        if planning_session is None:
            return _failure(CandidateAuditFailureCode.MISSING_PLANNING_SESSION)
        if planning_session.plan is None:
            return _failure(CandidateAuditFailureCode.MISSING_CANDIDATE_PLAN)
        if not _same(
            planning_session.identifier,
            metadata.candidate_planning_session_id,
        ) or not _same(planning_session.candidate_id, metadata.candidate_id):
            return _failure(CandidateAuditFailureCode.IDENTITY_MISMATCH)
        if not _same(planning_session.candidate_fingerprint, metadata.candidate_fingerprint):
            return _failure(CandidateAuditFailureCode.FINGERPRINT_MISMATCH)
        plan = planning_session.plan
        if not _same(plan.identifier, metadata.candidate_plan_id) or not _same(
            plan.candidate_id,
            metadata.candidate_id,
        ):
            return _failure(CandidateAuditFailureCode.IDENTITY_MISMATCH)
        if not _same(plan.candidate_fingerprint, metadata.candidate_fingerprint):
            return _failure(CandidateAuditFailureCode.FINGERPRINT_MISMATCH)
        if planning_session.candidate_plan_fingerprint not in (None, metadata.candidate_plan_fingerprint):
            return _failure(CandidateAuditFailureCode.FINGERPRINT_MISMATCH)

        require_complete = workflow.state is WorkflowSessionState.COMPLETED if require_complete is None else require_complete
        request = workflow.candidate_implementation_request
        if request is None:
            return _maybe_incomplete(require_complete, CandidateAuditFailureCode.MISSING_IMPLEMENTATION_REQUEST, metadata, workflow)
        request_check = _validate_request(metadata, workflow, request)
        if request_check is not None:
            return _failure(request_check)

        implementation_approval_id = workflow.candidate_implementation_approval_id
        if approvals.implementation is None:
            return _maybe_incomplete(require_complete, CandidateAuditFailureCode.MISSING_IMPLEMENTATION_APPROVAL, metadata, workflow, request.identifier, implementation_approval_id)
        approval_check = _validate_approval(
            approvals.implementation,
            expected_id=implementation_approval_id,
            workflow_id=workflow.identifier,
            purpose=ApprovalPurpose.IMPLEMENTATION,
        )
        if approval_check is not None:
            return _failure(approval_check)

        execution = workflow.execution_result
        if execution is None:
            return _maybe_incomplete(require_complete, CandidateAuditFailureCode.MISSING_EXECUTION_RESULT, metadata, workflow, request.identifier, implementation_approval_id)
        if execution.request_id != request.identifier:
            return _failure(CandidateAuditFailureCode.EXECUTION_MISMATCH)

        verification_plan = workflow.candidate_verification_plan
        if verification_plan is None:
            return _maybe_incomplete(require_complete, CandidateAuditFailureCode.MISSING_VERIFICATION_PLAN, metadata, workflow, request.identifier, implementation_approval_id, execution.request_id)
        if not (
            verification_plan.workflow_session_id == workflow.identifier
            and verification_plan.candidate_planning_session_id == metadata.candidate_planning_session_id
            and verification_plan.candidate_id == metadata.candidate_id
            and verification_plan.candidate_fingerprint == metadata.candidate_fingerprint
            and verification_plan.candidate_plan_id == metadata.candidate_plan_id
            and verification_plan.candidate_plan_fingerprint == metadata.candidate_plan_fingerprint
            and verification_plan.implementation_request_id == request.identifier
            and verification_plan.execution_result_id == execution.request_id
        ):
            return _failure(CandidateAuditFailureCode.VERIFICATION_MISMATCH)

        if approvals.verification is None:
            return _maybe_incomplete(require_complete, CandidateAuditFailureCode.MISSING_VERIFICATION_APPROVAL, metadata, workflow, request.identifier, implementation_approval_id, execution.request_id, verification_plan.identifier)
        approval_check = _validate_approval(
            approvals.verification,
            expected_id=f"approval-verification-{workflow.identifier}",
            workflow_id=workflow.identifier,
            purpose=ApprovalPurpose.VERIFICATION,
            allow_pending=workflow.state
            in {
                WorkflowSessionState.PATCH_APPLIED_PENDING_VERIFICATION,
                WorkflowSessionState.AWAITING_VERIFICATION_APPROVAL,
            },
        )
        if approval_check is not None:
            return _failure(approval_check)

        evidence = workflow.candidate_verification_evidence
        if evidence is None:
            return _maybe_incomplete(require_complete, CandidateAuditFailureCode.MISSING_VERIFICATION_EVIDENCE, metadata, workflow, request.identifier, implementation_approval_id, execution.request_id, verification_plan.identifier, approvals.verification.decision.request.identifier)
        if not (
            evidence.verification_plan_id == verification_plan.identifier
            and evidence.workflow_id == workflow.identifier
            and evidence.candidate_id == metadata.candidate_id
            and evidence.candidate_fingerprint == metadata.candidate_fingerprint
            and evidence.plan_fingerprint == metadata.candidate_plan_fingerprint
            and evidence.implementation_request_id == request.identifier
            and evidence.changed_files_digest == verification_plan.changed_files_digest
        ):
            return _failure(CandidateAuditFailureCode.VERIFICATION_MISMATCH)

        review_result = workflow.candidate_review_result
        if review_result is None:
            return _maybe_incomplete(require_complete, CandidateAuditFailureCode.MISSING_REVIEW_RESULT, metadata, workflow)
        if not (
            review_result.workflow_id == workflow.identifier
            and review_result.verification_plan_id == verification_plan.identifier
            and review_result.verification_evidence_id == evidence.identifier
        ):
            return _failure(CandidateAuditFailureCode.REVIEW_MISMATCH)
        if workflow.review_report is None:
            return _maybe_incomplete(require_complete, CandidateAuditFailureCode.MISSING_REVIEW_REPORT, metadata, workflow)

        commit_request = workflow.commit_request
        if commit_request is None:
            return _maybe_incomplete(require_complete, CandidateAuditFailureCode.MISSING_COMMIT_REQUEST, metadata, workflow)
        if approvals.commit is None:
            return _maybe_incomplete(require_complete, CandidateAuditFailureCode.MISSING_COMMIT_APPROVAL, metadata, workflow)
        approval_check = _validate_approval(
            approvals.commit,
            expected_id=f"approval-commit-{workflow.identifier}",
            workflow_id=workflow.identifier,
            purpose=ApprovalPurpose.COMMIT,
            allow_pending=workflow.state is WorkflowSessionState.AWAITING_COMMIT_APPROVAL,
        )
        if approval_check is not None:
            return _failure(approval_check)
        commit_metadata = approvals.commit.decision.request.commit_metadata
        if commit_metadata is None or tuple(sorted(commit_request.paths)) != commit_metadata.reviewed_files:
            return _failure(CandidateAuditFailureCode.COMMIT_MISMATCH)

        commit_result = workflow.commit_result
        if commit_result is None:
            return _maybe_incomplete(require_complete, CandidateAuditFailureCode.MISSING_COMMIT_RESULT, metadata, workflow)
        commit_check = _validate_commit_result(commit_request_paths=commit_request.paths, commit_result=commit_result)
        if commit_check is not None:
            return _failure(commit_check)

        chain = _chain(
            metadata,
            workflow,
            implementation_request_id=request.identifier,
            implementation_approval_id=implementation_approval_id,
            execution_result_id=execution.request_id,
            verification_plan_id=verification_plan.identifier,
            verification_approval_id=approvals.verification.decision.request.identifier,
            verification_evidence_id=evidence.identifier,
            review_result_id=review_result.identifier,
            review_report_id=workflow.review_report.request_id,
            commit_approval_id=approvals.commit.decision.request.identifier,
            commit_sha=commit_result.commit_sha,
            committed_files=commit_result.committed_files,
        )
        duplicate = _duplicate_identifier(chain)
        if duplicate:
            return _failure(CandidateAuditFailureCode.DUPLICATE_IDENTIFIER)
        return CandidateAuditValidationResult(valid=True, chain=chain)


def _validate_request(metadata, workflow, request) -> CandidateAuditFailureCode | None:
    if not (
        request.workflow_session_id == workflow.identifier
        and request.candidate_planning_session_id == metadata.candidate_planning_session_id
        and request.candidate_id == metadata.candidate_id
        and request.candidate_plan_id == metadata.candidate_plan_id
    ):
        return CandidateAuditFailureCode.IDENTITY_MISMATCH
    if not (
        request.candidate_fingerprint == metadata.candidate_fingerprint
        and request.candidate_plan_fingerprint == metadata.candidate_plan_fingerprint
    ):
        return CandidateAuditFailureCode.FINGERPRINT_MISMATCH
    return None


def _validate_approval(
    result: ApprovalResult,
    *,
    expected_id: str | None,
    workflow_id: str,
    purpose: ApprovalPurpose,
    allow_pending: bool = False,
) -> CandidateAuditFailureCode | None:
    request = result.decision.request
    if expected_id is not None and request.identifier != expected_id:
        return CandidateAuditFailureCode.APPROVAL_MISMATCH
    if request.workflow_id != workflow_id or request.purpose is not purpose:
        return CandidateAuditFailureCode.APPROVAL_MISMATCH
    if (
        result.decision.status is ApprovalStatus.PENDING
        and (purpose is ApprovalPurpose.IMPLEMENTATION or allow_pending)
    ):
        return None
    if result.decision.status is not ApprovalStatus.APPROVED:
        return CandidateAuditFailureCode.APPROVAL_MISMATCH
    return None


def _validate_commit_result(*, commit_request_paths: tuple[Path, ...], commit_result: CommitResult) -> CandidateAuditFailureCode | None:
    if not commit_result.commit_sha.strip():
        return CandidateAuditFailureCode.COMMIT_MISMATCH
    if tuple(sorted(commit_request_paths)) != tuple(sorted(commit_result.committed_files)):
        return CandidateAuditFailureCode.COMMIT_MISMATCH
    return None


def _maybe_incomplete(
    require_complete: bool,
    code: CandidateAuditFailureCode,
    metadata,
    workflow,
    implementation_request_id: str | None = None,
    implementation_approval_id: str | None = None,
    execution_result_id: str | None = None,
    verification_plan_id: str | None = None,
    verification_approval_id: str | None = None,
) -> CandidateAuditValidationResult:
    if require_complete:
        return _failure(code)
    return CandidateAuditValidationResult(
        valid=True,
        chain=_chain(
            metadata,
            workflow,
            implementation_request_id=implementation_request_id,
            implementation_approval_id=implementation_approval_id,
            execution_result_id=execution_result_id,
            verification_plan_id=verification_plan_id,
            verification_approval_id=verification_approval_id,
        ),
    )


def _chain(metadata, workflow, **overrides) -> CandidateAuditChain:
    return CandidateAuditChain(
        candidate_id=metadata.candidate_id,
        candidate_fingerprint=metadata.candidate_fingerprint,
        source_recommendation_id=metadata.source_recommendation_id,
        candidate_planning_session_id=metadata.candidate_planning_session_id,
        candidate_plan_id=metadata.candidate_plan_id,
        candidate_plan_fingerprint=metadata.candidate_plan_fingerprint,
        workflow_id=workflow.identifier,
        **overrides,
    )


def _duplicate_identifier(chain: CandidateAuditChain) -> bool:
    values = [
        chain.candidate_planning_session_id,
        chain.candidate_plan_id,
        chain.workflow_id,
        chain.implementation_request_id,
        chain.implementation_approval_id,
        chain.verification_plan_id,
        chain.verification_approval_id,
        chain.verification_evidence_id,
        chain.review_result_id,
        chain.commit_approval_id,
        chain.commit_sha,
    ]
    present = [value for value in values if value]
    return len(present) != len(set(present))


def _same(left: str | None, right: str | None) -> bool:
    return left is not None and left == right


def _failure(code: CandidateAuditFailureCode) -> CandidateAuditValidationResult:
    return CandidateAuditValidationResult(valid=False, failure_code=code)
