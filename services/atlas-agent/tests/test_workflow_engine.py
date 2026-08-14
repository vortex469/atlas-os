"""Tests for Atlas Agent workflow orchestration."""

from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from threading import Event
from unittest.mock import Mock, call

import pytest
from app.approval.engine import ApprovalEngine
from app.approval.models import (
    ApprovalDecision,
    ApprovalPurpose,
    ApprovalRequest,
    ApprovalResult,
    ApprovalStatus,
)
from app.approval.repository import ApprovalRepository
from app.candidate_planning.execution import (
    CandidateExecutionFailureCode,
    CandidateExecutionValidationResult,
    implementation_plan_from_candidate_request,
)
from app.candidate_planning.implementation import TRANSLATOR_VERSION
from app.candidate_planning.models import CandidateImplementationRequest
from app.candidate_planning.verification import (
    CandidateVerificationPlan,
    CandidateVerificationValidationResult,
)
from app.context.models import AgentContext, ServiceHealth
from app.execution.models import (
    EnvironmentVariable,
    ExecutionRequest,
    ExecutionResult,
    ExecutionStatus,
)
from app.execution.patches import PatchApplicationError
from app.execution.worker_contracts import CODEX_WORKSPACE_EXEC_ARGV_PREFIX
from app.model_providers.models import ModelResponse
from app.persistence.snapshot import AgentStatePersistenceCoordinator
from app.planning.advisor import PlanningAdvisor
from app.planning.models import ImplementationPlan, RoadmapCheckpoint
from app.repository.models import (
    CommitResult,
    RepositorySnapshot,
    ReviewedChange,
    ReviewedChangeEvidence,
)
from app.review.advisor import ReviewAdvisor
from app.review.models import ReviewReport, ReviewStatus
from app.verification.models import (
    VerificationCheck,
    VerificationReport,
    VerificationStatus,
)
from app.workflow.engine import WorkflowEngine
from app.workflow.models import (
    CandidateWorkflowMetadata,
    SprintPhase,
    WorkflowEffectKind,
    WorkflowRequest,
    WorkflowResult,
    WorkflowSession,
    WorkflowSessionState,
    WorkflowSource,
)
from app.workflow.state import WorkflowStateStore


def make_checkpoint() -> RoadmapCheckpoint:
    return RoadmapCheckpoint(
        identifier="A9",
        title="Workflow Automation",
        goal="Coordinate engineering workflows.",
        scope_items=("Add workflow orchestration",),
        affected_files=(Path("app/workflow/engine.py"),),
        required_tests=("Run pytest",),
    )


def make_snapshot(root: Path) -> RepositorySnapshot:
    return RepositorySnapshot(
        root=root,
        branch="feature/atlas-agent",
        head_commit="abc123",
        is_clean=True,
        modified_files=(),
        staged_files=(),
        untracked_files=(),
    )


def make_changed_snapshot(
    root: Path,
    *,
    head_commit: str = "abc123",
    modified_files: tuple[str, ...] = ("app/workflow/engine.py",),
    staged_files: tuple[str, ...] = (),
    untracked_files: tuple[str, ...] = (),
) -> RepositorySnapshot:
    return RepositorySnapshot(
        root=root,
        branch="feature/atlas-agent",
        head_commit=head_commit,
        is_clean=False,
        modified_files=modified_files,
        staged_files=staged_files,
        untracked_files=untracked_files,
    )


def make_commit_result(root: Path) -> CommitResult:
    return CommitResult(
        repository_root=root.resolve(strict=False),
        branch="feature/atlas-agent",
        parent_head="abc123",
        commit_sha="def456",
        message="feat(agent): workflow automation",
        committed_files=(Path("app/workflow/engine.py"),),
    )


def make_reviewed_evidence(root: Path, *, fingerprint: str = "a" * 64) -> ReviewedChangeEvidence:
    return ReviewedChangeEvidence(
        repository_root=root.resolve(strict=False),
        expected_branch="feature/atlas-agent",
        expected_head="abc123",
        reviewed_files=(Path("app/workflow/engine.py"),),
        commit_message="feat(agent): workflow automation",
        changes=(
            ReviewedChange(
                path=Path("app/workflow/engine.py"),
                status=" M",
                content_sha256="b" * 64,
            ),
        ),
        fingerprint=fingerprint,
    )


def make_plan(root: Path) -> ImplementationPlan:
    return ImplementationPlan(
        checkpoint_id="A9",
        title="Workflow Automation",
        goal="Coordinate engineering workflows.",
        repository_root=root,
        branch="feature/atlas-agent",
        head_commit="abc123",
        scope_items=("Add workflow orchestration",),
        affected_files=(Path("app/workflow/engine.py"),),
        required_tests=("Run pytest",),
        risks=(),
    )


def make_context() -> AgentContext:
    return AgentContext(
        atlas="online",
        assistant="Atlas",
        engine="Hermes",
        release="test",
        services={
            "atlas-core": ServiceHealth(
                provider_id="atlas-core",
                status="healthy",
            )
        },
    )


def make_execution_result(
    root: Path,
    *,
    status: ExecutionStatus = ExecutionStatus.SUCCEEDED,
    error: str | None = None,
) -> ExecutionResult:
    return ExecutionResult(
        request_id="execution-a9",
        checkpoint_id="A9",
        argv=("codex", "implement"),
        working_directory=root,
        status=status,
        return_code=0 if status is ExecutionStatus.SUCCEEDED else 1,
        stdout="",
        stderr="",
        duration_seconds=1.0,
        error=error,
    )


def make_verification_report(
    root: Path,
    *,
    status: VerificationStatus = VerificationStatus.PASSED,
    context: AgentContext | None = None,
) -> VerificationReport:
    return VerificationReport(
        repository_root=root,
        results=(),
        status=status,
        duration_seconds=1.0,
        context=context,
    )


def make_review_report(
    *,
    status: ReviewStatus = ReviewStatus.APPROVED,
) -> ReviewReport:
    return ReviewReport(
        request_id="review-a9",
        checkpoint_id="A9",
        status=status,
        findings=(),
        recommendations=(),
    )


def make_request(root: Path) -> WorkflowRequest:
    return WorkflowRequest(
        checkpoint=make_checkpoint(),
        repository_root=root,
        execution_identifier="execution-a9",
        execution_argv=("codex", "implement"),
        execution_workdir=root,
        verification_checks=(
            VerificationCheck(
                identifier="pytest",
                argv=("python", "-m", "pytest"),
                working_directory=root,
                environment=(
                    EnvironmentVariable(name="ATLAS_ENV", value="test"),
                ),
            ),
        ),
        review_identifier="review-a9",
    )

def make_approval_request() -> ApprovalRequest:
    return ApprovalRequest(
        identifier="approval-a12",
        checkpoint_id="A12",
        title="Approval Gate",
        requested_tool="codex",
        requested_command=("codex", "implement"),
        rationale="Approve controlled execution.",
    )

def make_engine(
    root: Path,
    *,
    execution_result: ExecutionResult,
    verification_report: VerificationReport,
    review_report: ReviewReport,
    planning_mode: str = "deterministic",
    planning_advisor: PlanningAdvisor | None = None,
    review_mode: str = "deterministic",
    review_advisor: ReviewAdvisor | None = None,
) -> tuple[WorkflowEngine, Mock, Mock, Mock, Mock, Mock, Mock]:
    inspector = Mock()
    inspector.inspect.return_value = make_snapshot(root)

    inspector_factory = Mock(return_value=inspector)

    planning_engine = Mock()
    planning_engine.plan.return_value = make_plan(root)


    execution_engine = Mock()
    execution_engine.execute.return_value = execution_result


    verification_engine = Mock()
    verification_engine.verify.return_value = verification_report

    review_engine = Mock()
    review_engine.review.return_value = review_report

    approval_engine = Mock(spec=ApprovalEngine)
    approval_repository = Mock(spec=ApprovalRepository)

    state_store = Mock(spec=WorkflowStateStore)

    engine = WorkflowEngine(
        repository_inspector_factory=inspector_factory,
        planning_engine=planning_engine,
        execution_engine=execution_engine,
        verification_engine=verification_engine,
        review_engine=review_engine,
        approval_engine=approval_engine,
        approval_repository=approval_repository,
        state_store=state_store,
        planning_mode=planning_mode,
        planning_advisor=planning_advisor,
        review_mode=review_mode,
        review_advisor=review_advisor,
    )

    return (
        engine,
        planning_engine,
        execution_engine,
        verification_engine,
        review_engine,
        approval_repository,
        state_store,
    )


def published_phases(state_store: Mock) -> list[SprintPhase]:
    return [
        invocation.args[0].phase
        for invocation in state_store.publish_sprint.call_args_list
    ]


def test_run_captures_context_once_before_planning(tmp_path: Path) -> None:
    context = make_context()
    (
        engine,
        planning_engine,
        _,
        _,
        _,
        _,
        state_store,
    ) = make_engine(
        tmp_path,
        execution_result=make_execution_result(tmp_path),
        verification_report=make_verification_report(tmp_path),
        review_report=make_review_report(),
    )

    result = engine.run(make_request(tmp_path), context=context)

    planning_engine.plan.assert_called_once_with(
        make_request(tmp_path).checkpoint,
        make_snapshot(tmp_path),
        context=context,
    )
    session = state_store.create_session.call_args.args[0]
    assert session.context is context
    assert result.context is context


def test_workflow_plans_stores_approval_and_pauses(
    tmp_path: Path,
) -> None:
    execution_result = make_execution_result(tmp_path)
    verification_report = make_verification_report(tmp_path)
    review_report = make_review_report()
    (
        engine,
        planning_engine,
        execution_engine,
        verification_engine,
        review_engine,
        approval_repository,
        state_store,
    ) = make_engine(
        tmp_path,
        execution_result=execution_result,
        verification_report=verification_report,
        review_report=review_report,
    )

    request = make_request(tmp_path)
    result = engine.run(request)

    assert result.sprint.phase is SprintPhase.AWAITING_APPROVAL
    assert result.plan is planning_engine.plan.return_value
    assert result.planning_analysis is None
    assert result.approval_request is not None
    assert result.execution_result is None
    assert result.verification_report is None
    assert result.review_report is None
    assert result.error_message is None

    planning_engine.plan.assert_called_once()
    approval_repository.save_request.assert_called_once_with(
        result.approval_request
    )
    approval = result.approval_request
    session = state_store.create_session.call_args.args[0]
    assert approval.workflow_id == session.identifier
    assert approval.checkpoint_id == request.checkpoint.identifier
    assert approval.requested_command is request.execution_argv
    assert approval.requested_working_directory is request.execution_workdir
    assert session.request is request
    assert session.plan is result.plan
    assert session.planning_analysis is None
    assert session.state is WorkflowSessionState.AWAITING_APPROVAL
    execution_engine.execute.assert_not_called()
    verification_engine.verify.assert_not_called()
    review_engine.review.assert_not_called()
    state_store.publish_verification.assert_not_called()
    state_store.publish_review.assert_not_called()
    assert published_phases(state_store) == [
        SprintPhase.PLANNED,
        SprintPhase.AWAITING_APPROVAL,
    ]


def test_deterministic_mode_never_calls_planning_advisor(
    tmp_path: Path,
) -> None:
    planning_advisor = Mock(spec=PlanningAdvisor)
    (
        engine,
        _,
        _,
        _,
        _,
        _,
        _,
    ) = make_engine(
        tmp_path,
        execution_result=make_execution_result(tmp_path),
        verification_report=make_verification_report(tmp_path),
        review_report=make_review_report(),
        planning_advisor=planning_advisor,
    )

    result = engine.run(make_request(tmp_path))

    planning_advisor.analyze.assert_not_called()
    assert result.planning_analysis is None


def test_model_assisted_mode_stores_analysis_without_replacing_plan(
    tmp_path: Path,
) -> None:
    analysis = ModelResponse(
        text="Keep the approved scope.",
        model="test-model",
        provider_id="test-provider",
    )
    planning_advisor = Mock(spec=PlanningAdvisor)
    planning_advisor.analyze.return_value = analysis
    (
        engine,
        planning_engine,
        execution_engine,
        _,
        _,
        _,
        state_store,
    ) = make_engine(
        tmp_path,
        execution_result=make_execution_result(tmp_path),
        verification_report=make_verification_report(tmp_path),
        review_report=make_review_report(),
        planning_mode="model-assisted",
        planning_advisor=planning_advisor,
    )
    plan = planning_engine.plan.return_value

    result = engine.run(make_request(tmp_path))

    planning_advisor.analyze.assert_called_once_with(plan)
    assert result.planning_analysis is analysis
    assert result.plan is plan
    session = state_store.create_session.call_args.args[0]
    assert session.plan is plan
    assert session.planning_analysis is analysis
    execution_engine.execute.assert_not_called()


def test_model_assisted_advisor_failure_blocks_before_execution(
    tmp_path: Path,
) -> None:
    planning_advisor = Mock(spec=PlanningAdvisor)
    planning_advisor.analyze.side_effect = RuntimeError(
        "sensitive provider failure"
    )
    (
        engine,
        _,
        execution_engine,
        verification_engine,
        review_engine,
        _,
        state_store,
    ) = make_engine(
        tmp_path,
        execution_result=make_execution_result(tmp_path),
        verification_report=make_verification_report(tmp_path),
        review_report=make_review_report(),
        planning_mode="model-assisted",
        planning_advisor=planning_advisor,
    )

    result = engine.run(make_request(tmp_path))

    assert result.sprint.phase is SprintPhase.BLOCKED
    assert result.planning_analysis is None
    assert result.error_message == "Model-assisted planning analysis failed"
    assert "sensitive provider failure" not in result.error_message
    execution_engine.execute.assert_not_called()
    verification_engine.verify.assert_not_called()
    review_engine.review.assert_not_called()
    assert published_phases(state_store) == [
        SprintPhase.PLANNED,
        SprintPhase.BLOCKED,
    ]


def test_invalid_review_mode_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="Unsupported review mode"):
        make_engine(
            tmp_path,
            execution_result=make_execution_result(tmp_path),
            verification_report=make_verification_report(tmp_path),
            review_report=make_review_report(),
            review_mode="unsupported",
        )


def test_planning_failure_blocks_before_approval_creation(
    tmp_path: Path,
) -> None:
    (
        engine,
        planning_engine,
        execution_engine,
        verification_engine,
        review_engine,
        approval_repository,
        state_store,
    ) = make_engine(
        tmp_path,
        execution_result=make_execution_result(tmp_path),
        verification_report=make_verification_report(tmp_path),
        review_report=make_review_report(),
    )
    planning_engine.plan.side_effect = RuntimeError("sensitive planning failure")

    result = engine.run(make_request(tmp_path))

    assert result.sprint.phase is SprintPhase.BLOCKED
    assert result.error_message == "Workflow planning failed"
    assert "sensitive planning failure" not in result.error_message
    approval_repository.save_request.assert_not_called()
    state_store.create_session.assert_not_called()
    execution_engine.execute.assert_not_called()
    verification_engine.verify.assert_not_called()
    review_engine.review.assert_not_called()
    assert published_phases(state_store) == [
        SprintPhase.PLANNED,
        SprintPhase.BLOCKED,
    ]


def test_approval_storage_failure_blocks_without_execution(
    tmp_path: Path,
) -> None:
    (
        engine,
        _,
        execution_engine,
        verification_engine,
        review_engine,
        approval_repository,
        state_store,
    ) = make_engine(
        tmp_path,
        execution_result=make_execution_result(tmp_path),
        verification_report=make_verification_report(tmp_path),
        review_report=make_review_report(),
    )
    approval_repository.save_request.side_effect = RuntimeError("storage down")

    result = engine.run(make_request(tmp_path))

    assert result.sprint.phase is SprintPhase.BLOCKED
    assert result.error_message == "Pre-execution approval storage failed"
    state_store.create_session.assert_called_once()
    session = state_store.create_session.call_args.args[0]
    state_store.delete_session.assert_called_once_with(session.identifier)
    execution_engine.execute.assert_not_called()
    verification_engine.verify.assert_not_called()
    review_engine.review.assert_not_called()


def test_session_storage_failure_leaves_no_approval(
    tmp_path: Path,
) -> None:
    (
        engine,
        _,
        execution_engine,
        verification_engine,
        review_engine,
        approval_repository,
        state_store,
    ) = make_engine(
        tmp_path,
        execution_result=make_execution_result(tmp_path),
        verification_report=make_verification_report(tmp_path),
        review_report=make_review_report(),
    )
    state_store.create_session.side_effect = ValueError(
        "Workflow session identifier already exists"
    )

    result = engine.run(make_request(tmp_path))

    assert result.sprint.phase is SprintPhase.BLOCKED
    assert result.error_message == "Pre-execution approval storage failed"
    approval_repository.save_request.assert_not_called()
    state_store.delete_session.assert_not_called()
    execution_engine.execute.assert_not_called()
    verification_engine.verify.assert_not_called()
    review_engine.review.assert_not_called()


def test_invalid_planning_mode_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="Unsupported planning mode"):
        make_engine(
            tmp_path,
            execution_result=make_execution_result(tmp_path),
            verification_report=make_verification_report(tmp_path),
            review_report=make_review_report(),
            planning_mode="autonomous",
        )


def test_model_assisted_mode_requires_advisor(tmp_path: Path) -> None:
    with pytest.raises(
        ValueError,
        match="Model-assisted planning requires a planning advisor",
    ):
        make_engine(
            tmp_path,
            execution_result=make_execution_result(tmp_path),
            verification_report=make_verification_report(tmp_path),
            review_report=make_review_report(),
            planning_mode="model-assisted",
        )


def test_execution_failure_fixture_remains_unreached_before_resume(
    tmp_path: Path,
) -> None:
    execution_result = make_execution_result(
        tmp_path,
        status=ExecutionStatus.FAILED,
        error="Execution failed",
    )
    (
        engine,
        _,
        execution_engine,
        verification_engine,
        review_engine,
        _,
        state_store,
    ) = make_engine(
        tmp_path,
        execution_result=execution_result,
        verification_report=make_verification_report(tmp_path),
        review_report=make_review_report(),
    )

    result = engine.run(make_request(tmp_path))

    assert result.sprint.phase is SprintPhase.AWAITING_APPROVAL
    assert result.execution_result is None
    assert result.verification_report is None
    assert result.review_report is None
    assert result.error_message is None
    execution_engine.execute.assert_not_called()
    verification_engine.verify.assert_not_called()
    review_engine.review.assert_not_called()
    assert published_phases(state_store) == [
        SprintPhase.PLANNED,
        SprintPhase.AWAITING_APPROVAL,
    ]


def test_verification_failure_fixture_remains_unreached_before_resume(
    tmp_path: Path,
) -> None:
    verification_report = make_verification_report(
        tmp_path,
        status=VerificationStatus.FAILED,
    )
    (
        engine,
        _,
        execution_engine,
        verification_engine,
        review_engine,
        _,
        state_store,
    ) = make_engine(
        tmp_path,
        execution_result=make_execution_result(tmp_path),
        verification_report=verification_report,
        review_report=make_review_report(),
    )

    result = engine.run(make_request(tmp_path))

    assert result.sprint.phase is SprintPhase.AWAITING_APPROVAL
    assert result.verification_report is None
    assert result.review_report is None
    assert result.error_message is None
    execution_engine.execute.assert_not_called()
    verification_engine.verify.assert_not_called()
    review_engine.review.assert_not_called()
    state_store.publish_verification.assert_not_called()
    state_store.publish_review.assert_not_called()
    assert published_phases(state_store) == [
        SprintPhase.PLANNED,
        SprintPhase.AWAITING_APPROVAL,
    ]


def test_review_rejection_fixture_remains_unreached_before_resume(
    tmp_path: Path,
) -> None:
    review_report = make_review_report(status=ReviewStatus.CHANGES_REQUIRED)
    (
        engine,
        _,
        execution_engine,
        verification_engine,
        review_engine,
        _,
        state_store,
    ) = make_engine(
        tmp_path,
        execution_result=make_execution_result(tmp_path),
        verification_report=make_verification_report(tmp_path),
        review_report=review_report,
    )

    result = engine.run(make_request(tmp_path))

    assert result.sprint.phase is SprintPhase.AWAITING_APPROVAL
    assert result.review_report is None
    assert result.error_message is None
    execution_engine.execute.assert_not_called()
    verification_engine.verify.assert_not_called()
    review_engine.review.assert_not_called()
    state_store.publish_review.assert_not_called()
    assert published_phases(state_store) == [
        SprintPhase.PLANNED,
        SprintPhase.AWAITING_APPROVAL,
    ]

def test_approved_decision_cannot_bypass_pause(tmp_path: Path) -> None:
    (
        engine,
        planning_engine,
        execution_engine,
        verification_engine,
        review_engine,
        approval_repository,
        _,
    ) = make_engine(
        tmp_path,
        execution_result=make_execution_result(tmp_path),
        verification_report=make_verification_report(tmp_path),
        review_report=make_review_report(),
    )

    decision = ApprovalDecision(
        request=make_approval_request(),
        status=ApprovalStatus.APPROVED,
        reviewer="tester",
    )
    result = engine.run(
        make_request(tmp_path),
        approval_decision=decision,
    )

    assert result.sprint.phase is SprintPhase.AWAITING_APPROVAL
    approval_repository.save_request.assert_called_once()
    planning_engine.plan.assert_called_once()
    execution_engine.execute.assert_not_called()
    verification_engine.verify.assert_not_called()
    review_engine.review.assert_not_called()

def test_rejected_decision_also_cannot_bypass_pause(tmp_path: Path) -> None:
    (
        engine,
        planning_engine,
        execution_engine,
        verification_engine,
        review_engine,
        approval_repository,
        state_store,
    ) = make_engine(
        tmp_path,
        execution_result=make_execution_result(tmp_path),
        verification_report=make_verification_report(tmp_path),
        review_report=make_review_report(),
    )

    decision = ApprovalDecision(
        request=make_approval_request(),
        status=ApprovalStatus.REJECTED,
        reviewer="tester",
        reason="Rejected for test.",
    )
    result = engine.run(
        make_request(tmp_path),
        approval_decision=decision,
    )

    assert result.sprint.phase is SprintPhase.AWAITING_APPROVAL
    assert result.error_message is None
    approval_repository.save_request.assert_called_once()
    planning_engine.plan.assert_called_once()
    execution_engine.execute.assert_not_called()
    verification_engine.verify.assert_not_called()
    review_engine.review.assert_not_called()
    assert published_phases(state_store) == [
        SprintPhase.PLANNED,
        SprintPhase.AWAITING_APPROVAL,
    ]


def make_resume_engine(
    root: Path,
    *,
    approval_status: ApprovalStatus = ApprovalStatus.APPROVED,
    session_state: WorkflowSessionState = WorkflowSessionState.AWAITING_APPROVAL,
    execution_result: ExecutionResult | None = None,
    verification_report: VerificationReport | None = None,
    review_report: ReviewReport | None = None,
    before_snapshot: RepositorySnapshot | None = None,
    after_snapshot: RepositorySnapshot | None = None,
    commit_error: Exception | None = None,
    context: AgentContext | None = None,
    review_mode: str = "deterministic",
    review_advisor: ReviewAdvisor | None = None,
) -> tuple[
    WorkflowEngine,
    WorkflowStateStore,
    ApprovalRepository,
    Mock,
    Mock,
    Mock,
    Mock,
    Mock,
]:
    request = make_request(root)
    plan = make_plan(root)
    session = WorkflowSession(
        identifier="workflow-a15-3",
        request=request,
        plan=plan,
        state=session_state,
        effect_kind=WorkflowEffectKind.REPOSITORY_CHANGE,
        context=context,
    )
    state_store = WorkflowStateStore()
    state_store.create_session(session)
    approval_repository = ApprovalRepository()
    approval_request = ApprovalRequest(
        identifier=f"approval-{session.identifier}",
        workflow_id=session.identifier,
        checkpoint_id=plan.checkpoint_id,
        title="Approve implementation",
        requested_tool=request.execution_argv[0],
        requested_command=request.execution_argv,
        requested_working_directory=request.execution_workdir,
        rationale="Approve the exact planned implementation operation.",
    )
    approval_repository.save_request(approval_request)
    approval_repository.update_decision(
        approval_request.identifier,
        ApprovalDecision(
            request=approval_request,
            status=approval_status,
            reviewer="tester" if approval_status is not ApprovalStatus.PENDING else None,
            reason="Not approved" if approval_status is ApprovalStatus.REJECTED else None,
        ),
    )
    inspector = Mock()
    inspector.inspect.side_effect = (
        before_snapshot or make_snapshot(root),
        after_snapshot or make_changed_snapshot(root),
    )
    inspector.reviewed_change_evidence.return_value = make_reviewed_evidence(root)
    inspector_factory = Mock(return_value=inspector)
    planning_engine = Mock()
    execution_engine = Mock()
    execution_engine.execute.return_value = (
        execution_result or make_execution_result(root)
    )
    verification_engine = Mock()
    verification_engine.verify.return_value = (
        verification_report or make_verification_report(root, context=context)
    )
    review_engine = Mock()
    review_engine.review.return_value = review_report or make_review_report()
    committer = Mock()
    committer.commit.return_value = make_commit_result(root)
    if commit_error is not None:
        committer.commit.side_effect = commit_error
    committer_factory = Mock(return_value=committer)
    engine = WorkflowEngine(
        repository_inspector_factory=inspector_factory,
        planning_engine=planning_engine,
        execution_engine=execution_engine,
        verification_engine=verification_engine,
        review_engine=review_engine,
        approval_engine=ApprovalEngine(),
        approval_repository=approval_repository,
        state_store=state_store,
        repository_committer_factory=committer_factory,
        review_mode=review_mode,
        review_advisor=review_advisor,
    )
    return (
        engine,
        state_store,
        approval_repository,
        inspector_factory,
        planning_engine,
        execution_engine,
        verification_engine,
        review_engine,
    )


def approve_verification_and_resume(
    engine: WorkflowEngine,
    approval_repository: ApprovalRepository,
) -> tuple[WorkflowResult, WorkflowResult]:
    implementation_result = engine.resume("workflow-a15-3")
    verification_request = implementation_result.approval_request
    assert verification_request is not None
    assert approval_repository.update_decision(
        verification_request.identifier,
        ApprovalDecision(
            request=verification_request,
            status=ApprovalStatus.APPROVED,
            reviewer="tester",
        ),
    )
    return implementation_result, engine.resume("workflow-a15-3")


def approve_commit_and_resume(
    engine: WorkflowEngine,
    approval_repository: ApprovalRepository,
) -> WorkflowResult:
    implementation = engine.resume("workflow-a15-3")
    verification_request = implementation.approval_request
    assert verification_request is not None
    assert approval_repository.update_decision(
        verification_request.identifier,
        ApprovalDecision(
            request=verification_request,
            status=ApprovalStatus.APPROVED,
            reviewer="tester",
        ),
    )
    commit_boundary = engine.resume("workflow-a15-3")
    commit_request = commit_boundary.approval_request
    assert commit_request is not None
    assert commit_request.purpose is ApprovalPurpose.COMMIT
    assert approval_repository.update_decision(
        commit_request.identifier,
        ApprovalDecision(
            request=commit_request,
            status=ApprovalStatus.APPROVED,
            reviewer="tester",
        ),
    )
    return engine.resume("workflow-a15-3")


def test_approved_workflow_resumes_exact_stored_plan(tmp_path: Path) -> None:
    (
        engine,
        state_store,
        approval_repository,
        inspector_factory,
        planning_engine,
        execution_engine,
        verification_engine,
        review_engine,
    ) = make_resume_engine(tmp_path)
    session = state_store.get_session("workflow-a15-3")

    implementation_result, result = approve_verification_and_resume(
        engine,
        approval_repository,
    )

    assert (
        implementation_result.sprint.phase
        is SprintPhase.AWAITING_VERIFICATION_APPROVAL
    )
    assert result.sprint.phase is SprintPhase.AWAITING_COMMIT_APPROVAL
    assert result.plan is session.plan
    assert result.execution_result is not None
    assert result.verification_report is not None
    assert result.review_report is not None
    assert result.commit_result is None
    assert (
        state_store.get_session(session.identifier).state
        is WorkflowSessionState.AWAITING_COMMIT_APPROVAL
    )
    execution_request = execution_engine.execute.call_args.args[0]
    review_request = review_engine.review.call_args.args[0]
    assert execution_request.plan is session.plan
    assert review_request.plan is session.plan
    verification_engine.verify.assert_called_once_with(
        repository_root=session.request.repository_root,
        checks=session.request.verification_checks,
        context=None,
    )
    assert inspector_factory.call_args_list == [
        call(session.request.repository_root),
        call(session.request.repository_root),
    ]
    planning_engine.plan.assert_not_called()


def test_resume_reuses_snapshot_without_context_acquisition(
    tmp_path: Path,
) -> None:
    context = make_context()
    (
        engine,
        _,
        approval_repository,
        _,
        _,
        _,
        verification_engine,
        review_engine,
    ) = make_resume_engine(
        tmp_path,
        context=context,
    )

    _, result = approve_verification_and_resume(engine, approval_repository)

    verification_engine.verify.assert_called_once_with(
        repository_root=tmp_path,
        checks=make_request(tmp_path).verification_checks,
        context=context,
    )
    review_request = review_engine.review.call_args.args[0]
    assert review_request.context is context
    assert result.context is context
    assert review_request.changed_files == (
        Path("app/workflow/engine.py"),
    )
    session = engine._state_store.get_session("workflow-a15-3")
    commit_request = session.commit_request
    assert commit_request is not None
    assert commit_request.paths == review_request.changed_files
    assert commit_request.message == "feat(agent): workflow automation"


def test_deterministic_review_mode_never_calls_review_advisor(
    tmp_path: Path,
) -> None:
    review_advisor = Mock(spec=ReviewAdvisor)
    (
        engine,
        _,
        approval_repository,
        _,
        _,
        _,
        _,
        _,
    ) = make_resume_engine(
        tmp_path,
        review_advisor=review_advisor,
    )

    _, result = approve_verification_and_resume(engine, approval_repository)

    review_advisor.analyze.assert_not_called()
    assert result.review_analysis is None


def test_model_assisted_review_runs_once_after_deterministic_review(
    tmp_path: Path,
) -> None:
    review_report = make_review_report()
    analysis = ModelResponse(
        text="Review advisory only.",
        model="test-model",
        provider_id="test-provider",
    )
    review_advisor = Mock(spec=ReviewAdvisor)
    review_advisor.analyze.return_value = analysis
    (
        engine,
        state_store,
        approval_repository,
        _,
        _,
        _,
        _,
        review_engine,
    ) = make_resume_engine(
        tmp_path,
        review_report=review_report,
        review_mode="model-assisted",
        review_advisor=review_advisor,
    )

    _, result = approve_verification_and_resume(engine, approval_repository)

    review_request = review_engine.review.call_args.args[0]
    review_advisor.analyze.assert_called_once_with(
        request=review_request,
        report=review_report,
    )
    assert result.review_report is review_report
    assert result.review_report.status is ReviewStatus.APPROVED
    assert result.review_analysis is analysis
    session = state_store.get_session("workflow-a15-3")
    assert session is not None
    assert session.review_report is review_report
    assert session.review_analysis is analysis
    assert session.state is WorkflowSessionState.AWAITING_COMMIT_APPROVAL


def test_model_assisted_review_failure_blocks_before_commit_approval(
    tmp_path: Path,
) -> None:
    review_advisor = Mock(spec=ReviewAdvisor)
    review_advisor.analyze.side_effect = RuntimeError("sensitive model failure")
    (
        engine,
        state_store,
        approval_repository,
        _,
        _,
        _,
        _,
        review_engine,
    ) = make_resume_engine(
        tmp_path,
        review_mode="model-assisted",
        review_advisor=review_advisor,
    )

    _, result = approve_verification_and_resume(engine, approval_repository)

    review_engine.review.assert_called_once()
    review_advisor.analyze.assert_called_once()
    assert result.sprint.phase is SprintPhase.BLOCKED
    assert result.error_message == "Model-assisted review analysis failed"
    assert "sensitive model failure" not in result.error_message
    assert result.review_report is not None
    assert result.review_analysis is None
    assert approval_repository.get_request("approval-commit-workflow-a15-3") is None
    session = state_store.get_session("workflow-a15-3")
    assert session is not None
    assert session.state is WorkflowSessionState.BLOCKED
    assert session.verification_report is result.verification_report
    assert session.review_report is result.review_report
    assert session.review_analysis is None
    assert session.commit_request is None


def test_commit_resume_reuses_review_analysis_without_model_call(
    tmp_path: Path,
) -> None:
    analysis = ModelResponse(
        text="Persisted advisory review.",
        model="test-model",
        provider_id="test-provider",
    )
    review_advisor = Mock(spec=ReviewAdvisor)
    review_advisor.analyze.return_value = analysis
    (
        engine,
        _,
        approval_repository,
        _,
        _,
        _,
        verification_engine,
        review_engine,
    ) = make_resume_engine(
        tmp_path,
        review_mode="model-assisted",
        review_advisor=review_advisor,
    )

    _, boundary = approve_verification_and_resume(engine, approval_repository)
    assert boundary.review_analysis is analysis
    review_advisor.analyze.reset_mock()
    verification_engine.verify.reset_mock()
    review_engine.review.reset_mock()
    commit_request = boundary.approval_request
    assert commit_request is not None
    assert approval_repository.update_decision(
        commit_request.identifier,
        ApprovalDecision(
            request=commit_request,
            status=ApprovalStatus.APPROVED,
            reviewer="tester",
        ),
    )

    result = engine.resume("workflow-a15-3")

    assert result.sprint.phase is SprintPhase.COMPLETED
    assert result.review_analysis is analysis
    verification_engine.verify.assert_not_called()
    review_engine.review.assert_not_called()
    review_advisor.analyze.assert_not_called()


def test_restart_commit_resume_reuses_review_analysis_without_model_call(
    tmp_path: Path,
) -> None:
    state_dir = tmp_path / "state"
    analysis = ModelResponse(
        text="Persisted advisory review.",
        model="test-model",
        provider_id="test-provider",
    )
    initial_review_advisor = Mock(spec=ReviewAdvisor)
    initial_review_advisor.analyze.return_value = analysis
    (
        initial_engine,
        state_store,
        approval_repository,
        _,
        _,
        _,
        _,
        _,
    ) = make_resume_engine(
        tmp_path,
        review_mode="model-assisted",
        review_advisor=initial_review_advisor,
    )
    _, boundary = approve_verification_and_resume(initial_engine, approval_repository)
    assert boundary.review_analysis is analysis
    persistence = AgentStatePersistenceCoordinator(
        state_dir=state_dir,
        workflow_state=state_store,
        approval_repository=approval_repository,
    )
    persistence.persist_current_state()

    recovered_state = WorkflowStateStore()
    recovered_approvals = ApprovalRepository()
    recovered_persistence = AgentStatePersistenceCoordinator(
        state_dir=state_dir,
        workflow_state=recovered_state,
        approval_repository=recovered_approvals,
    )
    recovered_persistence.initialize()
    commit_request = boundary.approval_request
    assert commit_request is not None
    assert recovered_approvals.update_decision(
        commit_request.identifier,
        ApprovalDecision(
            request=commit_request,
            status=ApprovalStatus.APPROVED,
            reviewer="tester",
        ),
    )
    inspector = Mock()
    inspector.reviewed_change_evidence.return_value = make_reviewed_evidence(tmp_path)
    inspector_factory = Mock(return_value=inspector)
    verification_engine = Mock()
    review_engine = Mock()
    review_advisor = Mock(spec=ReviewAdvisor)
    committer = Mock()
    committer.commit.return_value = make_commit_result(tmp_path)
    engine = WorkflowEngine(
        repository_inspector_factory=inspector_factory,
        planning_engine=Mock(),
        execution_engine=Mock(),
        verification_engine=verification_engine,
        review_engine=review_engine,
        approval_engine=ApprovalEngine(),
        approval_repository=recovered_approvals,
        state_store=recovered_state,
        repository_committer_factory=Mock(return_value=committer),
        review_mode="model-assisted",
        review_advisor=review_advisor,
        state_persistence=recovered_persistence,
    )

    result = engine.resume("workflow-a15-3")

    assert result.sprint.phase is SprintPhase.COMPLETED
    assert result.review_analysis == analysis
    verification_engine.verify.assert_not_called()
    review_engine.review.assert_not_called()
    review_advisor.analyze.assert_not_called()
    committer.commit.assert_called_once()


@pytest.mark.parametrize(
    ("state", "error"),
    (
        (WorkflowSessionState.EXECUTING, "Workflow already in progress"),
        (WorkflowSessionState.VERIFYING, "Workflow already in progress"),
        (WorkflowSessionState.COMMITTING, "Workflow already in progress"),
        (WorkflowSessionState.COMPLETED, "Workflow already completed"),
        (WorkflowSessionState.BLOCKED, "Workflow is not resumable"),
    ),
)
def test_terminal_or_claimed_workflow_does_not_resume_or_mutate(
    tmp_path: Path,
    state: WorkflowSessionState,
    error: str,
) -> None:
    engine, state_store, _, _, _, execution_engine, _, _ = make_resume_engine(
        tmp_path,
        session_state=state,
    )

    result = engine.resume("workflow-a15-3")

    assert result.error_message == error
    assert state_store.get_session("workflow-a15-3").state is state
    execution_engine.execute.assert_not_called()


def test_missing_workflow_fails_without_execution(tmp_path: Path) -> None:
    engine, _, _, _, _, execution_engine, _, _ = make_resume_engine(tmp_path)

    result = engine.resume("missing")

    assert result.sprint.phase is SprintPhase.BLOCKED
    assert result.error_message == "Workflow not found"
    execution_engine.execute.assert_not_called()


def test_missing_approval_leaves_workflow_awaiting(tmp_path: Path) -> None:
    (
        engine,
        state_store,
        approval_repository,
        _,
        _,
        execution_engine,
        _,
        _,
    ) = make_resume_engine(tmp_path)
    approval_repository._storage.clear()

    result = engine.resume("workflow-a15-3")

    assert result.error_message == "Approval not found"
    assert (
        state_store.get_session("workflow-a15-3").state
        is WorkflowSessionState.AWAITING_APPROVAL
    )
    execution_engine.execute.assert_not_called()


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("workflow_id", "another-workflow"),
        ("checkpoint_id", "A15.4"),
        ("requested_tool", "pytest"),
        ("requested_command", ("codex", "different")),
        ("requested_working_directory", Path("/different")),
    ),
)
def test_mismatched_approval_leaves_workflow_awaiting(
    tmp_path: Path,
    field: str,
    value: object,
) -> None:
    (
        engine,
        state_store,
        approval_repository,
        _,
        _,
        execution_engine,
        _,
        _,
    ) = make_resume_engine(tmp_path)
    stored = approval_repository.get_request("approval-workflow-a15-3")
    values = {
        name: getattr(stored.decision.request, name)
        for name in ApprovalRequest.__dataclass_fields__
    }
    values[field] = value
    mismatched = ApprovalRequest(**values)
    approval_repository._storage[mismatched.identifier] = ApprovalResult(
        decision=ApprovalDecision(
            request=mismatched,
            status=ApprovalStatus.APPROVED,
            reviewer="tester",
        )
    )

    result = engine.resume("workflow-a15-3")

    assert result.error_message == "Approval does not match workflow"
    assert (
        state_store.get_session("workflow-a15-3").state
        is WorkflowSessionState.AWAITING_APPROVAL
    )
    execution_engine.execute.assert_not_called()


def test_pending_implementation_approval_does_not_mutate_or_execute(
    tmp_path: Path,
) -> None:
    engine, state_store, approval_repository, _, _, execution_engine, _, _ = (
        make_resume_engine(
            tmp_path,
            approval_status=ApprovalStatus.PENDING,
        )
    )
    stored = approval_repository.get_request("approval-workflow-a15-3")
    assert stored is not None

    result = engine.resume("workflow-a15-3")

    assert result.error_message == "Approval pending"
    assert result.sprint.phase is SprintPhase.AWAITING_APPROVAL
    assert result.approval_request == stored.decision.request
    assert (
        state_store.get_session("workflow-a15-3").state
        is WorkflowSessionState.AWAITING_APPROVAL
    )
    assert (
        approval_repository.get_request("approval-workflow-a15-3").decision.status
        is ApprovalStatus.PENDING
    )
    assert result.execution_result is None
    execution_engine.execute.assert_not_called()


def test_approval_after_premature_implementation_resume_continues(
    tmp_path: Path,
) -> None:
    engine, state_store, approval_repository, _, _, execution_engine, verifier, _ = (
        make_resume_engine(
            tmp_path,
            approval_status=ApprovalStatus.PENDING,
        )
    )
    pending = approval_repository.get_request("approval-workflow-a15-3")
    assert pending is not None

    premature = engine.resume("workflow-a15-3")
    assert premature.error_message == "Approval pending"
    assert approval_repository.update_decision(
        pending.decision.request.identifier,
        ApprovalDecision(
            request=pending.decision.request,
            status=ApprovalStatus.APPROVED,
            reviewer="tester",
        ),
    )
    result = engine.resume("workflow-a15-3")

    assert result.sprint.phase is SprintPhase.AWAITING_VERIFICATION_APPROVAL
    assert result.error_message is None
    assert (
        state_store.get_session("workflow-a15-3").state
        is WorkflowSessionState.AWAITING_VERIFICATION_APPROVAL
    )
    execution_engine.execute.assert_called_once()
    verifier.verify.assert_not_called()


def test_restart_after_premature_implementation_resume_preserves_pending_approval(
    tmp_path: Path,
) -> None:
    state_dir = tmp_path / "state"
    engine, state_store, approval_repository, _, _, execution_engine, _, _ = (
        make_resume_engine(
            tmp_path,
            approval_status=ApprovalStatus.PENDING,
        )
    )
    pending = approval_repository.get_request("approval-workflow-a15-3")
    assert pending is not None

    premature = engine.resume("workflow-a15-3")
    persistence = AgentStatePersistenceCoordinator(
        state_dir=state_dir,
        workflow_state=state_store,
        approval_repository=approval_repository,
    )
    persistence.persist_current_state()

    recovered_state = WorkflowStateStore()
    recovered_approvals = ApprovalRepository()
    recovered_persistence = AgentStatePersistenceCoordinator(
        state_dir=state_dir,
        workflow_state=recovered_state,
        approval_repository=recovered_approvals,
    )
    recovered_persistence.initialize()
    recovered_pending = recovered_approvals.get_request("approval-workflow-a15-3")
    assert recovered_pending is not None
    assert recovered_pending.decision.status is ApprovalStatus.PENDING
    assert (
        recovered_state.get_session("workflow-a15-3").state
        is WorkflowSessionState.AWAITING_APPROVAL
    )

    assert premature.error_message == "Approval pending"
    assert approval_repository.get_request("approval-workflow-a15-3") is not None
    execution_engine.execute.assert_not_called()
    assert recovered_approvals.update_decision(
        recovered_pending.decision.request.identifier,
        ApprovalDecision(
            request=recovered_pending.decision.request,
            status=ApprovalStatus.APPROVED,
            reviewer="tester",
        ),
    )
    inspector = Mock()
    inspector.inspect.side_effect = (
        make_snapshot(tmp_path),
        make_changed_snapshot(tmp_path),
    )
    recovered_execution_engine = Mock()
    recovered_execution_engine.execute.return_value = make_execution_result(tmp_path)
    recovered_engine = WorkflowEngine(
        repository_inspector_factory=Mock(return_value=inspector),
        planning_engine=Mock(),
        execution_engine=recovered_execution_engine,
        verification_engine=Mock(),
        review_engine=Mock(),
        approval_engine=ApprovalEngine(),
        approval_repository=recovered_approvals,
        state_store=recovered_state,
        state_persistence=recovered_persistence,
    )

    result = recovered_engine.resume("workflow-a15-3")

    assert result.sprint.phase is SprintPhase.AWAITING_VERIFICATION_APPROVAL
    assert result.error_message is None
    assert (
        recovered_state.get_session("workflow-a15-3").state
        is WorkflowSessionState.AWAITING_VERIFICATION_APPROVAL
    )
    recovered_execution_engine.execute.assert_called_once()


def test_rejected_implementation_approval_still_blocks(
    tmp_path: Path,
) -> None:
    engine, state_store, _, _, _, execution_engine, _, _ = make_resume_engine(
        tmp_path,
        approval_status=ApprovalStatus.REJECTED,
    )

    result = engine.resume("workflow-a15-3")

    assert result.error_message == "Approval rejected"
    assert (
        state_store.get_session("workflow-a15-3").state
        is WorkflowSessionState.BLOCKED
    )
    execution_engine.execute.assert_not_called()


def test_duplicate_resume_does_not_replay_execution(tmp_path: Path) -> None:
    engine, _, approval_repository, _, _, execution_engine, _, _ = (
        make_resume_engine(tmp_path)
    )

    first = engine.resume("workflow-a15-3")
    repeated = engine.resume("workflow-a15-3")
    verification_request = first.approval_request
    assert verification_request is not None
    assert approval_repository.update_decision(
        verification_request.identifier,
        ApprovalDecision(
            request=verification_request,
            status=ApprovalStatus.APPROVED,
            reviewer="tester",
        ),
    )
    second = engine.resume("workflow-a15-3")
    third = engine.resume("workflow-a15-3")

    assert first.sprint.phase is SprintPhase.AWAITING_VERIFICATION_APPROVAL
    assert repeated.sprint.phase is SprintPhase.AWAITING_VERIFICATION_APPROVAL
    assert second.sprint.phase is SprintPhase.AWAITING_COMMIT_APPROVAL
    assert third.sprint.phase is SprintPhase.AWAITING_COMMIT_APPROVAL
    execution_engine.execute.assert_called_once()


def test_execution_failure_blocks_and_stops_pipeline(tmp_path: Path) -> None:
    engine, state_store, _, _, _, _, verification_engine, review_engine = (
        make_resume_engine(
            tmp_path,
            execution_result=make_execution_result(
                tmp_path,
                status=ExecutionStatus.FAILED,
            ),
        )
    )

    result = engine.resume("workflow-a15-3")

    assert result.error_message == "Execution failed"
    assert (
        state_store.get_session("workflow-a15-3").state
        is WorkflowSessionState.BLOCKED
    )
    verification_engine.verify.assert_not_called()
    review_engine.review.assert_not_called()


def test_verification_failure_blocks_before_review(tmp_path: Path) -> None:
    engine, state_store, approval_repository, _, _, _, _, review_engine = make_resume_engine(
        tmp_path,
        verification_report=make_verification_report(
            tmp_path,
            status=VerificationStatus.FAILED,
        ),
    )

    _, result = approve_verification_and_resume(engine, approval_repository)

    assert result.error_message == "Verification failed"
    assert (
        state_store.get_session("workflow-a15-3").state
        is WorkflowSessionState.BLOCKED
    )
    review_engine.review.assert_not_called()


def test_review_rejection_blocks_workflow(tmp_path: Path) -> None:
    engine, state_store, approval_repository, _, _, _, _, _ = make_resume_engine(
        tmp_path,
        review_report=make_review_report(
            status=ReviewStatus.CHANGES_REQUIRED,
        ),
    )

    _, result = approve_verification_and_resume(engine, approval_repository)

    assert result.error_message == "Review failed"
    assert (
        state_store.get_session("workflow-a15-3").state
        is WorkflowSessionState.BLOCKED
    )


def test_preexisting_non_log_change_blocks_before_execution(
    tmp_path: Path,
) -> None:
    engine, state_store, _, _, _, execution_engine, _, _ = make_resume_engine(
        tmp_path,
        before_snapshot=make_changed_snapshot(tmp_path),
    )

    result = engine.resume("workflow-a15-3")

    assert result.error_message == "Workflow repository validation failed"
    assert (
        state_store.get_session("workflow-a15-3").state
        is WorkflowSessionState.BLOCKED
    )
    execution_engine.execute.assert_not_called()


def test_preexisting_untracked_logs_are_permitted(tmp_path: Path) -> None:
    before = make_changed_snapshot(
        tmp_path,
        modified_files=(),
        untracked_files=("logs/",),
    )
    after = make_changed_snapshot(
        tmp_path,
        untracked_files=("logs/",),
    )
    engine, _, approval_repository, _, _, _, _, review_engine = make_resume_engine(
        tmp_path,
        before_snapshot=before,
        after_snapshot=after,
    )

    _, result = approve_verification_and_resume(engine, approval_repository)

    assert result.sprint.phase is SprintPhase.AWAITING_COMMIT_APPROVAL
    review_request = review_engine.review.call_args.args[0]
    assert review_request.changed_files == (
        Path("app/workflow/engine.py"),
    )


def test_out_of_plan_change_blocks_before_verification(
    tmp_path: Path,
) -> None:
    engine, state_store, _, _, _, _, verification_engine, review_engine = (
        make_resume_engine(
            tmp_path,
            after_snapshot=make_changed_snapshot(
                tmp_path,
                modified_files=("unrelated.py",),
            ),
        )
    )

    result = engine.resume("workflow-a15-3")

    assert result.error_message == "Workflow change inspection failed"
    assert (
        state_store.get_session("workflow-a15-3").state
        is WorkflowSessionState.BLOCKED
    )
    verification_engine.verify.assert_not_called()
    review_engine.review.assert_not_called()


def test_post_execution_head_validation_is_deferred_to_committer(
    tmp_path: Path,
) -> None:
    engine, _, approval_repository, _, _, _, _, review_engine = make_resume_engine(
        tmp_path,
        after_snapshot=make_changed_snapshot(
            tmp_path,
            head_commit="changed-after-execution",
        ),
    )

    _, result = approve_verification_and_resume(engine, approval_repository)

    assert result.sprint.phase is SprintPhase.AWAITING_COMMIT_APPROVAL
    review_engine.review.assert_called_once()
    session = engine._state_store.get_session("workflow-a15-3")
    commit_request = session.commit_request
    assert commit_request is not None
    assert commit_request.expected_head == "abc123"


def test_no_committable_change_blocks_before_verification(
    tmp_path: Path,
) -> None:
    engine, state_store, _, _, _, _, verification_engine, _ = make_resume_engine(
        tmp_path,
        after_snapshot=make_changed_snapshot(
            tmp_path,
            modified_files=(),
            untracked_files=("logs/",),
        ),
    )

    result = engine.resume("workflow-a15-3")

    assert result.error_message == "Workflow change inspection failed"
    assert (
        state_store.get_session("workflow-a15-3").state
        is WorkflowSessionState.BLOCKED
    )
    verification_engine.verify.assert_not_called()


def test_commit_failure_blocks_and_preserves_completed_artifacts(
    tmp_path: Path,
) -> None:
    engine, state_store, approval_repository, _, _, _, _, _ = make_resume_engine(
        tmp_path,
        commit_error=RuntimeError("git identity missing"),
    )

    _, commit_boundary = approve_verification_and_resume(engine, approval_repository)
    request = commit_boundary.approval_request
    assert request is not None
    assert approval_repository.update_decision(
        request.identifier,
        ApprovalDecision(
            request=request,
            status=ApprovalStatus.APPROVED,
            reviewer="tester",
        ),
    )
    result = engine.resume("workflow-a15-3")

    assert result.error_message == "Workflow commit failed"
    assert result.execution_result is not None
    assert result.verification_report is not None
    assert result.review_report is not None
    assert result.commit_result is None
    assert (
        state_store.get_session("workflow-a15-3").state
        is WorkflowSessionState.BLOCKED
    )


def test_review_rejection_never_calls_committer(tmp_path: Path) -> None:
    engine, _, approval_repository, _, _, _, _, _ = make_resume_engine(
        tmp_path,
        review_report=make_review_report(
            status=ReviewStatus.CHANGES_REQUIRED,
        ),
    )

    approve_verification_and_resume(engine, approval_repository)

    engine._repository_committer_factory.assert_not_called()


def test_implementation_pauses_with_persisted_verification_artifacts(
    tmp_path: Path,
) -> None:
    (
        engine,
        state_store,
        approval_repository,
        _,
        _,
        execution_engine,
        verification_engine,
        review_engine,
    ) = make_resume_engine(tmp_path)

    result = engine.resume("workflow-a15-3")

    assert result.sprint.phase is SprintPhase.AWAITING_VERIFICATION_APPROVAL
    assert result.approval_request is not None
    assert result.approval_request.purpose is ApprovalPurpose.VERIFICATION
    check = result.approval_request.verification_checks[0]
    assert check.command == ("python", "-m", "pytest")
    assert check.environment[0].name == "ATLAS_ENV"
    assert check.environment[0].value_digest != "test"
    assert len(check.environment[0].value_digest) == 64
    session = state_store.get_session("workflow-a15-3")
    assert session is not None
    assert session.state is WorkflowSessionState.AWAITING_VERIFICATION_APPROVAL
    assert session.execution_result is result.execution_result
    assert session.changed_files == (Path("app/workflow/engine.py"),)
    stored = approval_repository.get_request(result.approval_request.identifier)
    assert stored is not None
    execution_engine.execute.assert_called_once()
    verification_engine.verify.assert_not_called()
    review_engine.review.assert_not_called()
    engine._repository_committer_factory.assert_not_called()


def test_pending_or_missing_verification_approval_remains_waiting(
    tmp_path: Path,
) -> None:
    engine, state_store, repository, _, _, execution_engine, verifier, _ = (
        make_resume_engine(tmp_path)
    )
    implementation = engine.resume("workflow-a15-3")
    approval_request = implementation.approval_request
    assert approval_request is not None

    pending = engine.resume("workflow-a15-3")
    repository._storage.pop(approval_request.identifier)
    missing = engine.resume("workflow-a15-3")

    assert pending.error_message is None
    assert missing.error_message is None
    assert pending.sprint.phase is SprintPhase.AWAITING_VERIFICATION_APPROVAL
    assert missing.sprint.phase is SprintPhase.AWAITING_VERIFICATION_APPROVAL
    assert (
        state_store.get_session("workflow-a15-3").state
        is WorkflowSessionState.AWAITING_VERIFICATION_APPROVAL
    )
    execution_engine.execute.assert_called_once()
    verifier.verify.assert_not_called()


@pytest.mark.parametrize("mismatched", (False, True))
def test_rejected_or_mismatched_verification_approval_blocks(
    tmp_path: Path,
    mismatched: bool,
) -> None:
    engine, state_store, repository, _, _, execution_engine, verifier, _ = (
        make_resume_engine(tmp_path)
    )
    implementation = engine.resume("workflow-a15-3")
    request = implementation.approval_request
    assert request is not None
    if mismatched:
        values = {
            name: getattr(request, name)
            for name in ApprovalRequest.__dataclass_fields__
        }
        values["checkpoint_id"] = "A12.2"
        wrong_request = ApprovalRequest(**values)
        repository._storage[request.identifier] = ApprovalResult(
            decision=ApprovalDecision(
                request=wrong_request,
                status=ApprovalStatus.APPROVED,
                reviewer="tester",
            )
        )
    else:
        assert repository.update_decision(
            request.identifier,
            ApprovalDecision(
                request=request,
                status=ApprovalStatus.REJECTED,
                reviewer="tester",
                reason="Verification not approved.",
            ),
        )

    result = engine.resume("workflow-a15-3")

    expected = (
        "Approval does not match workflow"
        if mismatched
        else "Approval rejected"
    )
    assert result.error_message == expected
    assert (
        state_store.get_session("workflow-a15-3").state
        is WorkflowSessionState.BLOCKED
    )
    execution_engine.execute.assert_called_once()
    verifier.verify.assert_not_called()


def test_successful_review_pauses_with_commit_approval_evidence(
    tmp_path: Path,
) -> None:
    engine, state_store, repository, _, _, _, verifier, reviewer = make_resume_engine(
        tmp_path
    )

    _, result = approve_verification_and_resume(engine, repository)

    assert result.sprint.phase is SprintPhase.AWAITING_COMMIT_APPROVAL
    request = result.approval_request
    assert request is not None
    assert request.purpose is ApprovalPurpose.COMMIT
    assert request.requested_tool == "git"
    assert request.requested_command == ("git-commit", "app/workflow/engine.py")
    assert request.commit_metadata is not None
    assert request.commit_metadata.expected_branch == "feature/atlas-agent"
    assert request.commit_metadata.expected_head == "abc123"
    assert request.commit_metadata.reviewed_files == (Path("app/workflow/engine.py"),)
    assert request.commit_metadata.reviewed_content_fingerprint == "a" * 64
    session = state_store.get_session("workflow-a15-3")
    assert session.verification_report is result.verification_report
    assert session.review_report is result.review_report
    assert session.commit_request is not None
    assert session.reviewed_files == (Path("app/workflow/engine.py"),)
    assert session.expected_branch == "feature/atlas-agent"
    assert session.expected_head == "abc123"
    assert session.reviewed_content_fingerprint == "a" * 64
    verifier.verify.assert_called_once()
    reviewer.review.assert_called_once()
    engine._repository_committer_factory.assert_not_called()


def test_pending_or_missing_commit_approval_remains_waiting(
    tmp_path: Path,
) -> None:
    engine, state_store, repository, _, _, execution_engine, verifier, reviewer = (
        make_resume_engine(tmp_path)
    )
    _, boundary = approve_verification_and_resume(engine, repository)
    request = boundary.approval_request
    assert request is not None

    pending = engine.resume("workflow-a15-3")
    repository._storage.pop(request.identifier)
    missing = engine.resume("workflow-a15-3")

    assert pending.error_message is None
    assert missing.error_message is None
    assert pending.sprint.phase is SprintPhase.AWAITING_COMMIT_APPROVAL
    assert missing.sprint.phase is SprintPhase.AWAITING_COMMIT_APPROVAL
    assert (
        state_store.get_session("workflow-a15-3").state
        is WorkflowSessionState.AWAITING_COMMIT_APPROVAL
    )
    execution_engine.execute.assert_called_once()
    verifier.verify.assert_called_once()
    reviewer.review.assert_called_once()
    engine._repository_committer_factory.assert_not_called()


@pytest.mark.parametrize("mismatched", (False, True))
def test_rejected_or_mismatched_commit_approval_blocks(
    tmp_path: Path,
    mismatched: bool,
) -> None:
    engine, state_store, repository, _, _, _, _, _ = make_resume_engine(tmp_path)
    _, boundary = approve_verification_and_resume(engine, repository)
    request = boundary.approval_request
    assert request is not None
    if mismatched:
        values = {
            name: getattr(request, name)
            for name in ApprovalRequest.__dataclass_fields__
        }
        values["purpose"] = ApprovalPurpose.IMPLEMENTATION
        values["commit_metadata"] = None
        wrong_request = ApprovalRequest(**values)
        repository._storage[request.identifier] = ApprovalResult(
            decision=ApprovalDecision(
                request=wrong_request,
                status=ApprovalStatus.APPROVED,
                reviewer="tester",
            )
        )
    else:
        assert repository.update_decision(
            request.identifier,
            ApprovalDecision(
                request=request,
                status=ApprovalStatus.REJECTED,
                reviewer="tester",
                reason="Commit not approved.",
            ),
        )

    result = engine.resume("workflow-a15-3")

    assert result.error_message == (
        "Approval does not match workflow" if mismatched else "Approval rejected"
    )
    assert state_store.get_session("workflow-a15-3").state is WorkflowSessionState.BLOCKED
    engine._repository_committer_factory.assert_not_called()


@pytest.mark.parametrize(
    "evidence_error",
    (
        RuntimeError("branch drift"),
        RuntimeError("head drift"),
        RuntimeError("changed path drift"),
    ),
)
def test_commit_evidence_validation_failure_blocks_before_commit(
    tmp_path: Path,
    evidence_error: Exception,
) -> None:
    engine, state_store, repository, inspector_factory, _, _, _, _ = make_resume_engine(
        tmp_path
    )
    _, boundary = approve_verification_and_resume(engine, repository)
    request = boundary.approval_request
    assert request is not None
    assert repository.update_decision(
        request.identifier,
        ApprovalDecision(
            request=request,
            status=ApprovalStatus.APPROVED,
            reviewer="tester",
        ),
    )
    inspector_factory.return_value.reviewed_change_evidence.side_effect = evidence_error

    result = engine.resume("workflow-a15-3")

    assert result.error_message == "Workflow commit evidence validation failed"
    assert state_store.get_session("workflow-a15-3").state is WorkflowSessionState.BLOCKED
    engine._repository_committer_factory.assert_not_called()


def test_commit_fingerprint_drift_blocks_before_commit(tmp_path: Path) -> None:
    engine, state_store, repository, inspector_factory, _, _, _, _ = make_resume_engine(
        tmp_path
    )
    _, boundary = approve_verification_and_resume(engine, repository)
    request = boundary.approval_request
    assert request is not None
    assert repository.update_decision(
        request.identifier,
        ApprovalDecision(
            request=request,
            status=ApprovalStatus.APPROVED,
            reviewer="tester",
        ),
    )
    inspector_factory.return_value.reviewed_change_evidence.return_value = make_reviewed_evidence(
        tmp_path,
        fingerprint="c" * 64,
    )

    result = engine.resume("workflow-a15-3")

    assert result.error_message == "Workflow commit evidence validation failed"
    assert state_store.get_session("workflow-a15-3").state is WorkflowSessionState.BLOCKED
    engine._repository_committer_factory.assert_not_called()


def test_approved_commit_resume_does_not_replay_prior_stages(
    tmp_path: Path,
) -> None:
    engine, state_store, repository, _, _, execution_engine, verifier, reviewer = (
        make_resume_engine(tmp_path)
    )

    result = approve_commit_and_resume(engine, repository)
    repeated = engine.resume("workflow-a15-3")

    assert result.sprint.phase is SprintPhase.COMPLETED
    assert repeated.error_message == "Workflow already completed"
    assert state_store.get_session("workflow-a15-3").state is WorkflowSessionState.COMPLETED
    execution_engine.execute.assert_called_once()
    verifier.verify.assert_called_once()
    reviewer.review.assert_called_once()
    engine._repository_committer_factory.return_value.commit.assert_called_once()


def test_concurrent_commit_resumes_call_committer_once(tmp_path: Path) -> None:
    engine, _, repository, _, _, execution_engine, verifier, reviewer = make_resume_engine(
        tmp_path
    )
    _, boundary = approve_verification_and_resume(engine, repository)
    request = boundary.approval_request
    assert request is not None
    assert repository.update_decision(
        request.identifier,
        ApprovalDecision(
            request=request,
            status=ApprovalStatus.APPROVED,
            reviewer="tester",
        ),
    )

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = tuple(
            executor.map(lambda _: engine.resume("workflow-a15-3"), range(2))
        )

    assert sum(result.commit_result is not None for result in results) == 1
    execution_engine.execute.assert_called_once()
    verifier.verify.assert_called_once()
    reviewer.review.assert_called_once()
    engine._repository_committer_factory.return_value.commit.assert_called_once()


def test_concurrent_verification_resume_runs_stage_once(
    tmp_path: Path,
) -> None:
    engine, _, repository, _, _, execution_engine, verifier, reviewer = (
        make_resume_engine(tmp_path)
    )
    implementation = engine.resume("workflow-a15-3")
    request = implementation.approval_request
    assert request is not None
    assert repository.update_decision(
        request.identifier,
        ApprovalDecision(
            request=request,
            status=ApprovalStatus.APPROVED,
            reviewer="tester",
        ),
    )
    verification_entered = Event()
    release_verification = Event()
    verification_report = make_verification_report(tmp_path)

    def verify_once(**kwargs) -> VerificationReport:
        verification_entered.set()
        assert release_verification.wait(timeout=5)
        return verification_report

    verifier.verify.side_effect = verify_once

    with ThreadPoolExecutor(max_workers=2) as executor:
        first = executor.submit(engine.resume, "workflow-a15-3")
        assert verification_entered.wait(timeout=5)
        second = executor.submit(engine.resume, "workflow-a15-3")
        release_verification.set()
        results = (first.result(timeout=5), second.result(timeout=5))

    assert sum(
        result.sprint.phase is SprintPhase.AWAITING_COMMIT_APPROVAL for result in results
    ) == 1
    assert sum(
        result.sprint.phase is not SprintPhase.AWAITING_COMMIT_APPROVAL for result in results
    ) == 1
    execution_engine.execute.assert_called_once()
    verifier.verify.assert_called_once()
    reviewer.review.assert_called_once()
    engine._repository_committer_factory.return_value.commit.assert_not_called()


def make_candidate_request(root: Path) -> CandidateImplementationRequest:
    return CandidateImplementationRequest(
        identifier="candidate-implementation-v1-aaa",
        workflow_session_id="candidate-workflow-1",
        candidate_planning_session_id="candidate-plan-1",
        candidate_id="candidate-1",
        candidate_fingerprint="candidate-fingerprint-v1:aaa",
        candidate_plan_id="candidate-plan-output-candidate-plan-1",
        candidate_plan_fingerprint="plan-fingerprint-v1:aaa",
        execution_intent="update-compose-stack",
        repository_root=root,
        repository_branch="feature/atlas-agent",
        repository_head="abc123",
        argv=(*CODEX_WORKSPACE_EXEC_ARGV_PREFIX, "approved prompt"),
        working_directory=root,
        affected_files=(Path("compose.production.yaml"),),
        evidence_ids=("evidence-1",),
        compatibility_assessment_id="assessment-1",
        compatibility_status="compatible",
        translator_version=TRANSLATOR_VERSION,
        generated_at=datetime(2026, 8, 2, tzinfo=UTC),
    )


def make_candidate_workflow(root: Path) -> WorkflowSession:
    request = make_candidate_request(root)
    return WorkflowSession(
        identifier="candidate-workflow-1",
        request=None,
        plan=None,
        state=WorkflowSessionState.AWAITING_IMPLEMENTATION_APPROVAL,
        effect_kind=WorkflowEffectKind.REPOSITORY_CHANGE,
        source=WorkflowSource.CANDIDATE,
        candidate_metadata=CandidateWorkflowMetadata(
            candidate_planning_session_id=request.candidate_planning_session_id,
            candidate_id=request.candidate_id,
            candidate_fingerprint=request.candidate_fingerprint,
            candidate_plan_id=request.candidate_plan_id,
            candidate_plan_fingerprint=request.candidate_plan_fingerprint,
            source_recommendation_id="finding-1",
            source_subsystem="orion",
            catalog_item_id="frigate",
            target_id="atlas-compose",
            target_type="repository",
            execution_category="update",
            execution_intent=request.execution_intent,
            evidence_ids=request.evidence_ids,
            compatibility_assessment_id=request.compatibility_assessment_id,
            compatibility_status=request.compatibility_status,
            relationship_ids=("relationship-1",),
            conversion_timestamp=datetime(2026, 8, 2, tzinfo=UTC),
            core_revalidation_status="accepted_for_planning",
            core_revalidation_fingerprint=request.candidate_fingerprint,
            effect_kind=WorkflowEffectKind.REPOSITORY_CHANGE,
        ),
        candidate_implementation_request=request,
        candidate_implementation_approval_id="approval-candidate-workflow-1",
    )


def make_candidate_approval(root: Path) -> ApprovalRequest:
    request = make_candidate_request(root)
    return ApprovalRequest(
        identifier="approval-candidate-workflow-1",
        workflow_id="candidate-workflow-1",
        checkpoint_id=request.identifier,
        title="Approve exact candidate implementation request",
        requested_tool=request.argv[0],
        requested_command=request.argv,
        requested_working_directory=request.working_directory,
        rationale="Human-readable context only.",
        purpose=ApprovalPurpose.IMPLEMENTATION,
    )


class FakeCandidateValidator:
    def __init__(self, result: CandidateExecutionValidationResult) -> None:
        self.result = result
        self.calls = 0

    def validate(self, *, workflow, approval_result):
        self.calls += 1
        return self.result


class FakeCandidateVerificationValidator:
    @staticmethod
    def exact_approval_request(plan):
        return ApprovalRequest(
            identifier=f"approval-verification-{plan.workflow_session_id}",
            workflow_id=plan.workflow_session_id,
            checkpoint_id=plan.identifier,
            title="Approve exact candidate verification checks",
            requested_tool="verification",
            requested_command=("verification-suite",),
            requested_working_directory=plan.repository_root,
            rationale="Approve the exact candidate verification plan and changed-file evidence.",
            purpose=ApprovalPurpose.VERIFICATION,
        )

    def build_plan(self, workflow):
        request = workflow.candidate_implementation_request
        assert request is not None
        assert workflow.execution_result is not None
        changed_files = tuple(workflow.changed_files)
        plan = CandidateVerificationPlan(
            identifier=f"verification-plan-{workflow.identifier}",
            workflow_session_id=workflow.identifier,
            candidate_planning_session_id=request.candidate_planning_session_id,
            candidate_id=request.candidate_id,
            candidate_fingerprint=request.candidate_fingerprint,
            candidate_plan_id=request.candidate_plan_id,
            candidate_plan_fingerprint=request.candidate_plan_fingerprint,
            implementation_request_id=request.identifier,
            execution_result_id=workflow.execution_result.request_id,
            repository_root=request.repository_root,
            repository_branch=request.repository_branch,
            base_head=request.repository_head,
            post_execution_head=request.repository_head,
            baseline_status=workflow.worker_baseline_status,
            post_execution_status=None,
            changed_files=changed_files,
            changed_files_digest="test-digest",
            approved_affected_files=tuple(request.affected_files),
            verification_checks=(),
            verifier_version="test-verifier",
            generated_at=datetime.now(UTC),
        )
        approval = self.exact_approval_request(plan)
        return CandidateVerificationValidationResult(
            approved=True,
            plan=plan,
            approval_request=approval,
        )

    def placeholder_approval_request(self, workflow):
        return ApprovalRequest(
            identifier=f"approval-verification-{workflow.identifier}",
            workflow_id=workflow.identifier,
            checkpoint_id=workflow.plan.checkpoint_id,
            title=f"Approve verification of {workflow.plan.title}",
            requested_tool="verification",
            requested_command=("verification-suite",),
            requested_working_directory=workflow.plan.repository_root,
            rationale="Approve the future candidate verification phase.",
            purpose=ApprovalPurpose.VERIFICATION,
        )


def make_candidate_engine(
    root: Path,
    *,
    validation: CandidateExecutionValidationResult | None = None,
    execution_status: ExecutionStatus = ExecutionStatus.SUCCEEDED,
) -> tuple[
    WorkflowEngine,
    WorkflowStateStore,
    ApprovalRepository,
    Mock,
    Mock,
    Mock,
    FakeCandidateValidator,
]:
    state_store = WorkflowStateStore()
    state_store.create_session(make_candidate_workflow(root))
    approval_repository = ApprovalRepository()
    approval_request = make_candidate_approval(root)
    approval_repository.save_request(approval_request)
    assert approval_repository.update_decision(
        approval_request.identifier,
        ApprovalDecision(
            request=approval_request,
            status=ApprovalStatus.APPROVED,
            reviewer="tester",
        ),
    )
    implementation_request = make_candidate_request(root)
    plan = implementation_plan_from_candidate_request(implementation_request)
    execution_request = ExecutionRequest(
        identifier=implementation_request.identifier,
        plan=plan,
        argv=implementation_request.argv,
        working_directory=implementation_request.working_directory,
    )
    candidate_validator = FakeCandidateValidator(
        validation
        or CandidateExecutionValidationResult(
            approved=True,
            implementation_request=implementation_request,
            implementation_plan=plan,
            execution_request=execution_request,
            repository_snapshot=make_snapshot(root),
        )
    )
    inspector = Mock()
    inspector.inspect.return_value = make_changed_snapshot(
        root,
        modified_files=("compose.production.yaml",),
    )
    execution_engine = Mock()
    execution_engine.execute.return_value = make_execution_result(
        root,
        status=execution_status,
        error="failed" if execution_status is not ExecutionStatus.SUCCEEDED else None,
    )
    verification_engine = Mock()
    review_engine = Mock()
    engine = WorkflowEngine(
        repository_inspector_factory=Mock(return_value=inspector),
        planning_engine=Mock(),
        execution_engine=execution_engine,
        verification_engine=verification_engine,
        review_engine=review_engine,
        approval_engine=ApprovalEngine(),
        approval_repository=approval_repository,
        state_store=state_store,
        candidate_execution_validator=candidate_validator,
        candidate_verification_validator=FakeCandidateVerificationValidator(),
    )
    return (
        engine,
        state_store,
        approval_repository,
        execution_engine,
        verification_engine,
        review_engine,
        candidate_validator,
    )


def test_candidate_approved_request_executes_and_stops_at_verification_approval(tmp_path: Path) -> None:
    engine, state_store, approvals, execution_engine, verifier, reviewer, validator = make_candidate_engine(tmp_path)

    result = engine.resume("candidate-workflow-1")

    assert result.sprint.phase is SprintPhase.AWAITING_VERIFICATION_APPROVAL
    assert result.execution_result is not None
    assert result.approval_request is not None
    assert result.approval_request.identifier == "approval-verification-candidate-workflow-1"
    assert result.approval_request.requested_tool == "verification"
    assert result.approval_request.requested_command == ("verification-suite",)
    session = state_store.get_session("candidate-workflow-1")
    assert session is not None
    assert session.state is WorkflowSessionState.AWAITING_VERIFICATION_APPROVAL
    assert session.request is not None
    assert session.plan is not None
    assert session.execution_result is not None
    assert approvals.get_request("approval-verification-candidate-workflow-1") is not None
    execution_engine.execute.assert_called_once()
    executed_request = execution_engine.execute.call_args.args[0]
    assert executed_request.argv == (*CODEX_WORKSPACE_EXEC_ARGV_PREFIX, "approved prompt")
    assert executed_request.working_directory == tmp_path
    verifier.verify.assert_not_called()
    reviewer.review.assert_not_called()
    assert validator.calls == 1


def test_candidate_exact_match_resume_advances_to_verification_approval(tmp_path: Path) -> None:
    engine, state_store, approvals, execution_engine, verifier, reviewer, validator = (
        make_candidate_engine(tmp_path)
    )

    workflow = state_store.get_session("candidate-workflow-1")
    assert workflow is not None
    assert workflow.candidate_implementation_request is not None
    candidate_metadata = workflow.candidate_metadata
    assert candidate_metadata is not None

    implementation_request = workflow.candidate_implementation_request
    assert workflow.state is WorkflowSessionState.AWAITING_IMPLEMENTATION_APPROVAL
    assert candidate_metadata.candidate_id == implementation_request.candidate_id
    assert candidate_metadata.candidate_plan_id == implementation_request.candidate_plan_id
    assert candidate_metadata.candidate_fingerprint == implementation_request.candidate_fingerprint
    assert candidate_metadata.candidate_plan_fingerprint == implementation_request.candidate_plan_fingerprint
    assert candidate_metadata.execution_intent == implementation_request.execution_intent
    execution_approval = approvals.get_request(workflow.candidate_implementation_approval_id)
    assert execution_approval is not None
    assert execution_approval.decision.request.identifier == workflow.candidate_implementation_approval_id
    assert execution_approval.decision.request.checkpoint_id == implementation_request.identifier
    assert execution_approval.decision.request.requested_tool == implementation_request.argv[0]
    assert execution_approval.decision.request.requested_command == implementation_request.argv
    assert (
        execution_approval.decision.request.requested_working_directory
        == implementation_request.working_directory
    )

    result = engine.resume("candidate-workflow-1")

    assert result.error_message != "approval_evidence_mismatch"
    assert result.sprint.phase is SprintPhase.AWAITING_VERIFICATION_APPROVAL
    session = state_store.get_session("candidate-workflow-1")
    assert session is not None
    assert session.state is WorkflowSessionState.AWAITING_VERIFICATION_APPROVAL
    assert session.state is not WorkflowSessionState.BLOCKED
    execution_engine.execute.assert_called_once()
    assert session.execution_result is result.execution_result
    verifier.verify.assert_not_called()
    reviewer.review.assert_not_called()
    assert validator.calls == 1
    assert implementation_request.translator_version == TRANSLATOR_VERSION

    approval_request = result.approval_request
    assert approval_request is not None
    assert approval_request.identifier == "approval-verification-candidate-workflow-1"
    assert approval_request.purpose is ApprovalPurpose.VERIFICATION
    assert approval_request.requested_tool == "verification"
    assert approval_request.requested_command == ("verification-suite",)
    assert session.plan is not None
    assert session.execution_result is not None
    assert session.changed_files == (Path("compose.production.yaml"),)
    stored_verification_approval = approvals.get_request(
        approval_request.identifier
    )
    assert stored_verification_approval is not None

    second_result = engine.resume("candidate-workflow-1")
    assert second_result.error_message == "verification_evidence_mismatch"
    execution_engine.execute.assert_called_once()


def test_candidate_pending_validation_does_not_claim_or_execute(tmp_path: Path) -> None:
    validation = CandidateExecutionValidationResult(
        approved=False,
        failure_code=CandidateExecutionFailureCode.CORE_UNAVAILABLE,
        retryable=True,
        should_block=False,
    )
    engine, state_store, _, execution_engine, verifier, reviewer, _ = make_candidate_engine(
        tmp_path,
        validation=validation,
    )

    result = engine.resume("candidate-workflow-1")

    assert result.error_message == "core_unavailable"
    assert state_store.get_session("candidate-workflow-1").state is WorkflowSessionState.AWAITING_IMPLEMENTATION_APPROVAL
    execution_engine.execute.assert_not_called()
    verifier.verify.assert_not_called()
    reviewer.review.assert_not_called()


def test_candidate_validation_block_prevents_execution(tmp_path: Path) -> None:
    validation = CandidateExecutionValidationResult(
        approved=False,
        failure_code=CandidateExecutionFailureCode.APPROVAL_EVIDENCE_MISMATCH,
        message="Candidate implementation approval does not match persisted workflow evidence: Approval request does not match implementation request: approval requested command",
        should_block=True,
    )
    engine, state_store, _, execution_engine, _, _, _ = make_candidate_engine(
        tmp_path,
        validation=validation,
    )

    result = engine.resume("candidate-workflow-1")

    assert result.error_message == "approval_evidence_mismatch"
    assert (
        state_store.get_session("candidate-workflow-1").blocked_reason
        == "approval_evidence_mismatch: Candidate implementation approval does not match persisted workflow evidence: Approval request does not match implementation request: approval requested command"
    )
    assert state_store.get_session("candidate-workflow-1").state is WorkflowSessionState.BLOCKED
    execution_engine.execute.assert_not_called()


def test_candidate_failed_execution_blocks_without_verification_approval(tmp_path: Path) -> None:
    engine, state_store, approvals, execution_engine, verifier, reviewer, _ = make_candidate_engine(
        tmp_path,
        execution_status=ExecutionStatus.FAILED,
    )

    result = engine.resume("candidate-workflow-1")

    assert result.error_message == "execution_failed"
    session = state_store.get_session("candidate-workflow-1")
    assert session.state is WorkflowSessionState.BLOCKED
    assert session.execution_result is not None
    assert approvals.get_request("approval-verification-candidate-workflow-1") is None
    execution_engine.execute.assert_called_once()
    verifier.verify.assert_not_called()
    reviewer.review.assert_not_called()


def test_concurrent_candidate_resumes_execute_once(tmp_path: Path) -> None:
    engine, state_store, _, execution_engine, verifier, reviewer, _ = make_candidate_engine(tmp_path)

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = tuple(
            executor.map(lambda _: engine.resume("candidate-workflow-1"), range(2))
        )

    assert sum(result.error_message is None for result in results) == 1
    assert sum(
        result.sprint.phase is SprintPhase.AWAITING_VERIFICATION_APPROVAL
        for result in results
    ) == 1
    assert sum(
        result.sprint.phase is not SprintPhase.AWAITING_VERIFICATION_APPROVAL
        for result in results
    ) == 1
    assert state_store.get_session("candidate-workflow-1").state in {
        WorkflowSessionState.AWAITING_VERIFICATION_APPROVAL,
        WorkflowSessionState.BLOCKED,
    }
    execution_engine.execute.assert_called_once()
    verifier.verify.assert_not_called()
    reviewer.review.assert_not_called()


def test_worker_changed_files_are_normalized_and_baseline_independent(tmp_path: Path) -> None:
    engine, state_store, _, _, _, _, _ = make_candidate_engine(tmp_path)
    session = state_store.get_session("candidate-workflow-1")
    assert session is not None and session.candidate_implementation_request is not None
    plan = implementation_plan_from_candidate_request(session.candidate_implementation_request)
    target = Path("compose.production.yaml")
    assert engine._validate_worker_changed_files((target,), plan) == (target,)


def test_worker_empty_changed_files_fail_closed(tmp_path: Path) -> None:
    engine, state_store, _, _, _, _, _ = make_candidate_engine(tmp_path)
    session = state_store.get_session("candidate-workflow-1")
    assert session is not None and session.candidate_implementation_request is not None
    plan = implementation_plan_from_candidate_request(session.candidate_implementation_request)
    with pytest.raises(PatchApplicationError, match="worker_changed_files_empty"):
        engine._validate_worker_changed_files((), plan)


def test_worker_out_of_scope_changed_files_fail_closed(tmp_path: Path) -> None:
    engine, state_store, _, _, _, _, _ = make_candidate_engine(tmp_path)
    session = state_store.get_session("candidate-workflow-1")
    assert session is not None and session.candidate_implementation_request is not None
    plan = implementation_plan_from_candidate_request(session.candidate_implementation_request)
    with pytest.raises(PatchApplicationError, match="worker_changed_files_out_of_scope"):
        engine._validate_worker_changed_files((Path("unapproved.txt"),), plan)


def test_non_worker_changed_files_keep_checkout_scope_behavior(tmp_path: Path) -> None:
    engine, _, _, _, _, _, _ = make_candidate_engine(tmp_path)
    plan = replace(make_plan(tmp_path), affected_files=(Path("compose.production.yaml"),))
    snapshot = make_changed_snapshot(
        tmp_path,
        modified_files=("compose.production.yaml",),
    )
    assert engine._workflow_changed_files(snapshot, plan) == (Path("compose.production.yaml"),)


def test_worker_provenance_excludes_baseline_untracked_and_modified_paths(tmp_path: Path) -> None:
    engine, _, _, _, _, _, _ = make_candidate_engine(tmp_path)
    plan = make_plan(tmp_path)
    target = Path("services/atlas-agent/tests/test_execution_engine.py")
    plan = replace(plan, affected_files=(target,))
    assert engine._validate_worker_changed_files((target,), plan) == (target,)


def test_worker_success_persistence_shape_is_explicitly_representable(tmp_path: Path) -> None:
    _, state_store, _, _, _, _, _ = make_candidate_engine(tmp_path)
    session = state_store.get_session("candidate-workflow-1")
    assert session is not None
    target = Path("services/atlas-agent/tests/test_execution_engine.py")
    updated = replace(
        session,
        state=WorkflowSessionState.AWAITING_VERIFICATION_APPROVAL,
        worker_patch_applied=True,
        changed_files=(target,),
    )
    state_store._sessions[session.identifier] = updated
    restored = state_store.get_session(session.identifier)
    assert restored is not None
    assert restored.state is WorkflowSessionState.AWAITING_VERIFICATION_APPROVAL
    assert restored.worker_patch_applied is True
    assert restored.changed_files == (target,)
