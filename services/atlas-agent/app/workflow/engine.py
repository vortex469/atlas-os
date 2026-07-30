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
from app.execution.models import ExecutionRequest, ExecutionStatus
from app.model_providers.models import ModelResponse
from app.planning.advisor import PlanningAdvisor
from app.planning.engine import PlanningEngine
from app.planning.models import ImplementationPlan
from app.repository.committer import GitCommitter
from app.repository.inspector import GitInspector
from app.repository.models import CommitRequest, RepositorySnapshot
from app.review.engine import ReviewEngine
from app.review.models import ReviewRequest, ReviewStatus
from app.verification.engine import VerificationEngine
from app.verification.models import VerificationStatus
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
        repository_committer_factory: Callable[[Path], GitCommitter] = GitCommitter,
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
        self._repository_committer_factory = repository_committer_factory
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

    def resume(self, workflow_id: str) -> WorkflowResult:
        """Resume one approved workflow from its stored implementation plan."""

        session = self._state_store.get_session(workflow_id)

        if session is None:
            return self._blocked_resume_result(
                workflow_id=workflow_id,
                error_message="Workflow not found",
            )

        if session.state is WorkflowSessionState.IN_PROGRESS:
            return self._blocked_session_result(
                session=session,
                error_message="Workflow already in progress",
            )

        if session.state is WorkflowSessionState.COMPLETED:
            return self._blocked_session_result(
                session=session,
                error_message="Workflow already completed",
            )

        if session.state is not WorkflowSessionState.AWAITING_APPROVAL:
            return self._blocked_session_result(
                session=session,
                error_message="Workflow is not resumable",
            )

        approval_identifier = f"approval-{workflow_id}"
        approval_result = self._approval_repository.get_request(
            approval_identifier
        )

        if approval_result is None:
            return self._blocked_session_result(
                session=session,
                error_message="Approval not found",
            )

        approval_request = approval_result.decision.request

        if not self._approval_matches_session(
            approval_identifier=approval_identifier,
            approval_request=approval_request,
            session=session,
        ):
            return self._blocked_session_result(
                session=session,
                error_message="Approval does not match workflow",
            )

        try:
            evaluated_approval = self._approval_engine.evaluate(
                approval_result.decision
            )
        except Exception:
            logger.exception("Workflow approval validation failed")
            return self._blocked_session_result(
                session=session,
                error_message="Approval is invalid",
            )

        if not self._state_store.transition_session(
            workflow_id,
            WorkflowSessionState.AWAITING_APPROVAL,
            WorkflowSessionState.IN_PROGRESS,
        ):
            return self._blocked_session_result(
                session=session,
                error_message="Workflow already resumed",
            )

        if not evaluated_approval.approved:
            self._block_claimed_session(workflow_id)
            return self._blocked_session_result(
                session=session,
                error_message="Approval rejected",
            )

        request = session.request
        plan = session.plan
        in_progress_status = self._status(session, SprintPhase.IN_PROGRESS)
        self._state_store.publish_sprint(in_progress_status)

        inspector = self._repository_inspector_factory(request.repository_root)
        try:
            before_execution = inspector.inspect()
            self._validate_pre_execution_snapshot(before_execution, plan)
        except Exception:
            logger.exception("Workflow repository validation failed")
            self._block_claimed_session(workflow_id)
            return self._blocked_session_result(
                session=session,
                error_message="Workflow repository validation failed",
            )

        execution_request = ExecutionRequest(
            identifier=request.execution_identifier,
            plan=plan,
            argv=request.execution_argv,
            working_directory=request.execution_workdir,
        )

        try:
            execution_result = self._execution_engine.execute(execution_request)
        except Exception:
            logger.exception("Workflow execution failed")
            self._block_claimed_session(workflow_id)
            return self._blocked_session_result(
                session=session,
                error_message="Workflow execution failed",
            )

        if execution_result.status is not ExecutionStatus.SUCCEEDED:
            self._block_claimed_session(workflow_id)
            return self._blocked_session_result(
                session=session,
                execution_result=execution_result,
                error_message=execution_result.error or "Execution failed",
            )

        try:
            after_execution = inspector.inspect()
            changed_files = self._workflow_changed_files(after_execution, plan)
        except Exception:
            logger.exception("Workflow change inspection failed")
            self._block_claimed_session(workflow_id)
            return self._blocked_session_result(
                session=session,
                execution_result=execution_result,
                error_message="Workflow change inspection failed",
            )

        verifying_status = self._status(session, SprintPhase.VERIFYING)
        self._state_store.publish_sprint(verifying_status)

        try:
            verification_report = self._verification_engine.verify(
                repository_root=request.repository_root,
                checks=request.verification_checks,
            )
        except Exception:
            logger.exception("Workflow verification failed")
            self._block_claimed_session(workflow_id)
            return self._blocked_session_result(
                session=session,
                execution_result=execution_result,
                error_message="Workflow verification failed",
            )

        self._state_store.publish_verification(verification_report)

        if verification_report.status is not VerificationStatus.PASSED:
            self._block_claimed_session(workflow_id)
            return self._blocked_session_result(
                session=session,
                execution_result=execution_result,
                verification_report=verification_report,
                error_message="Verification failed",
            )

        reviewing_status = self._status(session, SprintPhase.REVIEWING)
        self._state_store.publish_sprint(reviewing_status)
        review_request = ReviewRequest(
            identifier=request.review_identifier,
            plan=plan,
            changed_files=changed_files,
            verification_report=verification_report,
            architecture_assessments=request.architecture_assessments,
            test_evidence=request.test_evidence,
        )

        try:
            review_report = self._review_engine.review(review_request)
        except Exception:
            logger.exception("Workflow review failed")
            self._block_claimed_session(workflow_id)
            return self._blocked_session_result(
                session=session,
                execution_result=execution_result,
                verification_report=verification_report,
                error_message="Workflow review failed",
            )

        self._state_store.publish_review(review_report)

        if review_report.status is not ReviewStatus.APPROVED:
            self._block_claimed_session(workflow_id)
            return self._blocked_session_result(
                session=session,
                execution_result=execution_result,
                verification_report=verification_report,
                review_report=review_report,
                error_message="Review failed",
            )

        try:
            commit_request = CommitRequest(
                repository_root=plan.repository_root,
                expected_branch=plan.branch,
                expected_head=plan.head_commit,
                paths=changed_files,
                message=self._commit_message(plan.title),
            )
            commit_result = self._repository_committer_factory(
                plan.repository_root
            ).commit(commit_request)
        except Exception:
            logger.exception("Workflow commit failed")
            self._block_claimed_session(workflow_id)
            return self._blocked_session_result(
                session=session,
                execution_result=execution_result,
                verification_report=verification_report,
                review_report=review_report,
                error_message="Workflow commit failed",
            )

        self._state_store.transition_session(
            workflow_id,
            WorkflowSessionState.IN_PROGRESS,
            WorkflowSessionState.COMPLETED,
        )
        completed_status = self._status(session, SprintPhase.COMPLETED)
        self._state_store.publish_sprint(completed_status)

        return WorkflowResult(
            sprint=completed_status,
            plan=plan,
            planning_analysis=session.planning_analysis,
            approval_request=approval_request,
            execution_result=execution_result,
            verification_report=verification_report,
            review_report=review_report,
            commit_result=commit_result,
        )

    @staticmethod
    def _validate_pre_execution_snapshot(
        snapshot: RepositorySnapshot,
        plan: ImplementationPlan,
    ) -> None:
        if snapshot.root != plan.repository_root.resolve(strict=False):
            raise ValueError("Repository root differs from the approved plan")
        if snapshot.branch != plan.branch:
            raise ValueError("Repository branch differs from the approved plan")
        if snapshot.head_commit != plan.head_commit:
            raise ValueError("Repository HEAD differs from the approved plan")

        if snapshot.modified_files or snapshot.staged_files:
            raise ValueError("Repository contains pre-existing changes")
        if any(
            not WorkflowEngine._is_log_path(path)
            for path in snapshot.untracked_files
        ):
            raise ValueError("Repository contains pre-existing changes")

    @staticmethod
    def _workflow_changed_files(
        snapshot: RepositorySnapshot,
        plan: ImplementationPlan,
    ) -> tuple[Path, ...]:
        if snapshot.root != plan.repository_root.resolve(strict=False):
            raise ValueError("Repository root differs from the approved plan")
        if snapshot.branch != plan.branch:
            raise ValueError("Repository branch differs from the approved plan")

        actual = {
            Path(path)
            for path in (
                *snapshot.modified_files,
                *snapshot.staged_files,
                *snapshot.untracked_files,
            )
            if not WorkflowEngine._is_log_path(path)
        }
        allowed = set(plan.affected_files)
        if not actual:
            raise ValueError("Workflow produced no committable changes")
        if not actual.issubset(allowed):
            raise ValueError("Workflow changed files outside the approved plan")
        return tuple(sorted(actual))

    @staticmethod
    def _is_log_path(path: str | Path) -> bool:
        parts = Path(path).parts
        return bool(parts) and parts[0] == "logs"

    @staticmethod
    def _commit_message(title: str) -> str:
        normalized_title = " ".join(title.split()).lower()
        if not normalized_title:
            raise ValueError("Plan title must not be blank")
        return f"feat(agent): {normalized_title}"

    @staticmethod
    def _approval_matches_session(
        *,
        approval_identifier: str,
        approval_request: ApprovalRequest,
        session: WorkflowSession,
    ) -> bool:
        request = session.request

        return (
            approval_request.identifier == approval_identifier
            and approval_request.workflow_id == session.identifier
            and approval_request.checkpoint_id == session.plan.checkpoint_id
            and approval_request.requested_tool == request.execution_argv[0]
            and approval_request.requested_command == request.execution_argv
            and approval_request.requested_working_directory
            == request.execution_workdir
        )

    def _block_claimed_session(self, workflow_id: str) -> None:
        self._state_store.transition_session(
            workflow_id,
            WorkflowSessionState.IN_PROGRESS,
            WorkflowSessionState.BLOCKED,
        )

    def _blocked_session_result(
        self,
        *,
        session: WorkflowSession,
        error_message: str,
        execution_result=None,
        verification_report=None,
        review_report=None,
    ) -> WorkflowResult:
        blocked_status = self._status(session, SprintPhase.BLOCKED)
        self._state_store.publish_sprint(blocked_status)

        return WorkflowResult(
            sprint=blocked_status,
            plan=session.plan,
            planning_analysis=session.planning_analysis,
            execution_result=execution_result,
            verification_report=verification_report,
            review_report=review_report,
            error_message=error_message,
        )

    def _blocked_resume_result(
        self,
        *,
        workflow_id: str,
        error_message: str,
    ) -> WorkflowResult:
        blocked_status = SprintStatus(
            checkpoint_id=workflow_id,
            title="Workflow Resume",
            goal="Resume an approved workflow.",
            phase=SprintPhase.BLOCKED,
        )
        self._state_store.publish_sprint(blocked_status)
        return WorkflowResult(
            sprint=blocked_status,
            error_message=error_message,
        )

    @staticmethod
    def _status(
        session: WorkflowSession,
        phase: SprintPhase,
    ) -> SprintStatus:
        checkpoint = session.request.checkpoint
        return SprintStatus(
            checkpoint_id=checkpoint.identifier,
            title=checkpoint.title,
            goal=checkpoint.goal,
            phase=phase,
        )
