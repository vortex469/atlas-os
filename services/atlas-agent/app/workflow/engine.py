"""Workflow orchestration for Atlas Agent checkpoints."""

from __future__ import annotations

import logging
import os
from collections.abc import Callable
from dataclasses import replace
from hashlib import sha256
from pathlib import Path
from uuid import uuid4

from app.approval.engine import ApprovalEngine
from app.approval.models import (
    ApprovalDecision,
    ApprovalPurpose,
    ApprovalRequest,
    ApprovalStatus,
    CommitApprovalMetadata,
    VerificationApprovalCheck,
    VerificationApprovalEnvironment,
)
from app.approval.repository import ApprovalRepository
from app.candidate_planning.commit import (
    CandidateCommitFailureCode,
    CandidateCommitValidator,
)
from app.candidate_planning.execution import (
    CandidateExecutionFailureCode,
    CandidateExecutionValidationResult,
    CandidateExecutionValidator,
)
from app.candidate_planning.verification import (
    CandidateReviewAdapter,
    CandidateVerificationFailureCode,
    CandidateVerificationValidator,
    build_verification_evidence,
)
from app.context.models import AgentContext
from app.execution.engine import ExecutionEngine
from app.execution.exceptions import ExecutionValidationError
from app.execution.models import EnvironmentVariable, ExecutionRequest, ExecutionStatus
from app.model_providers.models import ModelResponse
from app.persistence.snapshot import AgentStatePersistenceCoordinator
from app.planning.advisor import PlanningAdvisor
from app.planning.engine import PlanningEngine
from app.planning.models import ImplementationPlan, RoadmapCheckpoint
from app.repository.committer import GitCommitter
from app.repository.inspector import GitInspector
from app.repository.models import CommitRequest, RepositorySnapshot
from app.review.advisor import ReviewAdvisor
from app.review.engine import ReviewEngine
from app.review.models import ReviewRequest, ReviewStatus
from app.verification.engine import VerificationEngine
from app.verification.models import VerificationCheck, VerificationStatus
from app.workflow.models import (
    SprintPhase,
    SprintStatus,
    WorkflowRequest,
    WorkflowResult,
    WorkflowSession,
    WorkflowSessionState,
    WorkflowSource,
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
        review_mode: str = "deterministic",
        review_advisor: ReviewAdvisor | None = None,
        state_persistence: AgentStatePersistenceCoordinator | None = None,
        candidate_execution_validator: CandidateExecutionValidator | None = None,
        candidate_verification_validator: CandidateVerificationValidator | None = None,
        candidate_review_adapter: CandidateReviewAdapter | None = None,
        candidate_commit_validator: CandidateCommitValidator | None = None,
    ) -> None:
        if planning_mode not in ("deterministic", "model-assisted"):
            raise ValueError(f"Unsupported planning mode: {planning_mode}")
        if review_mode not in ("deterministic", "model-assisted"):
            raise ValueError(f"Unsupported review mode: {review_mode}")

        if planning_mode == "model-assisted" and planning_advisor is None:
            raise ValueError(
                "Model-assisted planning requires a planning advisor"
            )
        if review_mode == "model-assisted" and review_advisor is None:
            raise ValueError(
                "Model-assisted review requires a review advisor"
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
        self._review_mode = review_mode
        self._review_advisor = review_advisor
        self._state_persistence = state_persistence
        self._candidate_execution_validator = candidate_execution_validator
        self._candidate_verification_validator = candidate_verification_validator
        self._candidate_review_adapter = candidate_review_adapter
        self._candidate_commit_validator = candidate_commit_validator

    def block_before_planning(
        self,
        request: WorkflowRequest,
        *,
        error_message: str,
    ) -> WorkflowResult:
        """Publish a blocked result before repository planning begins."""

        blocked_status = SprintStatus(
            checkpoint_id=request.checkpoint.identifier,
            title=request.checkpoint.title,
            goal=request.checkpoint.goal,
            phase=SprintPhase.BLOCKED,
        )
        self._publish_sprint(blocked_status)
        return WorkflowResult(
            sprint=blocked_status,
            error_message=error_message,
        )

    def run(
        self,
        request: WorkflowRequest,
        *,
        approval_decision: ApprovalDecision | None = None,
        context: AgentContext | None = None,
    ) -> WorkflowResult:
        """Plan one workflow request and pause for pre-execution approval."""

        planned_status = SprintStatus(
            checkpoint_id=request.checkpoint.identifier,
            title=request.checkpoint.title,
            goal=request.checkpoint.goal,
            phase=SprintPhase.PLANNED,
        )
        self._publish_sprint(planned_status)

        inspector = self._repository_inspector_factory(request.repository_root)
        try:
            snapshot = inspector.inspect()
            plan = self._planning_engine.plan(
                request.checkpoint,
                snapshot,
                context=context,
            )
        except Exception:
            logger.exception("Workflow planning failed")
            blocked_status = SprintStatus(
                checkpoint_id=request.checkpoint.identifier,
                title=request.checkpoint.title,
                goal=request.checkpoint.goal,
                phase=SprintPhase.BLOCKED,
            )
            self._publish_sprint(blocked_status)

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
                self._publish_sprint(blocked_status)

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
            context=context,
        )

        try:
            if self._state_persistence is None:
                self._state_store.create_session(session)
                try:
                    self._approval_repository.save_request(approval_request)
                except Exception:
                    self._state_store.delete_session(workflow_id)
                    raise
            else:
                self._state_persistence.mutate_aggregate(
                    lambda workflow, approvals: (
                        workflow.create_session(session),
                        approvals.save_request(approval_request),
                    )
                )
        except Exception:
            logger.exception("Pre-execution approval storage failed")
            blocked_status = SprintStatus(
                checkpoint_id=request.checkpoint.identifier,
                title=request.checkpoint.title,
                goal=request.checkpoint.goal,
                phase=SprintPhase.BLOCKED,
            )
            self._publish_sprint(blocked_status)

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
        self._publish_sprint(awaiting_approval_status)

        return WorkflowResult(
            sprint=awaiting_approval_status,
            plan=plan,
            context=context,
            planning_analysis=planning_analysis,
            approval_request=approval_request,
        )

    def resume(self, workflow_id: str) -> WorkflowResult:
        """Resume one workflow from its current approval boundary."""

        session = self._state_store.get_session(workflow_id)

        if session is None:
            return self._blocked_resume_result(
                workflow_id=workflow_id,
                error_message="Workflow not found",
            )

        if session.state in {
            WorkflowSessionState.EXECUTING,
            WorkflowSessionState.VERIFYING,
            WorkflowSessionState.COMMITTING,
        }:
            return self._session_error_result(
                session=session,
                error_message="Workflow already in progress",
            )

        if session.state is WorkflowSessionState.COMPLETED:
            if session.source is WorkflowSource.CANDIDATE and session.commit_result is not None:
                completed_status = self._status(session, SprintPhase.COMPLETED)
                self._publish_sprint(completed_status)
                return WorkflowResult(
                    sprint=completed_status,
                    plan=session.plan,
                    context=session.context,
                    planning_analysis=session.planning_analysis,
                    review_analysis=session.review_analysis,
                    execution_result=session.execution_result,
                    verification_report=session.verification_report,
                    review_report=session.review_report,
                    commit_result=session.commit_result,
                )
            return self._session_error_result(
                session=session,
                error_message="Workflow already completed",
            )

        if session.state is WorkflowSessionState.AWAITING_APPROVAL:
            if session.source is WorkflowSource.CANDIDATE:
                return self._candidate_session_result(
                    session=session,
                    phase=SprintPhase.BLOCKED,
                    error_message="Candidate workflow is not ready for implementation execution",
                )
            return self._resume_implementation(session)
        if (
            session.state
            is WorkflowSessionState.AWAITING_IMPLEMENTATION_APPROVAL
        ):
            return self._resume_candidate_implementation(session)
        if (
            session.state
            is WorkflowSessionState.AWAITING_VERIFICATION_APPROVAL
        ):
            return self._resume_verification(session)
        if session.state is WorkflowSessionState.AWAITING_COMMIT_APPROVAL:
            return self._resume_commit(session)

        return self._blocked_session_result(
            session=session,
            error_message="Workflow is not resumable",
        )

    def _resume_implementation(
        self,
        session: WorkflowSession,
    ) -> WorkflowResult:
        workflow_id = session.identifier
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

        if evaluated_approval.decision.status is ApprovalStatus.PENDING:
            return self._pending_implementation_result(
                session,
                approval_request=approval_request,
            )

        if not self._transition_session(
            workflow_id,
            WorkflowSessionState.AWAITING_APPROVAL,
            WorkflowSessionState.EXECUTING,
        ):
            return self._session_error_result(
                session=session,
                error_message="Workflow already resumed",
            )

        if not evaluated_approval.approved:
            self._block_claimed_session(
                workflow_id,
                WorkflowSessionState.EXECUTING,
            )
            return self._blocked_session_result(
                session=session,
                error_message="Approval rejected",
            )

        request = session.request
        plan = session.plan
        context = session.context
        in_progress_status = self._status(session, SprintPhase.IN_PROGRESS)
        self._publish_sprint(in_progress_status)

        inspector = self._repository_inspector_factory(request.repository_root)
        try:
            before_execution = inspector.inspect()
            self._validate_pre_execution_snapshot(before_execution, plan)
        except Exception:
            logger.exception("Workflow repository validation failed")
            self._block_claimed_session(
                workflow_id,
                WorkflowSessionState.EXECUTING,
            )
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
            self._block_claimed_session(
                workflow_id,
                WorkflowSessionState.EXECUTING,
            )
            return self._blocked_session_result(
                session=session,
                error_message="Workflow execution failed",
            )

        if execution_result.status is not ExecutionStatus.SUCCEEDED:
            self._block_claimed_session(
                workflow_id,
                WorkflowSessionState.EXECUTING,
            )
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
            self._block_claimed_session(
                workflow_id,
                WorkflowSessionState.EXECUTING,
            )
            return self._blocked_session_result(
                session=session,
                execution_result=execution_result,
                error_message="Workflow change inspection failed",
            )

        try:
            verification_approval = self._verification_approval_request(session)
            if self._state_persistence is None:
                self._approval_repository.save_request(verification_approval)
                transition_ok = self._state_store.transition_session(
                    workflow_id,
                    WorkflowSessionState.EXECUTING,
                    WorkflowSessionState.AWAITING_VERIFICATION_APPROVAL,
                    execution_result=execution_result,
                    changed_files=changed_files,
                )
            else:
                def pause_for_verification(workflow, approvals):
                    approvals.save_request(verification_approval)
                    return workflow.transition_session(
                        workflow_id,
                        WorkflowSessionState.EXECUTING,
                        WorkflowSessionState.AWAITING_VERIFICATION_APPROVAL,
                        execution_result=execution_result,
                        changed_files=changed_files,
                    )

                transition_ok = self._state_persistence.mutate_aggregate(
                    pause_for_verification
                )
        except Exception:
            logger.exception("Verification approval storage failed")
            self._block_claimed_session(
                workflow_id,
                WorkflowSessionState.EXECUTING,
            )
            return self._blocked_session_result(
                session=session,
                execution_result=execution_result,
                error_message="Verification approval storage failed",
            )

        if not transition_ok:
            return self._blocked_session_result(
                session=session,
                execution_result=execution_result,
                error_message="Workflow state transition failed",
            )

        awaiting_status = self._status(
            session,
            SprintPhase.AWAITING_VERIFICATION_APPROVAL,
        )
        self._publish_sprint(awaiting_status)
        return WorkflowResult(
            sprint=awaiting_status,
            plan=plan,
            context=context,
            planning_analysis=session.planning_analysis,
            approval_request=verification_approval,
            execution_result=execution_result,
        )

    def _resume_candidate_implementation(
        self,
        session: WorkflowSession,
    ) -> WorkflowResult:
        """Execute one approved immutable candidate implementation request."""

        if self._candidate_execution_validator is None:
            self._log_candidate_pre_execution_failure(
                session=session,
                approval_result=None,
                validation_failure_code=CandidateExecutionFailureCode.APPROVAL_EVIDENCE_MISMATCH.value,
            )
            return self._block_candidate_session(
                session=session,
                error_message=CandidateExecutionFailureCode.APPROVAL_EVIDENCE_MISMATCH.value,
            )
        approval_result = None
        approval_id = session.candidate_implementation_approval_id
        if approval_id is not None:
            approval_result = self._approval_repository.get_request(approval_id)
            if approval_result is not None:
                try:
                    approval_result = self._approval_engine.evaluate(
                        approval_result.decision
                    )
                except Exception:
                    logger.exception("Candidate approval validation failed")
                    self._log_candidate_pre_execution_failure(
                        session=session,
                        approval_result=approval_result,
                        validation_failure_code=CandidateExecutionFailureCode.APPROVAL_EVIDENCE_MISMATCH.value,
                    )
                    return self._block_candidate_session(
                        session=session,
                        error_message=CandidateExecutionFailureCode.APPROVAL_EVIDENCE_MISMATCH.value,
                    )

        validation = self._candidate_execution_validator.validate(
            workflow=session,
            approval_result=approval_result,
        )
        if not validation.approved:
            self._log_candidate_pre_execution_failure(
                session=session,
                approval_result=approval_result,
                validation_failure_code=(
                    validation.failure_code.value
                    if validation.failure_code is not None
                    else "unknown"
                ),
            )
            return self._candidate_validation_failure_result(session, validation)

        execution_request = validation.execution_request
        implementation_plan = validation.implementation_plan
        if execution_request is None or implementation_plan is None:
            self._log_candidate_pre_execution_failure(
                session=session,
                approval_result=approval_result,
                validation_failure_code=CandidateExecutionFailureCode.APPROVAL_EVIDENCE_MISMATCH.value,
            )
            return self._block_candidate_session(
                session=session,
                error_message=CandidateExecutionFailureCode.APPROVAL_EVIDENCE_MISMATCH.value,
            )
        workflow_request = self._candidate_workflow_request(
            execution_request=execution_request,
            plan=implementation_plan,
        )
        if not self._transition_session(
            session.identifier,
            WorkflowSessionState.AWAITING_IMPLEMENTATION_APPROVAL,
            WorkflowSessionState.EXECUTING,
            request=workflow_request,
            plan=implementation_plan,
        ):
            current_session = self._state_store.get_session(session.identifier)
            self._log_candidate_pre_execution_failure(
                session=session,
                approval_result=approval_result,
                validation_failure_code="invalid_workflow_state",
                cas_current_state=(
                    current_session.state.value
                    if current_session is not None
                    else None
                ),
            )
            return self._session_error_result(
                session=session,
                error_message="Workflow already resumed",
            )

        claimed_session = replace(
            session,
            state=WorkflowSessionState.EXECUTING,
            request=workflow_request,
            plan=implementation_plan,
        )
        in_progress_status = self._status(claimed_session, SprintPhase.IN_PROGRESS)
        self._publish_sprint(in_progress_status)

        try:
            execution_result = self._execution_engine.execute(execution_request)
        except ExecutionValidationError:
            logger.exception("Candidate execution denied by tool policy")
            self._block_claimed_session(
                session.identifier,
                WorkflowSessionState.EXECUTING,
            )
            return self._blocked_session_result(
                session=claimed_session,
                error_message=CandidateExecutionFailureCode.TOOL_POLICY_DENIED.value,
            )
        except Exception:
            logger.exception("Candidate execution failed")
            self._block_claimed_session(
                session.identifier,
                WorkflowSessionState.EXECUTING,
            )
            return self._blocked_session_result(
                session=claimed_session,
                error_message=CandidateExecutionFailureCode.EXECUTION_FAILED.value,
            )

        if execution_result.status is not ExecutionStatus.SUCCEEDED:
            self._transition_session(
                session.identifier,
                WorkflowSessionState.EXECUTING,
                WorkflowSessionState.BLOCKED,
                execution_result=execution_result,
            )
            return self._blocked_session_result(
                session=claimed_session,
                execution_result=execution_result,
                error_message=CandidateExecutionFailureCode.EXECUTION_FAILED.value,
            )

        try:
            inspector = self._repository_inspector_factory(
                execution_request.plan.repository_root
            )
            after_execution = inspector.inspect()
            changed_files = self._workflow_changed_files(
                after_execution,
                implementation_plan,
            )
            verification_approval = self._candidate_verification_approval_request(
                claimed_session
            )
            if self._state_persistence is None:
                self._approval_repository.save_request(verification_approval)
                transition_ok = self._state_store.transition_session(
                    session.identifier,
                    WorkflowSessionState.EXECUTING,
                    WorkflowSessionState.AWAITING_VERIFICATION_APPROVAL,
                    execution_result=execution_result,
                    changed_files=changed_files,
                )
            else:

                def pause_for_verification(workflow, approvals):
                    approvals.save_request(verification_approval)
                    return workflow.transition_session(
                        session.identifier,
                        WorkflowSessionState.EXECUTING,
                        WorkflowSessionState.AWAITING_VERIFICATION_APPROVAL,
                        execution_result=execution_result,
                        changed_files=changed_files,
                    )

                transition_ok = self._state_persistence.mutate_aggregate(
                    pause_for_verification
                )
        except Exception:
            logger.exception("Candidate verification approval storage failed")
            self._block_claimed_session(
                session.identifier,
                WorkflowSessionState.EXECUTING,
            )
            return self._blocked_session_result(
                session=claimed_session,
                execution_result=execution_result,
                error_message=CandidateExecutionFailureCode.PERSISTENCE_FAILED.value,
            )

        if not transition_ok:
            return self._blocked_session_result(
                session=claimed_session,
                execution_result=execution_result,
                error_message="Workflow state transition failed",
            )

        awaiting_status = self._status(
            claimed_session,
            SprintPhase.AWAITING_VERIFICATION_APPROVAL,
        )
        self._publish_sprint(awaiting_status)
        return WorkflowResult(
            sprint=awaiting_status,
            plan=implementation_plan,
            context=claimed_session.context,
            planning_analysis=claimed_session.planning_analysis,
            approval_request=verification_approval,
            execution_result=execution_result,
        )

    def _log_candidate_pre_execution_failure(
        self,
        *,
        session: WorkflowSession,
        approval_result,
        validation_failure_code: str,
        cas_current_state: str | None = None,
    ) -> None:
        """Emit safe, structured diagnostics before candidate execution is claimed."""

        implementation_request = session.candidate_implementation_request
        approval_status = (
            approval_result.decision.status.value
            if approval_result is not None
            else None
        )
        logger.warning(
            "candidate_pre_execution_failure",
            extra={
                "workflow_id": session.identifier,
                "workflow_state": session.state.value,
                "candidate_implementation_request_id": (
                    implementation_request.identifier
                    if implementation_request is not None
                    else None
                ),
                "approval_request_id": session.candidate_implementation_approval_id,
                "approval_decision_status": approval_status,
                "validation_failure_code": validation_failure_code,
                "cas_expected_state": WorkflowSessionState.AWAITING_IMPLEMENTATION_APPROVAL.value,
                "cas_current_state": cas_current_state or session.state.value,
                "execution_claimed": False,
            },
        )

    def _resume_candidate_verification(
        self,
        session: WorkflowSession,
    ) -> WorkflowResult:
        """Run exact approved candidate verification and deterministic review."""

        if (
            self._candidate_verification_validator is None
            or self._candidate_review_adapter is None
        ):
            return self._block_candidate_verification_session(
                session=session,
                error_message=CandidateVerificationFailureCode.VERIFICATION_EVIDENCE_MISMATCH.value,
            )

        plan = session.candidate_verification_plan
        approval_identifier = f"approval-verification-{session.identifier}"
        if plan is None:
            prepared = self._prepare_candidate_verification_plan(session)
            if prepared.error_message is not None or prepared.approval_request is not None:
                return prepared
            refreshed = self._state_store.get_session(session.identifier)
            if refreshed is None:
                return self._block_candidate_verification_session(
                    session=session,
                    error_message=CandidateVerificationFailureCode.PERSISTENCE_FAILED.value,
                )
            session = refreshed

        approval_result = self._approval_repository.get_request(approval_identifier)
        validation = self._candidate_verification_validator.validate_for_execution(
            workflow=session,
            approval_result=approval_result,
        )
        if not validation.approved:
            return self._candidate_verification_failure_result(session, validation)

        if not self._transition_session(
            session.identifier,
            WorkflowSessionState.AWAITING_VERIFICATION_APPROVAL,
            WorkflowSessionState.VERIFYING,
        ):
            return self._session_error_result(
                session=session,
                error_message="Workflow already resumed",
            )

        claimed_session = replace(session, state=WorkflowSessionState.VERIFYING)
        verifying_status = self._status(claimed_session, SprintPhase.VERIFYING)
        self._publish_sprint(verifying_status)

        verification_plan = validation.plan
        if verification_plan is None:
            self._block_claimed_session(session.identifier, WorkflowSessionState.VERIFYING)
            return self._blocked_session_result(
                session=claimed_session,
                error_message=CandidateVerificationFailureCode.VERIFICATION_EVIDENCE_MISMATCH.value,
            )

        started_at = self._candidate_verification_validator._clock()
        try:
            verification_report = self._verification_engine.verify(
                repository_root=verification_plan.repository_root,
                checks=validation.checks,
                context=session.context,
            )
        except Exception:
            logger.exception("Candidate verification failed")
            self._block_claimed_session(session.identifier, WorkflowSessionState.VERIFYING)
            return self._blocked_session_result(
                session=claimed_session,
                execution_result=session.execution_result,
                error_message=CandidateVerificationFailureCode.VERIFICATION_FAILED.value,
            )
        completed_at = self._candidate_verification_validator._clock()
        verification_evidence = build_verification_evidence(
            plan=verification_plan,
            workflow=session,
            report=verification_report,
            started_at=started_at,
            completed_at=completed_at,
        )
        self._publish_verification(verification_report)

        if verification_report.status is not VerificationStatus.PASSED:
            self._transition_session(
                session.identifier,
                WorkflowSessionState.VERIFYING,
                WorkflowSessionState.BLOCKED,
                verification_report=verification_report,
                candidate_verification_evidence=verification_evidence,
                blocked_reason=CandidateVerificationFailureCode.VERIFICATION_FAILED.value,
            )
            return self._blocked_session_result(
                session=claimed_session,
                execution_result=session.execution_result,
                verification_report=verification_report,
                error_message=CandidateVerificationFailureCode.VERIFICATION_FAILED.value,
            )

        reviewing_status = self._status(claimed_session, SprintPhase.REVIEWING)
        self._publish_sprint(reviewing_status)
        commit_request = CommitRequest(
            repository_root=verification_plan.repository_root,
            expected_branch=verification_plan.repository_branch,
            expected_head=verification_plan.base_head,
            paths=verification_plan.changed_files,
            message="feat(agent): update compose stack candidate",
        )
        try:
            evidence = self._repository_inspector_factory(
                verification_plan.repository_root
            ).reviewed_change_evidence(
                reviewed_files=commit_request.paths,
                expected_branch=commit_request.expected_branch,
                expected_head=commit_request.expected_head,
                commit_message=commit_request.message,
            )
            review_result = self._candidate_review_adapter.review(
                workflow=session,
                verification_plan=verification_plan,
                verification_evidence=verification_evidence,
                verification_report=verification_report,
                reviewed_content_fingerprint=evidence.fingerprint,
            )
        except Exception:
            logger.exception("Candidate review failed")
            self._transition_session(
                session.identifier,
                WorkflowSessionState.VERIFYING,
                WorkflowSessionState.BLOCKED,
                verification_report=verification_report,
                candidate_verification_evidence=verification_evidence,
                blocked_reason=CandidateVerificationFailureCode.REVIEW_FAILED.value,
            )
            return self._blocked_session_result(
                session=claimed_session,
                execution_result=session.execution_result,
                verification_report=verification_report,
                error_message=CandidateVerificationFailureCode.REVIEW_FAILED.value,
            )

        if not review_result.approved or review_result.review_report is None:
            code = review_result.failure_code or CandidateVerificationFailureCode.REVIEW_FAILED
            self._transition_session(
                session.identifier,
                WorkflowSessionState.VERIFYING,
                WorkflowSessionState.BLOCKED,
                verification_report=verification_report,
                candidate_verification_evidence=verification_evidence,
                candidate_review_result=review_result.candidate_review_result,
                blocked_reason=code.value,
            )
            return self._blocked_session_result(
                session=claimed_session,
                execution_result=session.execution_result,
                verification_report=verification_report,
                review_report=review_result.review_report,
                error_message=code.value,
            )

        review_report = review_result.review_report
        self._publish_review(review_report)
        commit_approval = self._commit_approval_request(
            session=session,
            commit_request=commit_request,
            fingerprint=evidence.fingerprint,
        )
        artifacts = {
            "verification_report": verification_report,
            "candidate_verification_evidence": verification_evidence,
            "review_report": review_report,
            "candidate_review_result": review_result.candidate_review_result,
            "commit_request": commit_request,
            "reviewed_files": evidence.reviewed_files,
            "expected_branch": evidence.expected_branch,
            "expected_head": evidence.expected_head,
            "reviewed_content_fingerprint": evidence.fingerprint,
        }
        try:
            if self._state_persistence is None:
                self._approval_repository.save_request(commit_approval)
                transition_ok = self._state_store.transition_session(
                    session.identifier,
                    WorkflowSessionState.VERIFYING,
                    WorkflowSessionState.AWAITING_COMMIT_APPROVAL,
                    **artifacts,
                )
            else:

                def pause_for_commit(workflow, approvals):
                    approvals.save_request(commit_approval)
                    return workflow.transition_session(
                        session.identifier,
                        WorkflowSessionState.VERIFYING,
                        WorkflowSessionState.AWAITING_COMMIT_APPROVAL,
                        **artifacts,
                    )

                transition_ok = self._state_persistence.mutate_aggregate(
                    pause_for_commit
                )
        except Exception:
            logger.exception("Candidate commit approval storage failed")
            self._transition_session(
                session.identifier,
                WorkflowSessionState.VERIFYING,
                WorkflowSessionState.BLOCKED,
                verification_report=verification_report,
                candidate_verification_evidence=verification_evidence,
                review_report=review_report,
                candidate_review_result=review_result.candidate_review_result,
                blocked_reason=CandidateVerificationFailureCode.COMMIT_APPROVAL_CREATION_FAILED.value,
            )
            return self._blocked_session_result(
                session=claimed_session,
                execution_result=session.execution_result,
                verification_report=verification_report,
                review_report=review_report,
                error_message=CandidateVerificationFailureCode.COMMIT_APPROVAL_CREATION_FAILED.value,
            )

        if not transition_ok:
            return self._blocked_session_result(
                session=claimed_session,
                execution_result=session.execution_result,
                verification_report=verification_report,
                review_report=review_report,
                error_message=CandidateVerificationFailureCode.PERSISTENCE_FAILED.value,
            )
        awaiting_commit_status = self._status(
            claimed_session,
            SprintPhase.AWAITING_COMMIT_APPROVAL,
        )
        self._publish_sprint(awaiting_commit_status)
        return WorkflowResult(
            sprint=awaiting_commit_status,
            plan=session.plan,
            context=session.context,
            planning_analysis=session.planning_analysis,
            approval_request=commit_approval,
            execution_result=session.execution_result,
            verification_report=verification_report,
            review_report=review_report,
        )

    def _prepare_candidate_verification_plan(
        self,
        session: WorkflowSession,
    ) -> WorkflowResult:
        assert self._candidate_verification_validator is not None
        built = self._candidate_verification_validator.build_plan(session)
        if not built.approved or built.plan is None or built.approval_request is None:
            return self._candidate_verification_failure_result(session, built)
        exact = built.approval_request
        placeholder = self._candidate_verification_validator.placeholder_approval_request(
            session
        )
        approval_identifier = exact.identifier
        try:
            if self._state_persistence is None:
                current = self._approval_repository.get_request(approval_identifier)
                if current is None:
                    self._approval_repository.save_request(exact)
                elif current.decision.request == placeholder:
                    ok = self._approval_repository.supersede_pending_request(
                        identifier=approval_identifier,
                        expected_request=placeholder,
                        replacement_request=exact,
                    )
                    if not ok:
                        return self._block_candidate_verification_session(
                            session=session,
                            error_message=CandidateVerificationFailureCode.VERIFICATION_EVIDENCE_MISMATCH.value,
                        )
                elif current.decision.request != exact:
                    return self._block_candidate_verification_session(
                        session=session,
                        error_message=CandidateVerificationFailureCode.VERIFICATION_EVIDENCE_MISMATCH.value,
                    )
                current_session = self._state_store.get_session(session.identifier)
                if current_session is None:
                    raise ValueError("Workflow session missing")
                persisted = self._state_store.transition_session(
                    session.identifier,
                    WorkflowSessionState.AWAITING_VERIFICATION_APPROVAL,
                    WorkflowSessionState.AWAITING_VERIFICATION_APPROVAL,
                    candidate_verification_plan=built.plan,
                )
                if not persisted:
                    return self._block_candidate_verification_session(
                        session=session,
                        error_message=CandidateVerificationFailureCode.PERSISTENCE_FAILED.value,
                    )
            else:

                def persist_plan_and_approval(workflow, approvals):
                    current_session = workflow.get_session(session.identifier)
                    if current_session is None:
                        raise ValueError("Workflow session missing")
                    current = approvals.get_request(approval_identifier)
                    if current is None:
                        approvals.save_request(exact)
                    elif current.decision.request == placeholder:
                        ok = approvals.supersede_pending_request(
                            identifier=approval_identifier,
                            expected_request=placeholder,
                            replacement_request=exact,
                        )
                        if not ok:
                            return False
                    elif current.decision.request != exact:
                        return False
                    workflow.sessions[session.identifier] = replace(
                        current_session,
                        candidate_verification_plan=built.plan,
                    )
                    return True

                ok = self._state_persistence.mutate_aggregate(
                    persist_plan_and_approval
                )
                if not ok:
                    return self._block_candidate_verification_session(
                        session=session,
                        error_message=CandidateVerificationFailureCode.VERIFICATION_EVIDENCE_MISMATCH.value,
                    )
        except Exception:
            logger.exception("Candidate verification approval preparation failed")
            return self._block_candidate_verification_session(
                session=session,
                error_message=CandidateVerificationFailureCode.PERSISTENCE_FAILED.value,
            )
        awaiting_status = self._status(
            session,
            SprintPhase.AWAITING_VERIFICATION_APPROVAL,
        )
        self._publish_sprint(awaiting_status)
        return WorkflowResult(
            sprint=awaiting_status,
            plan=session.plan,
            context=session.context,
            planning_analysis=session.planning_analysis,
            approval_request=exact,
            execution_result=session.execution_result,
        )

    def _candidate_verification_failure_result(
        self,
        session: WorkflowSession,
        validation,
    ) -> WorkflowResult:
        code = validation.failure_code or CandidateVerificationFailureCode.VERIFICATION_EVIDENCE_MISMATCH
        message = code.value
        if validation.retryable:
            return self._candidate_session_result(
                session=session,
                phase=SprintPhase.AWAITING_VERIFICATION_APPROVAL,
                error_message=message,
            )
        if validation.should_block:
            return self._block_candidate_verification_session(
                session=session,
                error_message=message,
            )
        return self._candidate_session_result(
            session=session,
            phase=SprintPhase.BLOCKED,
            error_message=message,
        )

    def _block_candidate_verification_session(
        self,
        *,
        session: WorkflowSession,
        error_message: str,
    ) -> WorkflowResult:
        self._transition_session(
            session.identifier,
            session.state,
            WorkflowSessionState.BLOCKED,
            blocked_reason=error_message,
        )
        return self._candidate_session_result(
            session=session,
            phase=SprintPhase.BLOCKED,
            error_message=error_message,
        )

    def _resume_verification(
        self,
        session: WorkflowSession,
    ) -> WorkflowResult:
        if session.source is WorkflowSource.CANDIDATE:
            return self._resume_candidate_verification(session)

        workflow_id = session.identifier
        approval_identifier = f"approval-verification-{workflow_id}"
        approval_result = self._approval_repository.get_request(
            approval_identifier
        )

        if approval_result is None:
            return self._waiting_verification_result(session)

        approval_request = approval_result.decision.request
        try:
            expected_request = self._verification_approval_request(session)
        except Exception:
            logger.exception("Workflow approval validation failed")
            return self._block_verification_session(
                session=session,
                error_message="Approval is invalid",
            )
        if approval_request != expected_request:
            return self._block_verification_session(
                session=session,
                error_message="Approval does not match workflow",
            )

        try:
            evaluated_approval = self._approval_engine.evaluate(
                approval_result.decision
            )
        except Exception:
            logger.exception("Workflow approval validation failed")
            return self._block_verification_session(
                session=session,
                error_message="Approval is invalid",
            )

        if evaluated_approval.decision.status is ApprovalStatus.PENDING:
            return self._waiting_verification_result(
                session,
                approval_request=approval_request,
            )

        if not evaluated_approval.approved:
            return self._block_verification_session(
                session=session,
                error_message="Approval rejected",
            )

        if not self._transition_session(
            workflow_id,
            WorkflowSessionState.AWAITING_VERIFICATION_APPROVAL,
            WorkflowSessionState.VERIFYING,
        ):
            return self._session_error_result(
                session=session,
                error_message="Workflow already resumed",
            )

        request = session.request
        plan = session.plan
        context = session.context
        execution_result = session.execution_result
        changed_files = session.changed_files
        if execution_result is None or not changed_files:
            self._block_claimed_session(
                workflow_id,
                WorkflowSessionState.VERIFYING,
            )
            return self._blocked_session_result(
                session=session,
                error_message="Workflow execution artifacts are missing",
            )

        verifying_status = self._status(session, SprintPhase.VERIFYING)
        self._publish_sprint(verifying_status)

        try:
            verification_checks = self._rehydrate_verification_checks(
                request.verification_checks
            )
            verification_report = self._verification_engine.verify(
                repository_root=request.repository_root,
                checks=verification_checks,
                context=context,
            )
        except ValueError as exc:
            self._block_claimed_session(
                workflow_id,
                WorkflowSessionState.VERIFYING,
            )
            return self._blocked_session_result(
                session=session,
                execution_result=execution_result,
                error_message=str(exc),
            )
        except Exception:
            logger.exception("Workflow verification failed")
            self._block_claimed_session(
                workflow_id,
                WorkflowSessionState.VERIFYING,
            )
            return self._blocked_session_result(
                session=session,
                execution_result=execution_result,
                error_message="Workflow verification failed",
            )

        self._publish_verification(verification_report)

        if verification_report.status is not VerificationStatus.PASSED:
            self._block_claimed_session(
                workflow_id,
                WorkflowSessionState.VERIFYING,
            )
            return self._blocked_session_result(
                session=session,
                execution_result=execution_result,
                verification_report=verification_report,
                error_message="Verification failed",
            )

        reviewing_status = self._status(session, SprintPhase.REVIEWING)
        self._publish_sprint(reviewing_status)
        review_request = ReviewRequest(
            identifier=request.review_identifier,
            plan=plan,
            changed_files=changed_files,
            verification_report=verification_report,
            context=context,
            architecture_assessments=request.architecture_assessments,
            test_evidence=request.test_evidence,
        )

        try:
            review_report = self._review_engine.review(review_request)
        except Exception:
            logger.exception("Workflow review failed")
            self._block_claimed_session(
                workflow_id,
                WorkflowSessionState.VERIFYING,
            )
            return self._blocked_session_result(
                session=session,
                execution_result=execution_result,
                verification_report=verification_report,
                error_message="Workflow review failed",
            )

        self._publish_review(review_report)

        if review_report.status is not ReviewStatus.APPROVED:
            self._block_claimed_session(
                workflow_id,
                WorkflowSessionState.VERIFYING,
            )
            return self._blocked_session_result(
                session=session,
                execution_result=execution_result,
                verification_report=verification_report,
                review_report=review_report,
                error_message="Review failed",
            )

        review_analysis: ModelResponse | None = None
        if self._review_mode == "model-assisted":
            assert self._review_advisor is not None
            try:
                review_analysis = self._review_advisor.analyze(
                    request=review_request,
                    report=review_report,
                )
            except Exception:
                logger.exception("Model-assisted review analysis failed")
                self._transition_session(
                    workflow_id,
                    WorkflowSessionState.VERIFYING,
                    WorkflowSessionState.BLOCKED,
                    verification_report=verification_report,
                    review_report=review_report,
                )
                return self._blocked_session_result(
                    session=session,
                    execution_result=execution_result,
                    verification_report=verification_report,
                    review_report=review_report,
                    error_message="Model-assisted review analysis failed",
                )

        commit_request = CommitRequest(
            repository_root=plan.repository_root,
            expected_branch=plan.branch,
            expected_head=plan.head_commit,
            paths=changed_files,
            message=self._commit_message(plan.title),
        )
        try:
            evidence = self._repository_inspector_factory(
                plan.repository_root
            ).reviewed_change_evidence(
                reviewed_files=commit_request.paths,
                expected_branch=commit_request.expected_branch,
                expected_head=commit_request.expected_head,
                commit_message=commit_request.message,
            )
            commit_approval = self._commit_approval_request(
                session=session,
                commit_request=commit_request,
                fingerprint=evidence.fingerprint,
            )
            artifacts = {
                "verification_report": verification_report,
                "review_report": review_report,
                "review_analysis": review_analysis,
                "commit_request": commit_request,
                "reviewed_files": evidence.reviewed_files,
                "expected_branch": evidence.expected_branch,
                "expected_head": evidence.expected_head,
                "reviewed_content_fingerprint": evidence.fingerprint,
            }
            if self._state_persistence is None:
                self._approval_repository.save_request(commit_approval)
                transition_ok = self._state_store.transition_session(
                    workflow_id,
                    WorkflowSessionState.VERIFYING,
                    WorkflowSessionState.AWAITING_COMMIT_APPROVAL,
                    **artifacts,
                )
            else:
                def pause_for_commit(workflow, approvals):
                    approvals.save_request(commit_approval)
                    return workflow.transition_session(
                        workflow_id,
                        WorkflowSessionState.VERIFYING,
                        WorkflowSessionState.AWAITING_COMMIT_APPROVAL,
                        **artifacts,
                    )

                transition_ok = self._state_persistence.mutate_aggregate(
                    pause_for_commit
                )
        except Exception:
            logger.exception("Commit approval storage failed")
            self._block_claimed_session(
                workflow_id,
                WorkflowSessionState.VERIFYING,
            )
            return self._blocked_session_result(
                session=session,
                execution_result=execution_result,
                verification_report=verification_report,
                review_report=review_report,
                error_message="Commit approval storage failed",
            )

        if not transition_ok:
            return self._blocked_session_result(
                session=session,
                execution_result=execution_result,
                verification_report=verification_report,
                review_report=review_report,
                error_message="Workflow state transition failed",
            )
        awaiting_commit_status = self._status(
            session,
            SprintPhase.AWAITING_COMMIT_APPROVAL,
        )
        self._publish_sprint(awaiting_commit_status)

        return WorkflowResult(
            sprint=awaiting_commit_status,
            plan=plan,
            context=context,
            planning_analysis=session.planning_analysis,
            review_analysis=review_analysis,
            approval_request=commit_approval,
            execution_result=execution_result,
            verification_report=verification_report,
            review_report=review_report,
        )

    def _resume_commit(self, session: WorkflowSession) -> WorkflowResult:
        if session.source is WorkflowSource.CANDIDATE:
            return self._resume_candidate_commit(session)

        workflow_id = session.identifier
        approval_identifier = f"approval-commit-{workflow_id}"
        approval_result = self._approval_repository.get_request(approval_identifier)
        if approval_result is None:
            return self._waiting_commit_result(session)
        commit_request = session.commit_request
        fingerprint = session.reviewed_content_fingerprint
        if commit_request is None or fingerprint is None:
            return self._block_commit_session(
                session=session,
                error_message="Workflow commit artifacts are missing",
            )
        expected_approval = self._commit_approval_request(
            session=session,
            commit_request=commit_request,
            fingerprint=fingerprint,
        )
        if approval_result.decision.request != expected_approval:
            return self._block_commit_session(
                session=session,
                error_message="Approval does not match workflow",
            )
        try:
            evaluated_approval = self._approval_engine.evaluate(
                approval_result.decision
            )
        except Exception:
            logger.exception("Workflow commit approval validation failed")
            return self._block_commit_session(
                session=session,
                error_message="Approval is invalid",
            )
        if evaluated_approval.decision.status is ApprovalStatus.PENDING:
            return self._waiting_commit_result(
                session,
                approval_request=expected_approval,
            )
        if not evaluated_approval.approved:
            return self._block_commit_session(
                session=session,
                error_message="Approval rejected",
            )
        if not self._transition_session(
            workflow_id,
            WorkflowSessionState.AWAITING_COMMIT_APPROVAL,
            WorkflowSessionState.COMMITTING,
        ):
            return self._session_error_result(
                session=session,
                error_message="Workflow already resumed",
            )

        committing_status = self._status(session, SprintPhase.COMMITTING)
        self._publish_sprint(committing_status)
        try:
            current = self._repository_inspector_factory(
                commit_request.repository_root
            ).reviewed_change_evidence(
                reviewed_files=session.reviewed_files,
                expected_branch=session.expected_branch,
                expected_head=session.expected_head,
                commit_message=commit_request.message,
            )
            if current.fingerprint != fingerprint:
                raise ValueError("Reviewed repository evidence changed")
        except Exception:
            logger.exception("Workflow commit evidence validation failed")
            self._block_claimed_session(
                workflow_id,
                WorkflowSessionState.COMMITTING,
            )
            return self._blocked_session_result(
                session=session,
                execution_result=session.execution_result,
                verification_report=session.verification_report,
                review_report=session.review_report,
                error_message="Workflow commit evidence validation failed",
            )
        try:
            commit_result = self._repository_committer_factory(
                commit_request.repository_root
            ).commit(commit_request)
        except Exception:
            logger.exception("Workflow commit failed")
            self._block_claimed_session(
                workflow_id,
                WorkflowSessionState.COMMITTING,
            )
            return self._blocked_session_result(
                session=session,
                execution_result=session.execution_result,
                verification_report=session.verification_report,
                review_report=session.review_report,
                error_message="Workflow commit failed",
            )

        self._transition_session(
            workflow_id,
            WorkflowSessionState.COMMITTING,
            WorkflowSessionState.COMPLETED,
            commit_result=commit_result,
        )
        completed_status = self._status(session, SprintPhase.COMPLETED)
        self._publish_sprint(completed_status)
        return WorkflowResult(
            sprint=completed_status,
            plan=session.plan,
            context=session.context,
            planning_analysis=session.planning_analysis,
            review_analysis=session.review_analysis,
            approval_request=expected_approval,
            execution_result=session.execution_result,
            verification_report=session.verification_report,
            review_report=session.review_report,
            commit_result=commit_result,
        )

    def _candidate_commit_failure_result(
        self,
        session: WorkflowSession,
        validation,
    ) -> WorkflowResult:
        code = validation.failure_code or CandidateCommitFailureCode.COMMIT_APPROVAL_EVIDENCE_MISMATCH
        if validation.retryable:
            return self._candidate_session_result(
                session=session,
                phase=SprintPhase.AWAITING_COMMIT_APPROVAL,
                error_message=code.value,
            )
        return self._block_candidate_commit_session(
            session=session,
            error_message=code.value,
        )

    def _block_candidate_commit_session(
        self,
        *,
        session: WorkflowSession,
        error_message: str,
    ) -> WorkflowResult:
        self._transition_session(
            session.identifier,
            session.state,
            WorkflowSessionState.BLOCKED,
            blocked_reason=error_message,
        )
        return self._candidate_session_result(
            session=session,
            phase=SprintPhase.BLOCKED,
            error_message=error_message,
        )

    def _resume_candidate_commit(self, session: WorkflowSession) -> WorkflowResult:
        """Commit one exact approved candidate change set."""

        if self._candidate_commit_validator is None:
            return self._block_candidate_commit_session(
                session=session,
                error_message=CandidateCommitFailureCode.COMMIT_APPROVAL_EVIDENCE_MISMATCH.value,
            )
        approval_identifier = f"approval-commit-{session.identifier}"
        approval_result = self._approval_repository.get_request(approval_identifier)
        evaluated_approval = None
        if approval_result is not None:
            try:
                evaluated_approval = self._approval_engine.evaluate(
                    approval_result.decision
                )
            except Exception:
                logger.exception("Candidate commit approval validation failed")
                return self._block_candidate_commit_session(
                    session=session,
                    error_message=CandidateCommitFailureCode.COMMIT_APPROVAL_EVIDENCE_MISMATCH.value,
                )
        expected_approval = None
        if session.commit_request is not None and session.reviewed_content_fingerprint is not None:
            try:
                expected_approval = self._commit_approval_request(
                    session=session,
                    commit_request=session.commit_request,
                    fingerprint=session.reviewed_content_fingerprint,
                )
            except Exception:
                logger.exception("Candidate commit approval reconstruction failed")
                return self._block_candidate_commit_session(
                    session=session,
                    error_message=CandidateCommitFailureCode.COMMIT_APPROVAL_EVIDENCE_MISMATCH.value,
                )

        validation = self._candidate_commit_validator.validate(
            workflow=session,
            approval_result=evaluated_approval,
            expected_approval=expected_approval,
        )
        if not validation.approved:
            return self._candidate_commit_failure_result(session, validation)
        commit_request = validation.commit_request
        if commit_request is None:
            return self._block_candidate_commit_session(
                session=session,
                error_message=CandidateCommitFailureCode.COMMIT_APPROVAL_EVIDENCE_MISMATCH.value,
            )
        if not self._transition_session(
            session.identifier,
            WorkflowSessionState.AWAITING_COMMIT_APPROVAL,
            WorkflowSessionState.COMMITTING,
        ):
            return self._session_error_result(
                session=session,
                error_message="Workflow already resumed",
            )

        claimed_session = replace(session, state=WorkflowSessionState.COMMITTING)
        committing_status = self._status(claimed_session, SprintPhase.COMMITTING)
        self._publish_sprint(committing_status)
        try:
            commit_result = self._repository_committer_factory(
                commit_request.repository_root
            ).commit(commit_request)
        except Exception:
            logger.exception("Candidate commit failed")
            self._transition_session(
                session.identifier,
                WorkflowSessionState.COMMITTING,
                WorkflowSessionState.BLOCKED,
                blocked_reason=CandidateCommitFailureCode.COMMIT_FAILED.value,
            )
            return self._blocked_session_result(
                session=claimed_session,
                execution_result=session.execution_result,
                verification_report=session.verification_report,
                review_report=session.review_report,
                error_message=CandidateCommitFailureCode.COMMIT_FAILED.value,
            )

        result_validation = self._candidate_commit_validator.validate_commit_result(
            workflow=session,
            commit_result=commit_result,
        )
        if not result_validation.approved:
            code = (
                result_validation.failure_code
                or CandidateCommitFailureCode.COMMIT_RESULT_MISMATCH
            )
            self._transition_session(
                session.identifier,
                WorkflowSessionState.COMMITTING,
                WorkflowSessionState.BLOCKED,
                commit_result=commit_result,
                blocked_reason=code.value,
            )
            return self._blocked_session_result(
                session=claimed_session,
                execution_result=session.execution_result,
                verification_report=session.verification_report,
                review_report=session.review_report,
                commit_result=commit_result,
                error_message=code.value,
            )

        if not self._transition_session(
            session.identifier,
            WorkflowSessionState.COMMITTING,
            WorkflowSessionState.COMPLETED,
            commit_result=commit_result,
        ):
            return self._blocked_session_result(
                session=claimed_session,
                execution_result=session.execution_result,
                verification_report=session.verification_report,
                review_report=session.review_report,
                commit_result=commit_result,
                error_message=CandidateCommitFailureCode.PERSISTENCE_FAILED.value,
            )
        completed_status = self._status(claimed_session, SprintPhase.COMPLETED)
        self._publish_sprint(completed_status)
        return WorkflowResult(
            sprint=completed_status,
            plan=session.plan,
            context=session.context,
            planning_analysis=session.planning_analysis,
            review_analysis=session.review_analysis,
            approval_request=expected_approval,
            execution_result=session.execution_result,
            verification_report=session.verification_report,
            review_report=session.review_report,
            commit_result=commit_result,
        )

    def _verification_approval_request(
        self,
        session: WorkflowSession,
    ) -> ApprovalRequest:
        checks = tuple(
            VerificationApprovalCheck(
                identifier=check.identifier,
                command=check.argv,
                working_directory=(
                    check.working_directory.resolve(strict=False)
                    if check.working_directory.is_absolute()
                    else (
                        session.plan.repository_root
                        / check.working_directory
                    ).resolve(strict=False)
                ),
                timeout_seconds=check.timeout_seconds,
                environment=tuple(
                    VerificationApprovalEnvironment(
                        name=variable.name,
                        value_digest=sha256(
                            variable.value.encode("utf-8")
                        ).hexdigest()
                        if not variable.redacted
                        else variable.value_digest or "",
                    )
                    for variable in check.environment
                ),
            )
            for check in session.request.verification_checks
        )
        request = ApprovalRequest(
            identifier=f"approval-verification-{session.identifier}",
            workflow_id=session.identifier,
            checkpoint_id=session.plan.checkpoint_id,
            title=f"Approve verification of {session.plan.title}",
            requested_tool="verification",
            requested_command=(
                "verification-suite",
                *(check.identifier for check in checks),
            ),
            requested_working_directory=session.plan.repository_root,
            rationale="Approve the exact ordered verification checks.",
            purpose=ApprovalPurpose.VERIFICATION,
            verification_checks=checks,
        )
        return self._approval_engine.evaluate(
            ApprovalDecision(
                request=request,
                status=ApprovalStatus.PENDING,
            )
        ).decision.request

    def _publish_sprint(self, status: SprintStatus) -> None:
        if self._state_persistence is None:
            self._state_store.publish_sprint(status)
            return
        self._state_persistence.mutate_workflow(
            lambda workflow: workflow.publish_sprint(status)
        )

    def _publish_verification(self, report) -> None:
        if self._state_persistence is None:
            self._state_store.publish_verification(report)
            return
        self._state_persistence.mutate_workflow(
            lambda workflow: workflow.publish_verification(report)
        )

    def _publish_review(self, report) -> None:
        if self._state_persistence is None:
            self._state_store.publish_review(report)
            return
        self._state_persistence.mutate_workflow(
            lambda workflow: workflow.publish_review(report)
        )

    def _transition_session(
        self,
        identifier: str,
        expected_state: WorkflowSessionState,
        new_state: WorkflowSessionState,
        **artifacts: object,
    ) -> bool:
        if self._state_persistence is None:
            return self._state_store.transition_session(
                identifier,
                expected_state,
                new_state,
                **artifacts,
            )
        return self._state_persistence.mutate_workflow(
            lambda workflow: workflow.transition_session(
                identifier,
                expected_state,
                new_state,
                **artifacts,
            )
        )

    def _save_approval_request(self, request: ApprovalRequest) -> str:
        if self._state_persistence is None:
            return self._approval_repository.save_request(request)
        return self._state_persistence.mutate_approval(
            lambda approvals: approvals.save_request(request)
        )

    @staticmethod
    def _rehydrate_verification_checks(
        checks: tuple[VerificationCheck, ...],
    ) -> tuple[VerificationCheck, ...]:
        rehydrated: list[VerificationCheck] = []
        for check in checks:
            environment: list[EnvironmentVariable] = []
            for variable in check.environment:
                if not variable.redacted:
                    environment.append(variable)
                    continue
                raw_value = os.environ.get(variable.name)
                if raw_value is None:
                    raise ValueError(
                        "verification environment value is unavailable after restart"
                    )
                digest = sha256(raw_value.encode("utf-8")).hexdigest()
                if digest != variable.value_digest:
                    raise ValueError(
                        "verification environment value digest mismatch after restart"
                    )
                environment.append(
                    EnvironmentVariable(
                        name=variable.name,
                        value=raw_value,
                    )
                )
            rehydrated.append(
                replace(
                    check,
                    environment=tuple(environment),
                )
            )
        return tuple(rehydrated)

    def _commit_approval_request(
        self,
        *,
        session: WorkflowSession,
        commit_request: CommitRequest,
        fingerprint: str,
    ) -> ApprovalRequest:
        paths = tuple(sorted(commit_request.paths))
        request = ApprovalRequest(
            identifier=f"approval-commit-{session.identifier}",
            workflow_id=session.identifier,
            checkpoint_id=session.plan.checkpoint_id,
            title=f"Approve commit of {session.plan.title}",
            requested_tool="git",
            requested_command=("git-commit", *tuple(str(path) for path in paths)),
            requested_working_directory=commit_request.repository_root,
            rationale="Approve the exact reviewed Git commit.",
            purpose=ApprovalPurpose.COMMIT,
            commit_metadata=CommitApprovalMetadata(
                expected_branch=commit_request.expected_branch,
                expected_head=commit_request.expected_head,
                reviewed_files=paths,
                reviewed_content_fingerprint=fingerprint,
                commit_message=commit_request.message,
            ),
        )
        return self._approval_engine.evaluate(
            ApprovalDecision(
                request=request,
                status=ApprovalStatus.PENDING,
            )
        ).decision.request

    @staticmethod
    def _candidate_workflow_request(
        *,
        execution_request: ExecutionRequest,
        plan: ImplementationPlan,
    ) -> WorkflowRequest:
        checkpoint = RoadmapCheckpoint(
            identifier=plan.checkpoint_id,
            title=plan.title,
            goal=plan.goal,
            scope_items=plan.scope_items,
            affected_files=plan.affected_files,
            required_tests=plan.required_tests,
            risks=tuple(risk.description for risk in plan.risks),
        )
        return WorkflowRequest(
            checkpoint=checkpoint,
            repository_root=plan.repository_root,
            execution_identifier=execution_request.identifier,
            execution_argv=execution_request.argv,
            execution_workdir=execution_request.working_directory,
            verification_checks=(),
            review_identifier=f"candidate-review-{execution_request.identifier}",
        )

    @staticmethod
    def _candidate_verification_approval_request(
        session: WorkflowSession,
    ) -> ApprovalRequest:
        assert session.plan is not None
        return ApprovalRequest(
            identifier=f"approval-verification-{session.identifier}",
            workflow_id=session.identifier,
            checkpoint_id=session.plan.checkpoint_id,
            title=f"Approve verification of {session.plan.title}",
            requested_tool="verification",
            requested_command=("verification-suite",),
            requested_working_directory=session.plan.repository_root,
            rationale="Approve the future candidate verification phase.",
            purpose=ApprovalPurpose.VERIFICATION,
        )

    def _candidate_validation_failure_result(
        self,
        session: WorkflowSession,
        validation: CandidateExecutionValidationResult,
    ) -> WorkflowResult:
        code = validation.failure_code or CandidateExecutionFailureCode.APPROVAL_EVIDENCE_MISMATCH
        reason = (
            code.value
            if validation.message is None
            else f"{code.value}: {validation.message}"
        )
        if validation.should_block:
            return self._block_candidate_session(
                session=session,
                error_message=code.value,
                blocked_reason=reason,
            )
        return self._candidate_session_result(
            session=session,
            phase=SprintPhase.AWAITING_APPROVAL,
            error_message=code.value,
        )

    def _block_candidate_session(
        self,
        *,
        session: WorkflowSession,
        error_message: str,
        blocked_reason: str | None = None,
    ) -> WorkflowResult:
        self._transition_session(
            session.identifier,
            session.state,
            WorkflowSessionState.BLOCKED,
            blocked_reason=blocked_reason or error_message,
        )
        return self._candidate_session_result(
            session=session,
            phase=SprintPhase.BLOCKED,
            error_message=error_message,
        )

    def _candidate_session_result(
        self,
        *,
        session: WorkflowSession,
        phase: SprintPhase,
        error_message: str | None = None,
    ) -> WorkflowResult:
        if session.request is not None:
            sprint = self._status(session, phase)
        else:
            metadata = session.candidate_metadata
            sprint = SprintStatus(
                checkpoint_id=session.identifier,
                title="Candidate Implementation",
                goal=(
                    f"Execute candidate {metadata.candidate_id}"
                    if metadata is not None
                    else "Execute candidate implementation"
                ),
                phase=phase,
            )
        self._publish_sprint(sprint)
        return WorkflowResult(
            sprint=sprint,
            plan=session.plan,
            context=session.context,
            planning_analysis=session.planning_analysis,
            review_analysis=session.review_analysis,
            execution_result=session.execution_result,
            verification_report=session.verification_report,
            review_report=session.review_report,
            error_message=error_message,
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
            and approval_request.purpose is ApprovalPurpose.IMPLEMENTATION
            and approval_request.workflow_id == session.identifier
            and approval_request.checkpoint_id == session.plan.checkpoint_id
            and approval_request.requested_tool == request.execution_argv[0]
            and approval_request.requested_command == request.execution_argv
            and approval_request.requested_working_directory
            == request.execution_workdir
        )

    def _block_claimed_session(
        self,
        workflow_id: str,
        expected_state: WorkflowSessionState,
    ) -> None:
        self._transition_session(
            workflow_id,
            expected_state,
            WorkflowSessionState.BLOCKED,
        )

    def _waiting_verification_result(
        self,
        session: WorkflowSession,
        *,
        approval_request: ApprovalRequest | None = None,
    ) -> WorkflowResult:
        awaiting_status = self._status(
            session,
            SprintPhase.AWAITING_VERIFICATION_APPROVAL,
        )
        self._publish_sprint(awaiting_status)
        return WorkflowResult(
            sprint=awaiting_status,
            plan=session.plan,
            context=session.context,
            planning_analysis=session.planning_analysis,
            review_analysis=session.review_analysis,
            approval_request=approval_request,
            execution_result=session.execution_result,
        )

    def _pending_implementation_result(
        self,
        session: WorkflowSession,
        *,
        approval_request: ApprovalRequest,
    ) -> WorkflowResult:
        awaiting_status = self._status(session, SprintPhase.AWAITING_APPROVAL)
        self._publish_sprint(awaiting_status)
        return WorkflowResult(
            sprint=awaiting_status,
            plan=session.plan,
            context=session.context,
            planning_analysis=session.planning_analysis,
            approval_request=approval_request,
            error_message="Approval pending",
        )

    def _waiting_commit_result(
        self,
        session: WorkflowSession,
        *,
        approval_request: ApprovalRequest | None = None,
    ) -> WorkflowResult:
        awaiting_status = self._status(
            session,
            SprintPhase.AWAITING_COMMIT_APPROVAL,
        )
        self._publish_sprint(awaiting_status)
        return WorkflowResult(
            sprint=awaiting_status,
            plan=session.plan,
            context=session.context,
            planning_analysis=session.planning_analysis,
            review_analysis=session.review_analysis,
            approval_request=approval_request,
            execution_result=session.execution_result,
            verification_report=session.verification_report,
            review_report=session.review_report,
        )

    def _block_verification_session(
        self,
        *,
        session: WorkflowSession,
        error_message: str,
    ) -> WorkflowResult:
        if not self._transition_session(
            session.identifier,
            WorkflowSessionState.AWAITING_VERIFICATION_APPROVAL,
            WorkflowSessionState.BLOCKED,
        ):
            return self._session_error_result(
                session=session,
                error_message="Workflow already resumed",
            )
        return self._blocked_session_result(
            session=session,
            error_message=error_message,
        )

    def _block_commit_session(
        self,
        *,
        session: WorkflowSession,
        error_message: str,
    ) -> WorkflowResult:
        if not self._transition_session(
            session.identifier,
            WorkflowSessionState.AWAITING_COMMIT_APPROVAL,
            WorkflowSessionState.BLOCKED,
        ):
            return self._session_error_result(
                session=session,
                error_message="Workflow already resumed",
            )
        return self._blocked_session_result(
            session=session,
            verification_report=session.verification_report,
            review_report=session.review_report,
            error_message=error_message,
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
        self._publish_sprint(blocked_status)

        return WorkflowResult(
            sprint=blocked_status,
            plan=session.plan,
            context=session.context,
            planning_analysis=session.planning_analysis,
            review_analysis=session.review_analysis,
            execution_result=execution_result or session.execution_result,
            verification_report=verification_report,
            review_report=review_report,
            error_message=error_message,
        )

    def _session_error_result(
        self,
        *,
        session: WorkflowSession,
        error_message: str,
    ) -> WorkflowResult:
        phase = {
            WorkflowSessionState.EXECUTING: SprintPhase.IN_PROGRESS,
            WorkflowSessionState.VERIFYING: SprintPhase.VERIFYING,
            WorkflowSessionState.COMMITTING: SprintPhase.COMMITTING,
            WorkflowSessionState.COMPLETED: SprintPhase.COMPLETED,
        }.get(session.state, SprintPhase.BLOCKED)
        return WorkflowResult(
            sprint=self._status(session, phase),
            plan=session.plan,
            context=session.context,
            planning_analysis=session.planning_analysis,
            review_analysis=session.review_analysis,
            execution_result=session.execution_result,
            verification_report=session.verification_report,
            review_report=session.review_report,
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
        self._publish_sprint(blocked_status)
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
