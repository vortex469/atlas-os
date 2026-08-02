"""Candidate-specific commit validation for exact approved commits."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path

from app.approval.models import ApprovalRequest, ApprovalResult, ApprovalStatus
from app.candidate_planning.conversion import candidate_plan_fingerprint
from app.candidate_planning.execution import CandidatePlanningIntakeClient
from app.candidate_planning.models import CoreCandidatePlanningIntakeStatus
from app.candidate_planning.planner import RepositoryResolver
from app.candidate_planning.state import CandidatePlanningStateStore
from app.core_client.exceptions import AtlasCoreClientError
from app.repository.exceptions import RepositoryInspectionError
from app.repository.inspector import GitInspector
from app.repository.models import CommitRequest, CommitResult, RepositorySnapshot
from app.review.models import ReviewStatus
from app.verification.models import VerificationStatus
from app.workflow.models import WorkflowSession, WorkflowSessionState, WorkflowSource


class CandidateCommitFailureCode(StrEnum):
    """Stable candidate commit failure codes."""

    COMMIT_APPROVAL_MISSING = "commit_approval_missing"
    COMMIT_NOT_APPROVED = "commit_not_approved"
    COMMIT_APPROVAL_EVIDENCE_MISMATCH = "commit_approval_evidence_mismatch"
    REVIEWED_EVIDENCE_MISMATCH = "reviewed_evidence_mismatch"
    CHANGED_FILES_DRIFT = "changed_files_drift"
    REPOSITORY_STALE = "repository_stale"
    CANDIDATE_STALE = "candidate_stale"
    PLAN_STALE = "plan_stale"
    IMPLEMENTATION_REQUEST_MISMATCH = "implementation_request_mismatch"
    VERIFICATION_EVIDENCE_MISMATCH = "verification_evidence_mismatch"
    REVIEW_EVIDENCE_MISMATCH = "review_evidence_mismatch"
    CORE_UNAVAILABLE = "core_unavailable"
    COMMIT_FAILED = "commit_failed"
    COMMIT_RESULT_MISMATCH = "commit_result_mismatch"
    PERSISTENCE_FAILED = "persistence_failed"


@dataclass(frozen=True, slots=True)
class CandidateCommitValidationResult:
    """Candidate commit validation result."""

    approved: bool
    failure_code: CandidateCommitFailureCode | None = None
    retryable: bool = False
    should_block: bool = False
    commit_request: CommitRequest | None = None


class CandidateCommitValidator:
    """Validate exact candidate commit approval, artifacts, and repository freshness."""

    def __init__(
        self,
        *,
        core_client: CandidatePlanningIntakeClient,
        candidate_state: CandidatePlanningStateStore,
        repository_resolver: RepositoryResolver,
        repository_inspector_factory: Callable[[Path], GitInspector] = GitInspector,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._core_client = core_client
        self._candidate_state = candidate_state
        self._repository_resolver = repository_resolver
        self._repository_inspector_factory = repository_inspector_factory
        self._clock = clock or (lambda: datetime.now(UTC))

    def validate(
        self,
        *,
        workflow: WorkflowSession,
        approval_result: ApprovalResult | None,
        expected_approval: ApprovalRequest | None,
    ) -> CandidateCommitValidationResult:
        local = self._validate_local_artifacts(workflow)
        if not local.approved:
            return local
        commit_request = workflow.commit_request
        assert commit_request is not None

        approval = self._validate_approval(
            approval_result=approval_result,
            expected_approval=expected_approval,
        )
        if not approval.approved:
            return approval

        core = self._validate_core(workflow)
        if not core.approved:
            return core
        plan = self._validate_candidate_plan(workflow)
        if not plan.approved:
            return plan
        linkage = self._validate_candidate_linkage(workflow)
        if not linkage.approved:
            return linkage
        repository = self._validate_repository(workflow)
        if not repository.approved:
            return repository
        return CandidateCommitValidationResult(
            approved=True,
            commit_request=commit_request,
        )

    def validate_commit_result(
        self,
        *,
        workflow: WorkflowSession,
        commit_result: CommitResult,
    ) -> CandidateCommitValidationResult:
        commit_request = workflow.commit_request
        if commit_request is None:
            return _failure(CandidateCommitFailureCode.COMMIT_RESULT_MISMATCH, should_block=True)
        expected_paths = _normalized_paths(commit_request.paths)
        if not commit_result.commit_sha.strip():
            return _failure(CandidateCommitFailureCode.COMMIT_RESULT_MISMATCH, should_block=True)
        if not (
            commit_result.repository_root.resolve(strict=False)
            == commit_request.repository_root.resolve(strict=False)
            and commit_result.branch == commit_request.expected_branch
            and commit_result.parent_head == commit_request.expected_head
            and _normalized_paths(commit_result.committed_files) == expected_paths
            and commit_result.message == commit_request.message
        ):
            return _failure(CandidateCommitFailureCode.COMMIT_RESULT_MISMATCH, should_block=True)
        try:
            snapshot = self._repository_inspector_factory(
                commit_request.repository_root
            ).inspect()
        except (OSError, RepositoryInspectionError, ValueError):
            return _failure(CandidateCommitFailureCode.COMMIT_RESULT_MISMATCH, should_block=True)
        if snapshot.branch != commit_request.expected_branch:
            return _failure(CandidateCommitFailureCode.COMMIT_RESULT_MISMATCH, should_block=True)
        if snapshot.head_commit is not None and snapshot.head_commit != commit_result.commit_sha:
            return _failure(CandidateCommitFailureCode.COMMIT_RESULT_MISMATCH, should_block=True)
        return CandidateCommitValidationResult(approved=True, commit_request=commit_request)

    def _validate_local_artifacts(
        self,
        workflow: WorkflowSession,
    ) -> CandidateCommitValidationResult:
        if workflow.source is not WorkflowSource.CANDIDATE:
            return _failure(CandidateCommitFailureCode.COMMIT_APPROVAL_EVIDENCE_MISMATCH, should_block=True)
        if workflow.state is not WorkflowSessionState.AWAITING_COMMIT_APPROVAL:
            return _failure(CandidateCommitFailureCode.COMMIT_APPROVAL_EVIDENCE_MISMATCH, should_block=True)
        if (
            workflow.candidate_metadata is None
            or workflow.candidate_implementation_request is None
            or workflow.candidate_verification_plan is None
            or workflow.candidate_verification_evidence is None
            or workflow.candidate_review_result is None
            or workflow.verification_report is None
            or workflow.review_report is None
            or workflow.commit_request is None
            or not workflow.reviewed_files
            or workflow.expected_branch is None
            or workflow.expected_head is None
            or workflow.reviewed_content_fingerprint is None
            or workflow.plan is None
        ):
            return _failure(CandidateCommitFailureCode.COMMIT_APPROVAL_EVIDENCE_MISMATCH, should_block=True)
        if workflow.candidate_verification_evidence.status is not VerificationStatus.PASSED:
            return _failure(CandidateCommitFailureCode.VERIFICATION_EVIDENCE_MISMATCH, should_block=True)
        if workflow.verification_report.status is not VerificationStatus.PASSED:
            return _failure(CandidateCommitFailureCode.VERIFICATION_EVIDENCE_MISMATCH, should_block=True)
        if workflow.candidate_review_result.status is not ReviewStatus.APPROVED:
            return _failure(CandidateCommitFailureCode.REVIEW_EVIDENCE_MISMATCH, should_block=True)
        if workflow.review_report.status is not ReviewStatus.APPROVED:
            return _failure(CandidateCommitFailureCode.REVIEW_EVIDENCE_MISMATCH, should_block=True)
        return CandidateCommitValidationResult(approved=True, commit_request=workflow.commit_request)

    @staticmethod
    def _validate_approval(
        *,
        approval_result: ApprovalResult | None,
        expected_approval: ApprovalRequest | None,
    ) -> CandidateCommitValidationResult:
        if approval_result is None:
            return _failure(CandidateCommitFailureCode.COMMIT_APPROVAL_MISSING, retryable=True)
        if expected_approval is None:
            return _failure(CandidateCommitFailureCode.COMMIT_APPROVAL_EVIDENCE_MISMATCH, should_block=True)
        if approval_result.decision.request != expected_approval:
            return _failure(CandidateCommitFailureCode.COMMIT_APPROVAL_EVIDENCE_MISMATCH, should_block=True)
        if approval_result.decision.status is ApprovalStatus.PENDING:
            return _failure(CandidateCommitFailureCode.COMMIT_NOT_APPROVED, retryable=True)
        if approval_result.decision.status is not ApprovalStatus.APPROVED:
            return _failure(CandidateCommitFailureCode.COMMIT_NOT_APPROVED, should_block=True)
        return CandidateCommitValidationResult(approved=True)

    def _validate_core(self, workflow: WorkflowSession) -> CandidateCommitValidationResult:
        request = workflow.candidate_implementation_request
        metadata = workflow.candidate_metadata
        if request is None or metadata is None:
            return _failure(CandidateCommitFailureCode.CANDIDATE_STALE, should_block=True)
        try:
            intake = asyncio.run(
                self._core_client.validate_candidate_planning_intake(
                    request.candidate_id,
                    expected_candidate_fingerprint=request.candidate_fingerprint,
                )
            )
        except (AtlasCoreClientError, RuntimeError):
            return _failure(CandidateCommitFailureCode.CORE_UNAVAILABLE, retryable=True)
        if intake.status != CoreCandidatePlanningIntakeStatus.ACCEPTED_FOR_PLANNING.value:
            return _failure(CandidateCommitFailureCode.CANDIDATE_STALE, should_block=True)
        candidate = intake.current_candidate
        if candidate is None or intake.current_candidate_fingerprint is None:
            return _failure(CandidateCommitFailureCode.CANDIDATE_STALE, should_block=True)
        if candidate.expires_at is not None and candidate.expires_at <= self._clock():
            return _failure(CandidateCommitFailureCode.CANDIDATE_STALE, should_block=True)
        session = self._candidate_state.get_session(request.candidate_planning_session_id)
        required_level = session.snapshot.required_approval_level if session is not None else None
        if not (
            intake.candidate_id == request.candidate_id
            and candidate.id == request.candidate_id
            and intake.current_candidate_fingerprint == request.candidate_fingerprint
            and candidate.target_id == metadata.target_id
            and candidate.target_type == metadata.target_type
            and candidate.execution_category == metadata.execution_category
            and candidate.execution_intent == metadata.execution_intent
            and candidate.required_approval_level == required_level
            and tuple(sorted(candidate.evidence_ids)) == metadata.evidence_ids
            and candidate.compatibility_assessment_id == metadata.compatibility_assessment_id
            and candidate.compatibility_status == metadata.compatibility_status
            and tuple(sorted(candidate.relationship_ids)) == metadata.relationship_ids
        ):
            return _failure(CandidateCommitFailureCode.CANDIDATE_STALE, should_block=True)
        return CandidateCommitValidationResult(approved=True)

    def _validate_candidate_plan(self, workflow: WorkflowSession) -> CandidateCommitValidationResult:
        request = workflow.candidate_implementation_request
        metadata = workflow.candidate_metadata
        if request is None or metadata is None:
            return _failure(CandidateCommitFailureCode.PLAN_STALE, should_block=True)
        session = self._candidate_state.get_session(request.candidate_planning_session_id)
        if session is None or session.workflow_session_id != workflow.identifier or session.plan is None:
            return _failure(CandidateCommitFailureCode.PLAN_STALE, should_block=True)
        recomputed = candidate_plan_fingerprint(session.plan)
        if not (
            recomputed == request.candidate_plan_fingerprint
            and recomputed == metadata.candidate_plan_fingerprint
            and recomputed == session.candidate_plan_fingerprint
        ):
            return _failure(CandidateCommitFailureCode.PLAN_STALE, should_block=True)
        return CandidateCommitValidationResult(approved=True)

    def _validate_candidate_linkage(self, workflow: WorkflowSession) -> CandidateCommitValidationResult:
        metadata = workflow.candidate_metadata
        request = workflow.candidate_implementation_request
        verification_plan = workflow.candidate_verification_plan
        verification_evidence = workflow.candidate_verification_evidence
        review_result = workflow.candidate_review_result
        commit_request = workflow.commit_request
        if not all((metadata, request, verification_plan, verification_evidence, review_result, commit_request)):
            return _failure(CandidateCommitFailureCode.COMMIT_APPROVAL_EVIDENCE_MISMATCH, should_block=True)
        assert metadata is not None
        assert request is not None
        assert verification_plan is not None
        assert verification_evidence is not None
        assert review_result is not None
        assert commit_request is not None
        if not (
            metadata.candidate_planning_session_id == request.candidate_planning_session_id
            and metadata.candidate_id == request.candidate_id
            and metadata.candidate_fingerprint == request.candidate_fingerprint
            and metadata.candidate_plan_id == request.candidate_plan_id
            and metadata.candidate_plan_fingerprint == request.candidate_plan_fingerprint
        ):
            return _failure(CandidateCommitFailureCode.IMPLEMENTATION_REQUEST_MISMATCH, should_block=True)
        if not (
            verification_plan.workflow_session_id == workflow.identifier
            and verification_plan.candidate_planning_session_id == request.candidate_planning_session_id
            and verification_plan.candidate_id == request.candidate_id
            and verification_plan.candidate_fingerprint == request.candidate_fingerprint
            and verification_plan.candidate_plan_id == request.candidate_plan_id
            and verification_plan.candidate_plan_fingerprint == request.candidate_plan_fingerprint
            and verification_plan.implementation_request_id == request.identifier
            and verification_plan.repository_root == request.repository_root
            and verification_plan.repository_branch == request.repository_branch
            and verification_plan.base_head == request.repository_head
        ):
            return _failure(CandidateCommitFailureCode.VERIFICATION_EVIDENCE_MISMATCH, should_block=True)
        if not (
            verification_evidence.verification_plan_id == verification_plan.identifier
            and verification_evidence.workflow_id == workflow.identifier
            and verification_evidence.candidate_id == request.candidate_id
            and verification_evidence.candidate_fingerprint == request.candidate_fingerprint
            and verification_evidence.plan_fingerprint == request.candidate_plan_fingerprint
            and verification_evidence.implementation_request_id == request.identifier
            and verification_evidence.changed_files_digest == verification_plan.changed_files_digest
        ):
            return _failure(CandidateCommitFailureCode.VERIFICATION_EVIDENCE_MISMATCH, should_block=True)
        if not (
            review_result.workflow_id == workflow.identifier
            and review_result.verification_plan_id == verification_plan.identifier
            and review_result.verification_evidence_id == verification_evidence.identifier
            and review_result.reviewed_content_fingerprint == workflow.reviewed_content_fingerprint
        ):
            return _failure(CandidateCommitFailureCode.REVIEW_EVIDENCE_MISMATCH, should_block=True)
        try:
            reviewed = _normalized_paths(workflow.reviewed_files)
            commit_paths = _normalized_paths(commit_request.paths)
            plan_changed = _normalized_paths(verification_plan.changed_files)
            affected = _normalized_paths(request.affected_files)
        except ValueError:
            return _failure(CandidateCommitFailureCode.REVIEW_EVIDENCE_MISMATCH, should_block=True)
        if not (
            reviewed == commit_paths
            and reviewed == plan_changed
            and _paths_within_scope(reviewed, affected)
            and commit_request.expected_branch == workflow.expected_branch == verification_plan.repository_branch
            and commit_request.expected_head == workflow.expected_head == verification_plan.base_head
            and commit_request.repository_root == verification_plan.repository_root
        ):
            return _failure(CandidateCommitFailureCode.REVIEW_EVIDENCE_MISMATCH, should_block=True)
        return CandidateCommitValidationResult(approved=True)

    def _validate_repository(self, workflow: WorkflowSession) -> CandidateCommitValidationResult:
        request = workflow.candidate_implementation_request
        commit_request = workflow.commit_request
        if request is None or commit_request is None:
            return _failure(CandidateCommitFailureCode.REPOSITORY_STALE, should_block=True)
        session = self._candidate_state.get_session(request.candidate_planning_session_id)
        if session is None:
            return _failure(CandidateCommitFailureCode.REPOSITORY_STALE, should_block=True)
        resolved = self._repository_resolver.resolve(
            target_id=session.snapshot.target_id,
            target_type=session.snapshot.target_type,
        )
        if resolved is None:
            return _failure(CandidateCommitFailureCode.REPOSITORY_STALE, should_block=True)
        trusted_root = resolved.resolve(strict=False)
        if trusted_root != commit_request.repository_root.resolve(strict=False):
            return _failure(CandidateCommitFailureCode.REPOSITORY_STALE, should_block=True)
        try:
            snapshot = self._repository_inspector_factory(trusted_root).inspect()
        except (OSError, RepositoryInspectionError, ValueError):
            return _failure(CandidateCommitFailureCode.REPOSITORY_STALE, should_block=True)
        if not _snapshot_matches_commit(snapshot, commit_request):
            return _failure(CandidateCommitFailureCode.REPOSITORY_STALE, should_block=True)
        try:
            reviewed = _normalized_paths(workflow.reviewed_files)
            actual = _normalized_paths(_snapshot_changed_files(snapshot))
        except ValueError:
            return _failure(CandidateCommitFailureCode.CHANGED_FILES_DRIFT, should_block=True)
        if actual != reviewed:
            return _failure(CandidateCommitFailureCode.CHANGED_FILES_DRIFT, should_block=True)
        for path in reviewed:
            if path.parts and path.parts[0] in {"jcode", "logs"}:
                return _failure(CandidateCommitFailureCode.CHANGED_FILES_DRIFT, should_block=True)
        try:
            evidence = self._repository_inspector_factory(trusted_root).reviewed_change_evidence(
                reviewed_files=reviewed,
                expected_branch=workflow.expected_branch,
                expected_head=workflow.expected_head,
                commit_message=commit_request.message,
                excluded_roots=(),
            )
        except (OSError, RepositoryInspectionError, ValueError):
            return _failure(CandidateCommitFailureCode.REVIEWED_EVIDENCE_MISMATCH, should_block=True)
        if evidence.fingerprint != workflow.reviewed_content_fingerprint:
            return _failure(CandidateCommitFailureCode.REVIEWED_EVIDENCE_MISMATCH, should_block=True)
        return CandidateCommitValidationResult(approved=True)


def _snapshot_matches_commit(snapshot: RepositorySnapshot, request: CommitRequest) -> bool:
    return (
        snapshot.root == request.repository_root.resolve(strict=False)
        and snapshot.branch == request.expected_branch
        and snapshot.head_commit == request.expected_head
    )


def _snapshot_changed_files(snapshot: RepositorySnapshot) -> tuple[Path, ...]:
    return tuple(Path(path) for path in (*snapshot.modified_files, *snapshot.staged_files, *snapshot.untracked_files))


def _normalized_paths(paths: tuple[Path, ...]) -> tuple[Path, ...]:
    normalized: list[Path] = []
    seen: set[Path] = set()
    for path in paths:
        if path.is_absolute() or path == Path(".") or ".." in path.parts:
            raise ValueError("Path must be repository-relative and safe")
        if path not in seen:
            normalized.append(path)
            seen.add(path)
    return tuple(sorted(normalized, key=lambda item: item.as_posix()))


def _paths_within_scope(changed_files: tuple[Path, ...], approved_files: tuple[Path, ...]) -> bool:
    approved = set(approved_files)
    for changed in changed_files:
        if changed not in approved and not any(
            changed.is_relative_to(scope) for scope in approved if scope.suffix == ""
        ):
            return False
    return True


def _failure(
    code: CandidateCommitFailureCode,
    *,
    retryable: bool = False,
    should_block: bool = False,
) -> CandidateCommitValidationResult:
    return CandidateCommitValidationResult(
        approved=False,
        failure_code=code,
        retryable=retryable,
        should_block=should_block,
    )
