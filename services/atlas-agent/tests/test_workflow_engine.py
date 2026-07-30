"""Tests for Atlas Agent workflow orchestration."""

from pathlib import Path
from unittest.mock import Mock

import pytest

from app.approval.engine import ApprovalEngine
from app.approval.models import (
    ApprovalDecision,
    ApprovalRequest,
    ApprovalStatus,
)
from app.approval.repository import ApprovalRepository
from app.context.models import AgentContext, ServiceHealth
from app.execution.models import ExecutionResult, ExecutionStatus
from app.model_providers.models import ModelResponse
from app.planning.advisor import PlanningAdvisor
from app.planning.models import ImplementationPlan, RoadmapCheckpoint
from app.repository.models import CommitResult, RepositorySnapshot
from app.review.models import ReviewReport, ReviewStatus
from app.verification.models import (
    VerificationCheck,
    VerificationReport,
    VerificationStatus,
)
from app.workflow.engine import WorkflowEngine
from app.workflow.models import (
    SprintPhase,
    WorkflowRequest,
    WorkflowSession,
    WorkflowSessionState,
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


def test_approved_workflow_resumes_exact_stored_plan(tmp_path: Path) -> None:
    (
        engine,
        state_store,
        _,
        inspector_factory,
        planning_engine,
        execution_engine,
        verification_engine,
        review_engine,
    ) = make_resume_engine(tmp_path)
    session = state_store.get_session("workflow-a15-3")

    result = engine.resume("workflow-a15-3")

    assert result.sprint.phase is SprintPhase.COMPLETED
    assert result.plan is session.plan
    assert result.execution_result is not None
    assert result.verification_report is not None
    assert result.review_report is not None
    assert result.commit_result is not None
    assert (
        state_store.get_session(session.identifier).state
        is WorkflowSessionState.COMPLETED
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
    inspector_factory.assert_called_once_with(session.request.repository_root)
    planning_engine.plan.assert_not_called()


def test_resume_reuses_snapshot_without_context_acquisition(
    tmp_path: Path,
) -> None:
    context = make_context()
    (
        engine,
        _,
        _,
        _,
        _,
        _,
        verification_engine,
        review_engine,
    ) = make_resume_engine(
        tmp_path,
        context=context,
    )

    result = engine.resume("workflow-a15-3")

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
    commit_request = (
        engine._repository_committer_factory.return_value.commit.call_args.args[0]
    )
    assert commit_request.paths == review_request.changed_files
    assert commit_request.message == "feat(agent): workflow automation"


@pytest.mark.parametrize(
    ("state", "error"),
    (
        (WorkflowSessionState.IN_PROGRESS, "Workflow already in progress"),
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
    approval_repository.update_decision(
        mismatched.identifier,
        ApprovalDecision(
            request=mismatched,
            status=ApprovalStatus.APPROVED,
            reviewer="tester",
        ),
    )

    result = engine.resume("workflow-a15-3")

    assert result.error_message == "Approval does not match workflow"
    assert (
        state_store.get_session("workflow-a15-3").state
        is WorkflowSessionState.AWAITING_APPROVAL
    )
    execution_engine.execute.assert_not_called()


@pytest.mark.parametrize(
    "approval_status",
    (ApprovalStatus.PENDING, ApprovalStatus.REJECTED),
)
def test_unapproved_decision_claims_then_blocks(
    tmp_path: Path,
    approval_status: ApprovalStatus,
) -> None:
    engine, state_store, _, _, _, execution_engine, _, _ = make_resume_engine(
        tmp_path,
        approval_status=approval_status,
    )

    result = engine.resume("workflow-a15-3")

    assert result.error_message == "Approval rejected"
    assert (
        state_store.get_session("workflow-a15-3").state
        is WorkflowSessionState.BLOCKED
    )
    execution_engine.execute.assert_not_called()


def test_duplicate_resume_does_not_replay_execution(tmp_path: Path) -> None:
    engine, _, _, _, _, execution_engine, _, _ = make_resume_engine(tmp_path)

    first = engine.resume("workflow-a15-3")
    second = engine.resume("workflow-a15-3")

    assert first.sprint.phase is SprintPhase.COMPLETED
    assert second.error_message == "Workflow already completed"
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
    engine, state_store, _, _, _, _, _, review_engine = make_resume_engine(
        tmp_path,
        verification_report=make_verification_report(
            tmp_path,
            status=VerificationStatus.FAILED,
        ),
    )

    result = engine.resume("workflow-a15-3")

    assert result.error_message == "Verification failed"
    assert (
        state_store.get_session("workflow-a15-3").state
        is WorkflowSessionState.BLOCKED
    )
    review_engine.review.assert_not_called()


def test_review_rejection_blocks_workflow(tmp_path: Path) -> None:
    engine, state_store, _, _, _, _, _, _ = make_resume_engine(
        tmp_path,
        review_report=make_review_report(
            status=ReviewStatus.CHANGES_REQUIRED,
        ),
    )

    result = engine.resume("workflow-a15-3")

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
    engine, _, _, _, _, _, _, review_engine = make_resume_engine(
        tmp_path,
        before_snapshot=before,
        after_snapshot=after,
    )

    result = engine.resume("workflow-a15-3")

    assert result.sprint.phase is SprintPhase.COMPLETED
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
    engine, _, _, _, _, _, _, review_engine = make_resume_engine(
        tmp_path,
        after_snapshot=make_changed_snapshot(
            tmp_path,
            head_commit="changed-after-execution",
        ),
    )

    result = engine.resume("workflow-a15-3")

    assert result.sprint.phase is SprintPhase.COMPLETED
    review_engine.review.assert_called_once()
    commit_request = (
        engine._repository_committer_factory.return_value.commit.call_args.args[0]
    )
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
    engine, state_store, _, _, _, _, _, _ = make_resume_engine(
        tmp_path,
        commit_error=RuntimeError("git identity missing"),
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
    engine, _, _, _, _, _, _, _ = make_resume_engine(
        tmp_path,
        review_report=make_review_report(
            status=ReviewStatus.CHANGES_REQUIRED,
        ),
    )

    engine.resume("workflow-a15-3")

    engine._repository_committer_factory.assert_not_called()
