"""Tests for candidate commit validation and execution."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import Mock

from app.approval.engine import ApprovalEngine
from app.approval.models import (
    ApprovalDecision,
    ApprovalPurpose,
    ApprovalRequest,
    ApprovalStatus,
    CommitApprovalMetadata,
)
from app.approval.repository import ApprovalRepository
from app.candidate_planning.commit import (
    CandidateCommitFailureCode,
    CandidateCommitValidationResult,
    CandidateCommitValidator,
)
from app.candidate_planning.execution import implementation_plan_from_candidate_request
from app.candidate_planning.planner import RepositoryResolver
from app.candidate_planning.state import CandidatePlanningStateStore
from app.candidate_planning.verification import (
    CandidateReviewResult,
    CandidateVerificationCheckEvidence,
    CandidateVerificationEvidence,
    CandidateVerificationPlan,
    changed_files_digest,
)
from app.execution.models import ExecutionResult, ExecutionStatus
from app.planning.models import RoadmapCheckpoint
from app.repository.models import (
    CommitRequest,
    CommitResult,
    RepositorySnapshot,
    ReviewedChange,
    ReviewedChangeEvidence,
)
from app.review.engine import ReviewEngine
from app.review.models import ReviewReport, ReviewStatus
from app.verification.engine import VerificationEngine
from app.verification.models import VerificationReport, VerificationStatus
from app.workflow.engine import WorkflowEngine
from app.workflow.models import (
    SprintPhase,
    WorkflowRequest,
    WorkflowSession,
    WorkflowSessionState,
)
from app.workflow.state import WorkflowStateStore
from tests.candidate_planning.test_execution import (
    FakeCoreClient,
    core_response,
    planning_session,
    workflow,
)

FINGERPRINT = "a" * 64


class FakeInspector:
    candidate_calls = 0
    snapshot = RepositorySnapshot(
        root=Path("/repo"),
        branch="feature/atlas-agent",
        head_commit="abc123",
        is_clean=False,
        modified_files=("compose.production.yaml",),
        staged_files=(),
        untracked_files=(),
    )

    def __init__(self, repository_root: Path) -> None:
        self.repository_root = repository_root

    def inspect(self) -> RepositorySnapshot:
        return replace(self.snapshot, root=self.repository_root.resolve(strict=False))

    def reviewed_change_evidence(self, **kwargs) -> ReviewedChangeEvidence:
        return ReviewedChangeEvidence(
            repository_root=self.repository_root.resolve(strict=False),
            expected_branch=kwargs["expected_branch"],
            expected_head=kwargs["expected_head"],
            reviewed_files=tuple(sorted(kwargs["reviewed_files"])),
            commit_message=kwargs["commit_message"],
            changes=(ReviewedChange(path=Path("compose.production.yaml"), status="M", content_sha256=FINGERPRINT),),
            fingerprint=FINGERPRINT,
        )

    def reviewed_candidate_change_evidence(self, **kwargs) -> ReviewedChangeEvidence:
        type(self).candidate_calls += 1
        return self.reviewed_change_evidence(**kwargs)


class FakeCandidateCommitValidator:
    def __init__(self, result: CandidateCommitValidationResult) -> None:
        self.result = result
        self.validate_calls = 0
        self.result_calls = 0

    def validate(self, *, workflow, approval_result, expected_approval):
        self.validate_calls += 1
        return self.result

    def validate_commit_result(self, *, workflow, commit_result):
        self.result_calls += 1
        return CandidateCommitValidationResult(approved=True, commit_request=workflow.commit_request)


def _commit_ready_workflow(root: Path) -> WorkflowSession:
    shell = workflow(root)
    request = shell.candidate_implementation_request
    assert request is not None
    plan = implementation_plan_from_candidate_request(request)
    changed = (Path("compose.production.yaml"),)
    digest = changed_files_digest(
        workflow_id=shell.identifier,
        implementation_request_id=request.identifier,
        candidate_fingerprint=request.candidate_fingerprint,
        plan_fingerprint=request.candidate_plan_fingerprint,
        repository_branch=request.repository_branch,
        base_head=request.repository_head,
        post_execution_head=request.repository_head,
        changed_files=changed,
        approved_affected_files=request.affected_files,
    )
    verification_plan = CandidateVerificationPlan(
        identifier="candidate-verification-plan-aaa",
        workflow_session_id=shell.identifier,
        candidate_planning_session_id=request.candidate_planning_session_id,
        candidate_id=request.candidate_id,
        candidate_fingerprint=request.candidate_fingerprint,
        candidate_plan_id=request.candidate_plan_id,
        candidate_plan_fingerprint=request.candidate_plan_fingerprint,
        implementation_request_id=request.identifier,
        execution_result_id=request.identifier,
        repository_root=root,
        repository_branch=request.repository_branch,
        base_head=request.repository_head,
        post_execution_head=request.repository_head,
        baseline_status=None,
        post_execution_status=None,
        changed_files=changed,
        changed_files_digest=digest,
        approved_affected_files=request.affected_files,
        verification_checks=(),
        verifier_version="candidate-update-compose-stack-verifier-v1",
        generated_at=request.generated_at,
    )
    verification_evidence = CandidateVerificationEvidence(
        identifier="candidate-verification-evidence-aaa",
        verification_plan_id=verification_plan.identifier,
        workflow_id=shell.identifier,
        candidate_id=request.candidate_id,
        candidate_fingerprint=request.candidate_fingerprint,
        plan_fingerprint=request.candidate_plan_fingerprint,
        implementation_request_id=request.identifier,
        changed_files_digest=digest,
        repository_branch=request.repository_branch,
        repository_head=request.repository_head,
        check_results=(
            CandidateVerificationCheckEvidence(
                identifier="compose-production-config",
                status=VerificationStatus.PASSED,
                return_code=0,
                stdout_digest=FINGERPRINT,
                stderr_digest=FINGERPRINT,
                output_truncated=False,
                duration_seconds=0.1,
            ),
        ),
        status=VerificationStatus.PASSED,
        started_at=request.generated_at,
        completed_at=request.generated_at,
        verifier_version="candidate-update-compose-stack-verifier-v1",
    )
    candidate_review = CandidateReviewResult(
        identifier="candidate-review-aaa",
        verification_plan_id=verification_plan.identifier,
        verification_evidence_id=verification_evidence.identifier,
        workflow_id=shell.identifier,
        status=ReviewStatus.APPROVED,
        failure_code=None,
        reviewed_content_fingerprint=FINGERPRINT,
        generated_at=request.generated_at,
    )
    commit_request = CommitRequest(
        repository_root=root,
        expected_branch=request.repository_branch,
        expected_head=request.repository_head,
        paths=changed,
        message="feat(agent): update compose stack candidate",
    )
    return replace(
        shell,
        state=WorkflowSessionState.AWAITING_COMMIT_APPROVAL,
        request=WorkflowRequest(
            checkpoint=RoadmapCheckpoint(
                identifier=plan.checkpoint_id,
                title=plan.title,
                goal=plan.goal,
                affected_files=plan.affected_files,
            ),
            repository_root=root,
            execution_identifier=request.identifier,
            execution_argv=request.argv,
            execution_workdir=request.working_directory,
            verification_checks=(),
            review_identifier="candidate-review-aaa",
        ),
        plan=plan,
        execution_result=ExecutionResult(
            request_id=request.identifier,
            checkpoint_id=request.identifier,
            argv=request.argv,
            working_directory=request.working_directory,
            status=ExecutionStatus.SUCCEEDED,
            return_code=0,
            stdout="",
            stderr="",
            duration_seconds=1.0,
        ),
        changed_files=changed,
        verification_report=VerificationReport(root, (), VerificationStatus.PASSED, 0.1),
        candidate_verification_plan=verification_plan,
        candidate_verification_evidence=verification_evidence,
        review_report=ReviewReport("review", request.identifier, ReviewStatus.APPROVED, (), ()),
        candidate_review_result=candidate_review,
        commit_request=commit_request,
        reviewed_files=changed,
        expected_branch=request.repository_branch,
        expected_head=request.repository_head,
        reviewed_content_fingerprint=FINGERPRINT,
    )


def _approval(session: WorkflowSession, *, status: ApprovalStatus = ApprovalStatus.APPROVED) -> ApprovalRequest:
    request = session.commit_request
    assert request is not None
    approval = ApprovalRequest(
        identifier=f"approval-commit-{session.identifier}",
        workflow_id=session.identifier,
        checkpoint_id=session.plan.checkpoint_id,
        title=f"Approve commit of {session.plan.title}",
        requested_tool="git",
        requested_command=("git-commit", "compose.production.yaml"),
        requested_working_directory=request.repository_root,
        rationale="Approve the exact reviewed Git commit.",
        purpose=ApprovalPurpose.COMMIT,
        commit_metadata=CommitApprovalMetadata(
            expected_branch=request.expected_branch,
            expected_head=request.expected_head,
            reviewed_files=request.paths,
            reviewed_content_fingerprint=FINGERPRINT,
            commit_message=request.message,
        ),
    )
    return ApprovalEngine().evaluate(
        ApprovalDecision(request=approval, status=ApprovalStatus.PENDING)
    ).decision.request


def _validator(root: Path) -> CandidateCommitValidator:
    mock_now = datetime(2026, 8, 2, 0, 0, tzinfo=UTC)
    state = CandidatePlanningStateStore()
    state.create_session(planning_session(root))
    FakeInspector.snapshot = RepositorySnapshot(
        root=root.resolve(strict=False),
        branch="feature/atlas-agent",
        head_commit="abc123",
        is_clean=False,
        modified_files=("compose.production.yaml",),
        staged_files=(),
        untracked_files=(),
    )
    return CandidateCommitValidator(
        core_client=FakeCoreClient(core_response()),
        candidate_state=state,
        repository_resolver=RepositoryResolver(repository_root=root),
        repository_inspector_factory=FakeInspector,
        clock=lambda: mock_now,
    )


def test_missing_pending_and_rejected_commit_approval_do_not_commit(tmp_path: Path) -> None:
    session = _commit_ready_workflow(tmp_path)
    validator = _validator(tmp_path)
    approval = _approval(session)

    missing = validator.validate(workflow=session, approval_result=None, expected_approval=approval)
    pending = validator.validate(
        workflow=session,
        approval_result=ApprovalEngine().evaluate(ApprovalDecision(request=approval, status=ApprovalStatus.PENDING)),
        expected_approval=approval,
    )
    rejected = validator.validate(
        workflow=session,
        approval_result=ApprovalEngine().evaluate(
            ApprovalDecision(request=approval, status=ApprovalStatus.REJECTED, reviewer="tester", reason="no")
        ),
        expected_approval=approval,
    )

    assert missing.failure_code is CandidateCommitFailureCode.COMMIT_APPROVAL_MISSING
    assert missing.retryable
    assert pending.failure_code is CandidateCommitFailureCode.COMMIT_NOT_APPROVED
    assert pending.retryable
    assert rejected.failure_code is CandidateCommitFailureCode.COMMIT_NOT_APPROVED
    assert rejected.should_block


def test_commit_approval_metadata_mismatch_blocks(tmp_path: Path) -> None:
    session = _commit_ready_workflow(tmp_path)
    validator = _validator(tmp_path)
    expected = _approval(session)
    wrong = replace(
        expected,
        commit_metadata=replace(expected.commit_metadata, commit_message="different"),
    )

    result = validator.validate(
        workflow=session,
        approval_result=ApprovalEngine().evaluate(
            ApprovalDecision(request=wrong, status=ApprovalStatus.APPROVED, reviewer="tester")
        ),
        expected_approval=expected,
    )

    assert result.failure_code is CandidateCommitFailureCode.COMMIT_APPROVAL_EVIDENCE_MISMATCH
    assert result.should_block


def test_repository_drift_blocks_candidate_commit(tmp_path: Path) -> None:
    session = _commit_ready_workflow(tmp_path)
    validator = _validator(tmp_path)
    approval = _approval(session)
    FakeInspector.snapshot = replace(FakeInspector.snapshot, untracked_files=("README.md",))

    result = validator.validate(
        workflow=session,
        approval_result=ApprovalEngine().evaluate(
            ApprovalDecision(request=approval, status=ApprovalStatus.APPROVED, reviewer="tester")
        ),
        expected_approval=approval,
    )

    assert result.failure_code is CandidateCommitFailureCode.CHANGED_FILES_DRIFT
    assert result.should_block


def test_candidate_commit_revalidates_reviewed_delta_over_baseline(
    tmp_path: Path,
) -> None:
    session = _commit_ready_workflow(tmp_path)
    plan = session.candidate_verification_plan
    assert plan is not None
    baseline = (("compose.execution-smoke.override.yaml", "baseline"),)
    post_execution = baseline + (("compose.production.yaml", "candidate"),)
    session = replace(
        session,
        candidate_verification_plan=replace(
            plan,
            baseline_status=baseline,
            post_execution_status=post_execution,
        ),
    )
    validator = _validator(tmp_path)
    approval = _approval(session)
    FakeInspector.candidate_calls = 0

    result = validator.validate(
        workflow=session,
        approval_result=ApprovalEngine().evaluate(
            ApprovalDecision(request=approval, status=ApprovalStatus.APPROVED, reviewer="tester")
        ),
        expected_approval=approval,
    )

    assert result.approved
    assert FakeInspector.candidate_calls == 1


def test_exact_candidate_commit_executes_once_and_persists_result(tmp_path: Path) -> None:
    session = _commit_ready_workflow(tmp_path)
    state = WorkflowStateStore()
    state.create_session(session)
    approvals = ApprovalRepository()
    approval = _approval(session)
    approvals.save_request(approval)
    assert approvals.update_decision(
        approval.identifier,
        ApprovalDecision(request=approval, status=ApprovalStatus.APPROVED, reviewer="tester"),
    )
    commit_result = CommitResult(
        repository_root=tmp_path,
        branch=session.commit_request.expected_branch,
        parent_head=session.commit_request.expected_head,
        commit_sha="def456",
        message=session.commit_request.message,
        committed_files=session.commit_request.paths,
    )
    committer = Mock()
    committer.commit.return_value = commit_result
    validator = FakeCandidateCommitValidator(
        CandidateCommitValidationResult(approved=True, commit_request=session.commit_request)
    )
    engine = WorkflowEngine(
        repository_inspector_factory=Mock(),
        planning_engine=Mock(),
        execution_engine=Mock(),
        verification_engine=VerificationEngine(Mock()),
        review_engine=ReviewEngine(),
        approval_engine=ApprovalEngine(),
        approval_repository=approvals,
        state_store=state,
        repository_committer_factory=Mock(return_value=committer),
        candidate_commit_validator=validator,
    )

    result = engine.resume(session.identifier)
    repeated = engine.resume(session.identifier)

    assert result.sprint.phase is SprintPhase.COMPLETED
    assert result.commit_result == commit_result
    assert repeated.sprint.phase is SprintPhase.COMPLETED
    assert repeated.commit_result == commit_result
    stored = state.get_session(session.identifier)
    assert stored.state is WorkflowSessionState.COMPLETED
    assert stored.commit_result == commit_result
    committer.commit.assert_called_once_with(session.commit_request)
    assert validator.validate_calls == 1
    assert validator.result_calls == 1
