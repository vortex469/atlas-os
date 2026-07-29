"""Workflow orchestration for Atlas Agent checkpoints."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from app.approval.engine import ApprovalEngine
from app.approval.models import ApprovalDecision
from app.execution.engine import ExecutionEngine
from app.execution.models import ExecutionRequest, ExecutionStatus
from app.planning.engine import PlanningEngine
from app.repository.inspector import GitInspector
from app.review.engine import ReviewEngine
from app.review.models import ReviewRequest, ReviewStatus
from app.verification.engine import VerificationEngine
from app.verification.models import VerificationStatus
from app.workflow.models import (
    SprintPhase,
    SprintStatus,
    WorkflowRequest,
    WorkflowResult,
)
from app.workflow.state import WorkflowStateStore


class WorkflowEngine:
    """Coordinate repository inspection, planning, execution, verification, and review."""

    def __init__(
        self,
        *,
        repository_inspector_factory: Callable[[Path], GitInspector],
        planning_engine: PlanningEngine,
        execution_engine: ExecutionEngine,
        verification_engine: VerificationEngine,
        review_engine: ReviewEngine,
        approval_engine: ApprovalEngine,
        state_store: WorkflowStateStore,
    ) -> None:
        self._repository_inspector_factory = repository_inspector_factory
        self._planning_engine = planning_engine
        self._execution_engine = execution_engine
        self._verification_engine = verification_engine
        self._review_engine = review_engine
        self._approval_engine = approval_engine
        self._state_store = state_store

    def run(
        self,
        request: WorkflowRequest,
        *,
        approval_decision: ApprovalDecision | None = None,
    ) -> WorkflowResult:
        """Execute one workflow request."""

        planned_status = SprintStatus(
            checkpoint_id=request.checkpoint.identifier,
            title=request.checkpoint.title,
            goal=request.checkpoint.goal,
            phase=SprintPhase.PLANNED,
        )
        self._state_store.publish_sprint(planned_status)

        inspector = self._repository_inspector_factory(request.repository_root)
        snapshot = inspector.inspect()
        plan = self._planning_engine.plan(request.checkpoint, snapshot)

        in_progress_status = SprintStatus(
            checkpoint_id=request.checkpoint.identifier,
            title=request.checkpoint.title,
            goal=request.checkpoint.goal,
            phase=SprintPhase.IN_PROGRESS,
        )
        self._state_store.publish_sprint(in_progress_status)

        execution_request = ExecutionRequest(
            identifier=request.execution_identifier,
            plan=plan,
            argv=request.execution_argv,
            working_directory=request.execution_workdir,
        )

        if approval_decision is not None:
            approval_result = self._approval_engine.evaluate(approval_decision)

            if not approval_result.approved:
                blocked_status = SprintStatus(
                    checkpoint_id=request.checkpoint.identifier,
                    title=request.checkpoint.title,
                    goal=request.checkpoint.goal,
                    phase=SprintPhase.BLOCKED,
                )
                self._state_store.publish_sprint(blocked_status)

                return WorkflowResult(
                    sprint=blocked_status,
                    error_message="Approval required",
                )

        execution_result = self._execution_engine.execute(execution_request)

        if execution_result.status is not ExecutionStatus.SUCCEEDED:
            blocked_status = SprintStatus(
                checkpoint_id=request.checkpoint.identifier,
                title=request.checkpoint.title,
                goal=request.checkpoint.goal,
                phase=SprintPhase.BLOCKED,
            )
            self._state_store.publish_sprint(blocked_status)

            return WorkflowResult(
                sprint=blocked_status,
                execution_result=execution_result,
                error_message=execution_result.error,
            )


        verifying_status = SprintStatus(
            checkpoint_id=request.checkpoint.identifier,
            title=request.checkpoint.title,
            goal=request.checkpoint.goal,
            phase=SprintPhase.VERIFYING,
        )
        self._state_store.publish_sprint(verifying_status)

        verification_report = self._verification_engine.verify(
            repository_root=request.repository_root,
            checks=request.verification_checks,
        )

        self._state_store.publish_verification(verification_report)

        if verification_report.status is not VerificationStatus.PASSED:
            blocked_status = SprintStatus(
                checkpoint_id=request.checkpoint.identifier,
                title=request.checkpoint.title,
                goal=request.checkpoint.goal,
                phase=SprintPhase.BLOCKED,
            )
            self._state_store.publish_sprint(blocked_status)

            return WorkflowResult(
                sprint=blocked_status,
                execution_result=execution_result,
                verification_report=verification_report,
                error_message="Verification failed",
            )

        reviewing_status = SprintStatus(
            checkpoint_id=request.checkpoint.identifier,
            title=request.checkpoint.title,
            goal=request.checkpoint.goal,
            phase=SprintPhase.REVIEWING,
        )
        self._state_store.publish_sprint(reviewing_status)

        review_request = ReviewRequest(
            identifier=request.review_identifier,
            plan=plan,
            changed_files=plan.affected_files,
            verification_report=verification_report,
            architecture_assessments=request.architecture_assessments,
            test_evidence=request.test_evidence,
        )

        review_report = self._review_engine.review(review_request)
        self._state_store.publish_review(review_report)

        if review_report.status is not ReviewStatus.APPROVED:
            blocked_status = SprintStatus(
                checkpoint_id=request.checkpoint.identifier,
                title=request.checkpoint.title,
                goal=request.checkpoint.goal,
                phase=SprintPhase.BLOCKED,
            )
            self._state_store.publish_sprint(blocked_status)

            return WorkflowResult(
                sprint=blocked_status,
                execution_result=execution_result,
                verification_report=verification_report,
                review_report=review_report,
                error_message="Review failed",
            )

        completed_status = SprintStatus(
            checkpoint_id=request.checkpoint.identifier,
            title=request.checkpoint.title,
            goal=request.checkpoint.goal,
            phase=SprintPhase.COMPLETED,
        )
        self._state_store.publish_sprint(completed_status)

        return WorkflowResult(
            sprint=completed_status,
            execution_result=execution_result,
            verification_report=verification_report,
            review_report=review_report,
        )