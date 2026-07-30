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
from app.execution.models import ExecutionResult, ExecutionStatus
from app.model_providers.models import ModelResponse
from app.planning.advisor import PlanningAdvisor
from app.planning.models import ImplementationPlan, RoadmapCheckpoint
from app.repository.models import RepositorySnapshot
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
) -> VerificationReport:
    return VerificationReport(
        repository_root=root,
        results=(),
        status=status,
        duration_seconds=1.0,
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
