"""Workflow orchestration for Atlas Agent checkpoints."""

from __future__ import annotations

import logging
from collections.abc import Callable
from pathlib import Path
from uuid import uuid4

from app.approval.engine import ApprovalEngine
from app.approval.models import ApprovalDecision, ApprovalRequest
from app.approval.repository import ApprovalRepository
from app.execution.engine import ExecutionEngine
from app.execution.models import ExecutionRequest
from app.model_providers.models import ModelResponse
from app.planning.advisor import PlanningAdvisor
from app.planning.engine import PlanningEngine
from app.repository.inspector import GitInspector
from app.review.engine import ReviewEngine
from app.verification.engine import VerificationEngine
from app.workflow.models import (
    SprintPhase,
    SprintStatus,
    WorkflowRequest,
    WorkflowResult,
    WorkflowSession,
    WorkflowSessionState,
)
from app.workflow.state import WorkflowStateStore

logger = logging.getLogger("atlas-agent")


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
        approval_repository: ApprovalRepository,
        state_store: WorkflowStateStore,
        planning_mode: str = "deterministic",
        planning_advisor: PlanningAdvisor | None = None,
    ) -> None:
        if planning_mode not in ("deterministic", "model-assisted"):
            raise ValueError(f"Unsupported planning mode: {planning_mode}")

        if planning_mode == "model-assisted" and planning_advisor is None:
            raise ValueError(
                "Model-assisted planning requires a planning advisor"
            )

        self._repository_inspector_factory = repository_inspector_factory
        self._planning_engine = planning_engine
        self._execution_engine = execution_engine
        self._verification_engine = verification_engine
        self._review_engine = review_engine
        # Retained for decision evaluation when resume support arrives in A15.3.
        self._approval_engine = approval_engine
        self._approval_repository = approval_repository
        self._state_store = state_store
        self._planning_mode = planning_mode
        self._planning_advisor = planning_advisor

    def run(
        self,
        request: WorkflowRequest,
        *,
        approval_decision: ApprovalDecision | None = None,
    ) -> WorkflowResult:
        """Plan one workflow request and pause for pre-execution approval."""

        planned_status = SprintStatus(
            checkpoint_id=request.checkpoint.identifier,
            title=request.checkpoint.title,
            goal=request.checkpoint.goal,
            phase=SprintPhase.PLANNED,
        )
        self._state_store.publish_sprint(planned_status)

        inspector = self._repository_inspector_factory(request.repository_root)
        try:
            snapshot = inspector.inspect()
            plan = self._planning_engine.plan(request.checkpoint, snapshot)
        except Exception:
            logger.exception("Workflow planning failed")
            blocked_status = SprintStatus(
                checkpoint_id=request.checkpoint.identifier,
                title=request.checkpoint.title,
                goal=request.checkpoint.goal,
                phase=SprintPhase.BLOCKED,
            )
            self._state_store.publish_sprint(blocked_status)

            return WorkflowResult(
                sprint=blocked_status,
                error_message="Workflow planning failed",
            )

        planning_analysis: ModelResponse | None = None

        if self._planning_mode == "model-assisted":
            assert self._planning_advisor is not None
            try:
                planning_analysis = self._planning_advisor.analyze(plan)
            except Exception:
                logger.exception("Model-assisted planning analysis failed")
                blocked_status = SprintStatus(
                    checkpoint_id=request.checkpoint.identifier,
                    title=request.checkpoint.title,
                    goal=request.checkpoint.goal,
                    phase=SprintPhase.BLOCKED,
                )
                self._state_store.publish_sprint(blocked_status)

                return WorkflowResult(
                    sprint=blocked_status,
                    plan=plan,
                    error_message="Model-assisted planning analysis failed",
                )

        execution_request = ExecutionRequest(
            identifier=request.execution_identifier,
            plan=plan,
            argv=request.execution_argv,
            working_directory=request.execution_workdir,
        )

        workflow_id = str(uuid4())
        approval_request = ApprovalRequest(
            identifier=f"approval-{workflow_id}",
            workflow_id=workflow_id,
            checkpoint_id=request.checkpoint.identifier,
            title=f"Approve implementation of {request.checkpoint.title}",
            requested_tool=execution_request.argv[0],
            requested_command=execution_request.argv,
            requested_working_directory=execution_request.working_directory,
            rationale="Approve the exact planned implementation operation.",
        )
        session = WorkflowSession(
            identifier=workflow_id,
            request=request,
            plan=plan,
            state=WorkflowSessionState.AWAITING_APPROVAL,
            planning_analysis=planning_analysis,
        )

        session_created = False
        try:
            self._state_store.create_session(session)
            session_created = True
            self._approval_repository.save_request(approval_request)
        except Exception:
            if session_created:
                self._state_store.delete_session(workflow_id)
            logger.exception("Pre-execution approval storage failed")
            blocked_status = SprintStatus(
                checkpoint_id=request.checkpoint.identifier,
                title=request.checkpoint.title,
                goal=request.checkpoint.goal,
                phase=SprintPhase.BLOCKED,
            )
            self._state_store.publish_sprint(blocked_status)

            return WorkflowResult(
                sprint=blocked_status,
                plan=plan,
                planning_analysis=planning_analysis,
                error_message="Pre-execution approval storage failed",
            )

        awaiting_approval_status = SprintStatus(
            checkpoint_id=request.checkpoint.identifier,
            title=request.checkpoint.title,
            goal=request.checkpoint.goal,
            phase=SprintPhase.AWAITING_APPROVAL,
        )
        self._state_store.publish_sprint(awaiting_approval_status)

        return WorkflowResult(
            sprint=awaiting_approval_status,
            plan=plan,
            planning_analysis=planning_analysis,
            approval_request=approval_request,
        )
