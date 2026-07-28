"""Tests for Atlas Agent workflow orchestration."""

from pathlib import Path
from unittest.mock import Mock

from app.execution.models import ExecutionResult, ExecutionStatus
from app.planning.models import ImplementationPlan, RoadmapCheckpoint
from app.repository.models import RepositorySnapshot
from app.review.models import ReviewReport, ReviewStatus
from app.verification.models import (
    VerificationCheck,
    VerificationReport,
    VerificationStatus,
)
from app.workflow.engine import WorkflowEngine
from app.workflow.models import SprintPhase, WorkflowRequest
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


def make_engine(
    root: Path,
    *,
    execution_result: ExecutionResult,
    verification_report: VerificationReport,
    review_report: ReviewReport,
) -> tuple[WorkflowEngine, Mock, Mock, Mock, Mock, Mock]:
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

    state_store = Mock(spec=WorkflowStateStore)

    engine = WorkflowEngine(
        repository_inspector_factory=inspector_factory,
        planning_engine=planning_engine,
        execution_engine=execution_engine,
        verification_engine=verification_engine,
        review_engine=review_engine,
        state_store=state_store,
    )

    return (
        engine,
        planning_engine,
        execution_engine,
        verification_engine,
        review_engine,
        state_store,
    )


def published_phases(state_store: Mock) -> list[SprintPhase]:
    return [
        invocation.args[0].phase
        for invocation in state_store.publish_sprint.call_args_list
    ]


def test_successful_workflow_completes_and_publishes_artifacts(
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
        state_store,
    ) = make_engine(
        tmp_path,
        execution_result=execution_result,
        verification_report=verification_report,
        review_report=review_report,
    )

    request = make_request(tmp_path)
    result = engine.run(request)

    assert result.sprint.phase is SprintPhase.COMPLETED
    assert result.execution_result is execution_result
    assert result.verification_report is verification_report
    assert result.review_report is review_report
    assert result.error_message is None

    planning_engine.plan.assert_called_once()
    execution_engine.execute.assert_called_once()
    verification_engine.verify.assert_called_once_with(
        repository_root=tmp_path,
        checks=request.verification_checks,
    )
    review_engine.review.assert_called_once()

    state_store.publish_verification.assert_called_once_with(verification_report)
    state_store.publish_review.assert_called_once_with(review_report)
    assert published_phases(state_store) == [
        SprintPhase.PLANNED,
        SprintPhase.IN_PROGRESS,
        SprintPhase.VERIFYING,
        SprintPhase.REVIEWING,
        SprintPhase.COMPLETED,
    ]


def test_execution_failure_blocks_downstream_stages(tmp_path: Path) -> None:
    execution_result = make_execution_result(
        tmp_path,
        status=ExecutionStatus.FAILED,
        error="Execution failed",
    )
    (
        engine,
        _,
        _,
        verification_engine,
        review_engine,
        state_store,
    ) = make_engine(
        tmp_path,
        execution_result=execution_result,
        verification_report=make_verification_report(tmp_path),
        review_report=make_review_report(),
    )

    result = engine.run(make_request(tmp_path))

    assert result.sprint.phase is SprintPhase.BLOCKED
    assert result.execution_result is execution_result
    assert result.verification_report is None
    assert result.review_report is None
    assert result.error_message == "Execution failed"
    verification_engine.verify.assert_not_called()
    review_engine.review.assert_not_called()
    assert published_phases(state_store) == [
        SprintPhase.PLANNED,
        SprintPhase.IN_PROGRESS,
        SprintPhase.BLOCKED,
    ]


def test_verification_failure_blocks_review(tmp_path: Path) -> None:
    verification_report = make_verification_report(
        tmp_path,
        status=VerificationStatus.FAILED,
    )
    (
        engine,
        _,
        _,
        _,
        review_engine,
        state_store,
    ) = make_engine(
        tmp_path,
        execution_result=make_execution_result(tmp_path),
        verification_report=verification_report,
        review_report=make_review_report(),
    )

    result = engine.run(make_request(tmp_path))

    assert result.sprint.phase is SprintPhase.BLOCKED
    assert result.verification_report is verification_report
    assert result.review_report is None
    assert result.error_message == "Verification failed"
    review_engine.review.assert_not_called()
    state_store.publish_verification.assert_called_once_with(verification_report)
    state_store.publish_review.assert_not_called()
    assert published_phases(state_store) == [
        SprintPhase.PLANNED,
        SprintPhase.IN_PROGRESS,
        SprintPhase.VERIFYING,
        SprintPhase.BLOCKED,
    ]


def test_review_rejection_blocks_completion(tmp_path: Path) -> None:
    review_report = make_review_report(status=ReviewStatus.CHANGES_REQUIRED)
    (
        engine,
        _,
        _,
        _,
        _,
        state_store,
    ) = make_engine(
        tmp_path,
        execution_result=make_execution_result(tmp_path),
        verification_report=make_verification_report(tmp_path),
        review_report=review_report,
    )

    result = engine.run(make_request(tmp_path))

    assert result.sprint.phase is SprintPhase.BLOCKED
    assert result.review_report is review_report
    assert result.error_message == "Review failed"
    state_store.publish_review.assert_called_once_with(review_report)
    assert published_phases(state_store) == [
        SprintPhase.PLANNED,
        SprintPhase.IN_PROGRESS,
        SprintPhase.VERIFYING,
        SprintPhase.REVIEWING,
        SprintPhase.BLOCKED,
    ]
