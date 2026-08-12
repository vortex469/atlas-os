"""Candidate-specific verification and deterministic review boundaries."""

from __future__ import annotations

import asyncio
import json
import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from hashlib import sha256
from pathlib import Path

from app.approval.models import (
    ApprovalPurpose,
    ApprovalRequest,
    ApprovalResult,
    ApprovalStatus,
    VerificationApprovalCheck,
)
from app.candidate_planning.conversion import candidate_plan_fingerprint
from app.candidate_planning.execution import CandidatePlanningIntakeClient
from app.candidate_planning.models import (
    RC1_VALIDATION_SMOKE_INTENT,
    CandidateImplementationRequest,
    CoreCandidatePlanningIntakeStatus,
    is_supported_execution_intent,
)
from app.candidate_planning.planner import RepositoryResolver
from app.candidate_planning.state import CandidatePlanningStateStore
from app.core_client.exceptions import AtlasCoreClientError
from app.repository.exceptions import RepositoryInspectionError
from app.repository.inspector import GitInspector
from app.repository.models import RepositorySnapshot
from app.review.engine import ReviewEngine
from app.review.exceptions import ReviewValidationError
from app.review.models import ReviewReport, ReviewRequest, ReviewStatus
from app.verification.models import (
    VerificationCheck,
    VerificationCheckResult,
    VerificationReport,
    VerificationStatus,
)
from app.workflow.models import WorkflowSession, WorkflowSessionState, WorkflowSource

VERIFIER_VERSION = "candidate-update-compose-stack-verifier-v1"
COMPOSE_CHECK_ID = "compose-production-config"
_INTERNAL_CHECKS = ("changed-files-within-scope", "repository-diff-nonempty")
_SECRET_PATTERNS = (
    re.compile(r"\b(PASSWORD|TOKEN|SECRET)=", re.IGNORECASE),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
)


class CandidateVerificationFailureCode(StrEnum):
    """Stable candidate verification and review failure codes."""

    VERIFICATION_APPROVAL_MISSING = "verification_approval_missing"
    VERIFICATION_NOT_APPROVED = "verification_not_approved"
    VERIFICATION_EVIDENCE_MISMATCH = "verification_evidence_mismatch"
    CHANGED_FILES_OUT_OF_SCOPE = "changed_files_out_of_scope"
    CHANGED_FILES_DIGEST_MISMATCH = "changed_files_digest_mismatch"
    REPOSITORY_STALE = "repository_stale"
    CANDIDATE_STALE = "candidate_stale"
    PLAN_STALE = "plan_stale"
    IMPLEMENTATION_REQUEST_MISMATCH = "implementation_request_mismatch"
    CORE_UNAVAILABLE = "core_unavailable"
    VERIFICATION_FAILED = "verification_failed"
    REVIEW_FAILED = "review_failed"
    SECRET_LIKE_CHANGE_DETECTED = "secret_like_change_detected"
    COMMIT_APPROVAL_CREATION_FAILED = "commit_approval_creation_failed"
    PERSISTENCE_FAILED = "persistence_failed"


@dataclass(frozen=True, slots=True)
class CandidateVerificationPlan:
    identifier: str
    workflow_session_id: str
    candidate_planning_session_id: str
    candidate_id: str
    candidate_fingerprint: str
    candidate_plan_id: str
    candidate_plan_fingerprint: str
    implementation_request_id: str
    execution_result_id: str
    repository_root: Path
    repository_branch: str | None
    base_head: str
    post_execution_head: str
    changed_files: tuple[Path, ...]
    changed_files_digest: str
    approved_affected_files: tuple[Path, ...]
    verification_checks: tuple[VerificationCheck, ...]
    verifier_version: str
    generated_at: datetime


@dataclass(frozen=True, slots=True)
class CandidateVerificationCheckEvidence:
    identifier: str
    status: VerificationStatus
    return_code: int | None
    stdout_digest: str
    stderr_digest: str
    output_truncated: bool
    duration_seconds: float
    error: str | None = None


@dataclass(frozen=True, slots=True)
class CandidateVerificationEvidence:
    identifier: str
    verification_plan_id: str
    workflow_id: str
    candidate_id: str
    candidate_fingerprint: str
    plan_fingerprint: str
    implementation_request_id: str
    changed_files_digest: str
    repository_branch: str | None
    repository_head: str | None
    check_results: tuple[CandidateVerificationCheckEvidence, ...]
    status: VerificationStatus
    started_at: datetime
    completed_at: datetime
    verifier_version: str


@dataclass(frozen=True, slots=True)
class CandidateVerificationValidationResult:
    approved: bool
    failure_code: CandidateVerificationFailureCode | None = None
    message: str | None = None
    retryable: bool = False
    should_block: bool = False
    plan: CandidateVerificationPlan | None = None
    approval_request: ApprovalRequest | None = None
    checks: tuple[VerificationCheck, ...] = ()


@dataclass(frozen=True, slots=True)
class CandidateReviewResult:
    identifier: str
    verification_plan_id: str
    verification_evidence_id: str
    workflow_id: str
    status: ReviewStatus
    failure_code: CandidateVerificationFailureCode | None
    reviewed_content_fingerprint: str | None
    generated_at: datetime


@dataclass(frozen=True, slots=True)
class CandidateReviewAdapterResult:
    approved: bool
    failure_code: CandidateVerificationFailureCode | None = None
    review_report: ReviewReport | None = None
    candidate_review_result: CandidateReviewResult | None = None


class CandidateVerificationValidator:
    """Build and validate exact candidate verification plans."""

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

    def build_plan(self, workflow: WorkflowSession) -> CandidateVerificationValidationResult:
        local = self._validate_local_inputs(workflow)
        if not local.approved:
            return local
        request = workflow.candidate_implementation_request
        assert request is not None
        repository = self._repository_snapshot_for_request(request)
        if repository is None:
            return _failure(CandidateVerificationFailureCode.REPOSITORY_STALE, should_block=True)
        changed = _normalized_paths(_snapshot_changed_files(repository))
        expected_changed = _normalized_paths(workflow.changed_files)
        if not changed or changed != expected_changed:
            return _failure(CandidateVerificationFailureCode.REPOSITORY_STALE, should_block=True)
        approved = _normalized_paths(request.affected_files)
        if not _paths_within_scope(changed, approved):
            return _failure(CandidateVerificationFailureCode.CHANGED_FILES_OUT_OF_SCOPE, should_block=True)
        digest = changed_files_digest(
            workflow_id=workflow.identifier,
            implementation_request_id=request.identifier,
            candidate_fingerprint=request.candidate_fingerprint,
            plan_fingerprint=request.candidate_plan_fingerprint,
            repository_branch=request.repository_branch,
            base_head=request.repository_head,
            post_execution_head=repository.head_commit or "",
            changed_files=changed,
            approved_affected_files=approved,
        )
        checks = _verification_checks(request)
        plan = CandidateVerificationPlan(
            identifier=candidate_verification_plan_id(
                workflow_id=workflow.identifier,
                implementation_request_id=request.identifier,
                candidate_fingerprint=request.candidate_fingerprint,
                plan_fingerprint=request.candidate_plan_fingerprint,
                base_head=request.repository_head,
                post_execution_head=repository.head_commit or "",
                changed_files=changed,
                verifier_version=VERIFIER_VERSION,
            ),
            workflow_session_id=workflow.identifier,
            candidate_planning_session_id=request.candidate_planning_session_id,
            candidate_id=request.candidate_id,
            candidate_fingerprint=request.candidate_fingerprint,
            candidate_plan_id=request.candidate_plan_id,
            candidate_plan_fingerprint=request.candidate_plan_fingerprint,
            implementation_request_id=request.identifier,
            execution_result_id=workflow.execution_result.request_id if workflow.execution_result else "",
            repository_root=request.repository_root,
            repository_branch=request.repository_branch,
            base_head=request.repository_head,
            post_execution_head=repository.head_commit or "",
            changed_files=changed,
            changed_files_digest=digest,
            approved_affected_files=approved,
            verification_checks=checks,
            verifier_version=VERIFIER_VERSION,
            generated_at=self._clock(),
        )
        return CandidateVerificationValidationResult(
            approved=True,
            plan=plan,
            approval_request=self.exact_approval_request(plan),
            checks=checks,
        )

    def validate_for_execution(
        self,
        *,
        workflow: WorkflowSession,
        approval_result: ApprovalResult | None,
    ) -> CandidateVerificationValidationResult:
        plan = workflow.candidate_verification_plan
        if plan is None:
            return _failure(CandidateVerificationFailureCode.VERIFICATION_APPROVAL_MISSING, retryable=True)
        local = self._validate_local_inputs(workflow)
        if not local.approved:
            return local
        expected = self.exact_approval_request(plan)
        if approval_result is None:
            return _failure(CandidateVerificationFailureCode.VERIFICATION_APPROVAL_MISSING, retryable=True)
        if approval_result.decision.request != expected:
            return _failure(CandidateVerificationFailureCode.VERIFICATION_EVIDENCE_MISMATCH, should_block=True)
        decision = approval_result.decision
        if decision.status is ApprovalStatus.PENDING:
            return _failure(CandidateVerificationFailureCode.VERIFICATION_NOT_APPROVED, retryable=True)
        if decision.status is not ApprovalStatus.APPROVED:
            return _failure(CandidateVerificationFailureCode.VERIFICATION_NOT_APPROVED, should_block=True)
        core = self._validate_core(workflow)
        if not core.approved:
            return core
        plan_result = self._validate_candidate_plan_fingerprint(workflow)
        if not plan_result.approved:
            return plan_result
        request = workflow.candidate_implementation_request
        assert request is not None
        if not _plan_matches_request(plan, request, workflow):
            return _failure(CandidateVerificationFailureCode.IMPLEMENTATION_REQUEST_MISMATCH, should_block=True)
        repository = self._repository_snapshot_for_request(request)
        if repository is None:
            return _failure(CandidateVerificationFailureCode.REPOSITORY_STALE, should_block=True)
        changed = _normalized_paths(_snapshot_changed_files(repository))
        if changed != plan.changed_files:
            return _failure(CandidateVerificationFailureCode.REPOSITORY_STALE, should_block=True)
        digest = changed_files_digest(
            workflow_id=workflow.identifier,
            implementation_request_id=request.identifier,
            candidate_fingerprint=request.candidate_fingerprint,
            plan_fingerprint=request.candidate_plan_fingerprint,
            repository_branch=request.repository_branch,
            base_head=request.repository_head,
            post_execution_head=repository.head_commit or "",
            changed_files=changed,
            approved_affected_files=plan.approved_affected_files,
        )
        if digest != plan.changed_files_digest:
            return _failure(CandidateVerificationFailureCode.CHANGED_FILES_DIGEST_MISMATCH, should_block=True)
        return CandidateVerificationValidationResult(approved=True, plan=plan, checks=plan.verification_checks)

    def exact_approval_request(self, plan: CandidateVerificationPlan) -> ApprovalRequest:
        checks = tuple(
            VerificationApprovalCheck(
                identifier=check.identifier,
                command=check.argv,
                working_directory=check.working_directory.resolve(strict=False),
                timeout_seconds=check.timeout_seconds,
                environment=(),
            )
            for check in plan.verification_checks
        )
        request = ApprovalRequest(
            identifier=f"approval-verification-{plan.workflow_session_id}",
            workflow_id=plan.workflow_session_id,
            checkpoint_id=plan.identifier,
            title="Approve exact candidate verification checks",
            requested_tool="verification",
            requested_command=("verification-suite", *(check.identifier for check in checks)),
            requested_working_directory=plan.repository_root,
            rationale="Approve the exact candidate verification plan and changed-file evidence.",
            purpose=ApprovalPurpose.VERIFICATION,
            verification_checks=checks,
        )
        return request

    def placeholder_approval_request(self, workflow: WorkflowSession) -> ApprovalRequest:
        plan = workflow.plan
        assert plan is not None
        return ApprovalRequest(
            identifier=f"approval-verification-{workflow.identifier}",
            workflow_id=workflow.identifier,
            checkpoint_id=plan.checkpoint_id,
            title=f"Approve verification of {plan.title}",
            requested_tool="verification",
            requested_command=("verification-suite",),
            requested_working_directory=plan.repository_root,
            rationale="Approve the future candidate verification phase.",
            purpose=ApprovalPurpose.VERIFICATION,
        )

    def _validate_local_inputs(self, workflow: WorkflowSession) -> CandidateVerificationValidationResult:
        if workflow.source is not WorkflowSource.CANDIDATE:
            return _failure(CandidateVerificationFailureCode.VERIFICATION_EVIDENCE_MISMATCH, should_block=True)
        if workflow.state is not WorkflowSessionState.AWAITING_VERIFICATION_APPROVAL:
            return _failure(CandidateVerificationFailureCode.VERIFICATION_EVIDENCE_MISMATCH, should_block=True)
        request = workflow.candidate_implementation_request
        metadata = workflow.candidate_metadata
        if request is None or metadata is None or workflow.execution_result is None:
            return _failure(CandidateVerificationFailureCode.IMPLEMENTATION_REQUEST_MISMATCH, should_block=True)
        if workflow.execution_result.status.value != "succeeded" or not workflow.changed_files:
            return _failure(CandidateVerificationFailureCode.IMPLEMENTATION_REQUEST_MISMATCH, should_block=True)
        if not is_supported_execution_intent(request.execution_intent):
            return _failure(CandidateVerificationFailureCode.VERIFICATION_EVIDENCE_MISMATCH, should_block=True)
        if not (
            metadata.candidate_planning_session_id == request.candidate_planning_session_id
            and metadata.candidate_id == request.candidate_id
            and metadata.candidate_fingerprint == request.candidate_fingerprint
            and metadata.candidate_plan_id == request.candidate_plan_id
            and metadata.candidate_plan_fingerprint == request.candidate_plan_fingerprint
            and metadata.execution_intent == request.execution_intent
        ):
            return _failure(CandidateVerificationFailureCode.IMPLEMENTATION_REQUEST_MISMATCH, should_block=True)
        return self._validate_candidate_plan_fingerprint(workflow)

    def _validate_candidate_plan_fingerprint(self, workflow: WorkflowSession) -> CandidateVerificationValidationResult:
        request = workflow.candidate_implementation_request
        if request is None:
            return _failure(CandidateVerificationFailureCode.PLAN_STALE, should_block=True)
        session = self._candidate_state.get_session(request.candidate_planning_session_id)
        if session is None or session.workflow_session_id != workflow.identifier or session.plan is None:
            return _failure(CandidateVerificationFailureCode.PLAN_STALE, should_block=True)
        recomputed = candidate_plan_fingerprint(session.plan)
        if not (
            recomputed == request.candidate_plan_fingerprint
            and recomputed == session.candidate_plan_fingerprint
            and workflow.candidate_metadata is not None
            and recomputed == workflow.candidate_metadata.candidate_plan_fingerprint
        ):
            return _failure(CandidateVerificationFailureCode.PLAN_STALE, should_block=True)
        return CandidateVerificationValidationResult(approved=True)

    def _validate_core(self, workflow: WorkflowSession) -> CandidateVerificationValidationResult:
        request = workflow.candidate_implementation_request
        metadata = workflow.candidate_metadata
        if request is None or metadata is None:
            return _failure(CandidateVerificationFailureCode.CANDIDATE_STALE, should_block=True)
        try:
            intake = asyncio.run(
                self._core_client.validate_candidate_planning_intake(
                    request.candidate_id,
                    expected_candidate_fingerprint=request.candidate_fingerprint,
                )
            )
        except (AtlasCoreClientError, RuntimeError):
            return _failure(CandidateVerificationFailureCode.CORE_UNAVAILABLE, retryable=True)
        if intake.status != CoreCandidatePlanningIntakeStatus.ACCEPTED_FOR_PLANNING.value:
            return _failure(CandidateVerificationFailureCode.CANDIDATE_STALE, should_block=True)
        candidate = intake.current_candidate
        if candidate is None or intake.current_candidate_fingerprint is None:
            return _failure(CandidateVerificationFailureCode.CANDIDATE_STALE, should_block=True)
        if candidate.expires_at is not None and candidate.expires_at <= self._clock():
            return _failure(CandidateVerificationFailureCode.CANDIDATE_STALE, should_block=True)
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
            return _failure(CandidateVerificationFailureCode.CANDIDATE_STALE, should_block=True)
        return CandidateVerificationValidationResult(approved=True)

    def _repository_snapshot_for_request(self, request: CandidateImplementationRequest) -> RepositorySnapshot | None:
        session = self._candidate_state.get_session(request.candidate_planning_session_id)
        if session is None:
            return None
        resolved = self._repository_resolver.resolve(
            target_id=session.snapshot.target_id,
            target_type=session.snapshot.target_type,
        )
        if resolved is None:
            return None
        trusted_root = resolved.resolve(strict=False)
        if trusted_root != request.repository_root.resolve(strict=False):
            return None
        if not request.working_directory.resolve(strict=False).is_relative_to(trusted_root):
            return None
        for path in request.affected_files:
            if path.is_absolute() or ".." in path.parts:
                return None
        try:
            snapshot = self._repository_inspector_factory(trusted_root).inspect()
        except (OSError, RepositoryInspectionError, ValueError):
            return None
        if not (
            snapshot.root == trusted_root
            and snapshot.branch == request.repository_branch
            and snapshot.head_commit == request.repository_head
        ):
            return None
        return snapshot


class CandidateReviewAdapter:
    """Candidate-specific deterministic review before generic review."""

    def __init__(self, *, review_engine: ReviewEngine, clock: Callable[[], datetime] | None = None) -> None:
        self._review_engine = review_engine
        self._clock = clock or (lambda: datetime.now(UTC))

    def review(
        self,
        *,
        workflow: WorkflowSession,
        verification_plan: CandidateVerificationPlan,
        verification_evidence: CandidateVerificationEvidence,
        verification_report: VerificationReport,
        reviewed_content_fingerprint: str,
    ) -> CandidateReviewAdapterResult:
        if verification_report.status is not VerificationStatus.PASSED:
            return self._failure(workflow, verification_plan, verification_evidence, CandidateVerificationFailureCode.REVIEW_FAILED)
        if verification_evidence.status is not VerificationStatus.PASSED:
            return self._failure(workflow, verification_plan, verification_evidence, CandidateVerificationFailureCode.REVIEW_FAILED)
        if verification_evidence.verification_plan_id != verification_plan.identifier:
            return self._failure(workflow, verification_plan, verification_evidence, CandidateVerificationFailureCode.REVIEW_FAILED)
        if verification_evidence.changed_files_digest != verification_plan.changed_files_digest:
            return self._failure(workflow, verification_plan, verification_evidence, CandidateVerificationFailureCode.CHANGED_FILES_DIGEST_MISMATCH)
        if not _paths_within_scope(verification_plan.changed_files, verification_plan.approved_affected_files):
            return self._failure(workflow, verification_plan, verification_evidence, CandidateVerificationFailureCode.CHANGED_FILES_OUT_OF_SCOPE)
        if _secret_like_content_detected(verification_plan.repository_root, verification_plan.changed_files):
            return self._failure(workflow, verification_plan, verification_evidence, CandidateVerificationFailureCode.SECRET_LIKE_CHANGE_DETECTED)
        if workflow.plan is None:
            return self._failure(workflow, verification_plan, verification_evidence, CandidateVerificationFailureCode.REVIEW_FAILED)
        review_request = ReviewRequest(
            identifier=f"candidate-review-{verification_plan.identifier}",
            plan=workflow.plan,
            changed_files=verification_plan.changed_files,
            verification_report=verification_report,
            context=workflow.context,
        )
        try:
            review_report = self._review_engine.review(review_request)
        except ReviewValidationError:
            return self._failure(workflow, verification_plan, verification_evidence, CandidateVerificationFailureCode.REVIEW_FAILED)
        failure_code = None if review_report.status is ReviewStatus.APPROVED else CandidateVerificationFailureCode.REVIEW_FAILED
        result = CandidateReviewResult(
            identifier=review_request.identifier,
            verification_plan_id=verification_plan.identifier,
            verification_evidence_id=verification_evidence.identifier,
            workflow_id=workflow.identifier,
            status=review_report.status,
            failure_code=failure_code,
            reviewed_content_fingerprint=reviewed_content_fingerprint if review_report.status is ReviewStatus.APPROVED else None,
            generated_at=self._clock(),
        )
        return CandidateReviewAdapterResult(
            approved=review_report.status is ReviewStatus.APPROVED,
            failure_code=failure_code,
            review_report=review_report,
            candidate_review_result=result,
        )

    def _failure(
        self,
        workflow: WorkflowSession,
        plan: CandidateVerificationPlan,
        evidence: CandidateVerificationEvidence,
        code: CandidateVerificationFailureCode,
    ) -> CandidateReviewAdapterResult:
        return CandidateReviewAdapterResult(
            approved=False,
            failure_code=code,
            candidate_review_result=CandidateReviewResult(
                identifier=f"candidate-review-{plan.identifier}",
                verification_plan_id=plan.identifier,
                verification_evidence_id=evidence.identifier,
                workflow_id=workflow.identifier,
                status=ReviewStatus.CHANGES_REQUIRED,
                failure_code=code,
                reviewed_content_fingerprint=None,
                generated_at=self._clock(),
            ),
        )


def build_verification_evidence(
    *,
    plan: CandidateVerificationPlan,
    workflow: WorkflowSession,
    report: VerificationReport,
    started_at: datetime,
    completed_at: datetime,
) -> CandidateVerificationEvidence:
    return CandidateVerificationEvidence(
        identifier=f"candidate-verification-evidence-{plan.identifier}",
        verification_plan_id=plan.identifier,
        workflow_id=workflow.identifier,
        candidate_id=plan.candidate_id,
        candidate_fingerprint=plan.candidate_fingerprint,
        plan_fingerprint=plan.candidate_plan_fingerprint,
        implementation_request_id=plan.implementation_request_id,
        changed_files_digest=plan.changed_files_digest,
        repository_branch=plan.repository_branch,
        repository_head=plan.post_execution_head,
        check_results=tuple(_check_evidence(result) for result in report.results),
        status=report.status,
        started_at=started_at,
        completed_at=completed_at,
        verifier_version=VERIFIER_VERSION,
    )


def candidate_verification_plan_id(
    *,
    workflow_id: str,
    implementation_request_id: str,
    candidate_fingerprint: str,
    plan_fingerprint: str,
    base_head: str,
    post_execution_head: str,
    changed_files: tuple[Path, ...],
    verifier_version: str,
) -> str:
    payload = {
        "version": 1,
        "workflow_id": workflow_id,
        "implementation_request_id": implementation_request_id,
        "candidate_fingerprint": candidate_fingerprint,
        "plan_fingerprint": plan_fingerprint,
        "base_head": base_head,
        "post_execution_head": post_execution_head,
        "changed_files": [str(path) for path in _normalized_paths(changed_files)],
        "verifier_version": verifier_version,
    }
    digest = sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return f"candidate-verification-plan-{digest}"


def changed_files_digest(
    *,
    workflow_id: str,
    implementation_request_id: str,
    candidate_fingerprint: str,
    plan_fingerprint: str,
    repository_branch: str | None,
    base_head: str,
    post_execution_head: str,
    changed_files: tuple[Path, ...],
    approved_affected_files: tuple[Path, ...],
) -> str:
    normalized_changed = _normalized_paths(changed_files)
    normalized_approved = _normalized_paths(approved_affected_files)
    if not _paths_within_scope(normalized_changed, normalized_approved):
        raise ValueError("Changed files are outside approved affected-file scope")
    payload = {
        "version": 1,
        "workflow_id": workflow_id,
        "implementation_request_id": implementation_request_id,
        "candidate_fingerprint": candidate_fingerprint,
        "plan_fingerprint": plan_fingerprint,
        "repository_branch": repository_branch,
        "base_head": base_head,
        "post_execution_head": post_execution_head,
        "changed_files": [str(path) for path in normalized_changed],
        "approved_affected_files": [str(path) for path in normalized_approved],
    }
    digest = sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return f"changed-files-digest-v1:{digest}"


def _verification_checks(request: CandidateImplementationRequest) -> tuple[VerificationCheck, ...]:
    if request.execution_intent == RC1_VALIDATION_SMOKE_INTENT:
        return ()
    return (
        VerificationCheck(
            identifier=COMPOSE_CHECK_ID,
            argv=("docker", "compose", "--file", "compose.production.yaml", "config", "--no-env-resolution", "--quiet"),
            working_directory=request.repository_root,
            timeout_seconds=60.0,
        ),
    )


def _snapshot_changed_files(snapshot: RepositorySnapshot) -> tuple[Path, ...]:
    paths = [*snapshot.modified_files, *snapshot.staged_files]
    paths.extend(path for path in snapshot.untracked_files if Path(path).parts[:1] != ("logs",))
    return tuple(Path(path) for path in paths)


def _normalized_paths(paths: tuple[Path, ...]) -> tuple[Path, ...]:
    normalized: list[Path] = []
    seen: set[Path] = set()
    for path in paths:
        if path.is_absolute() or ".." in path.parts:
            raise ValueError("Path must be repository-relative and safe")
        clean = Path(*path.parts)
        if clean not in seen:
            normalized.append(clean)
            seen.add(clean)
    return tuple(sorted(normalized, key=lambda item: item.as_posix()))


def _paths_within_scope(changed_files: tuple[Path, ...], approved_files: tuple[Path, ...]) -> bool:
    approved = set(approved_files)
    for changed in changed_files:
        if changed not in approved and not any(changed.is_relative_to(scope) for scope in approved if scope.suffix == ""):
            return False
    return True


def _plan_matches_request(
    plan: CandidateVerificationPlan,
    request: CandidateImplementationRequest,
    workflow: WorkflowSession,
) -> bool:
    return (
        plan.workflow_session_id == workflow.identifier
        and plan.candidate_planning_session_id == request.candidate_planning_session_id
        and plan.candidate_id == request.candidate_id
        and plan.candidate_fingerprint == request.candidate_fingerprint
        and plan.candidate_plan_id == request.candidate_plan_id
        and plan.candidate_plan_fingerprint == request.candidate_plan_fingerprint
        and plan.implementation_request_id == request.identifier
        and plan.repository_root == request.repository_root
        and plan.repository_branch == request.repository_branch
        and plan.base_head == request.repository_head
        and plan.verifier_version == VERIFIER_VERSION
    )


def _check_evidence(result: VerificationCheckResult) -> CandidateVerificationCheckEvidence:
    stdout = result.stdout or ""
    stderr = result.stderr or ""
    return CandidateVerificationCheckEvidence(
        identifier=result.identifier,
        status=result.status,
        return_code=result.return_code,
        stdout_digest=sha256(stdout.encode()).hexdigest(),
        stderr_digest=sha256(stderr.encode()).hexdigest(),
        output_truncated=len(stdout) > 4096 or len(stderr) > 4096,
        duration_seconds=result.duration_seconds,
        error=result.error,
    )


def _secret_like_content_detected(repository_root: Path, changed_files: tuple[Path, ...]) -> bool:
    for relative in changed_files:
        path = repository_root / relative
        if not path.exists() or not path.is_file():
            continue
        try:
            content = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            return True
        for pattern in _SECRET_PATTERNS:
            if pattern.search(content):
                return True
    return False


def _failure(
    code: CandidateVerificationFailureCode,
    *,
    retryable: bool = False,
    should_block: bool = False,
) -> CandidateVerificationValidationResult:
    return CandidateVerificationValidationResult(
        approved=False,
        failure_code=code,
        message=code.value,
        retryable=retryable,
        should_block=should_block,
    )
