"""Dormant, approval-bound Agent orchestration for Core operational actions."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from datetime import UTC, datetime

from app.approval.models import ApprovalPurpose, ApprovalResult, ApprovalStatus
from app.approval.repository import ApprovalRepository
from app.candidate_planning.models import (
    OperationalActionRequest,
    is_operational_execution_enabled,
    operational_verification_digest,
)
from app.core_client.client import AtlasCoreClient
from app.core_client.exceptions import AtlasCoreClientError
from app.core_client.models import (
    CoreOperationalDispatchResult,
    CoreOperationalLifecycleStatus,
)
from app.persistence.snapshot import AgentStatePersistenceCoordinator
from app.workflow.models import (
    OperationalExecutionReference,
    OperationalExecutionStage,
    SprintPhase,
    SprintStatus,
    WorkflowEffectKind,
    WorkflowResult,
    WorkflowSession,
    WorkflowSessionState,
)
from app.workflow.state import WorkflowStateStore

ExecutionPolicy = Callable[[str], bool]
Now = Callable[[], datetime]


class OperationalExecutionOrchestrator:
    """Submit or reconcile one persisted operational request without provider access."""

    def __init__(
        self,
        *,
        core_client: AtlasCoreClient,
        approval_repository: ApprovalRepository,
        workflow_state: WorkflowStateStore,
        state_persistence: AgentStatePersistenceCoordinator | None = None,
        execution_policy: ExecutionPolicy = is_operational_execution_enabled,
        now: Now = lambda: datetime.now(UTC),
    ) -> None:
        self._core_client = core_client
        self._approvals = approval_repository
        self._workflow_state = workflow_state
        self._persistence = state_persistence
        self._execution_policy = execution_policy
        self._now = now

    async def resume(self, workflow_id: str) -> WorkflowResult:
        session = self._workflow_state.get_session(workflow_id)
        if session is None:
            return self._result(None, workflow_id, "Workflow not found")
        if session.effect_kind is not WorkflowEffectKind.OPERATIONAL_ACTION:
            return self._result(session, workflow_id, "Workflow is not operational")
        request = session.operational_action_request
        approval = self._validated_approval(session, request)
        if isinstance(approval, str):
            return self._result(session, workflow_id, approval)
        assert request is not None

        reference = session.operational_execution_reference
        if reference is not None and reference.request_id != request.request_id:
            return self._result(session, workflow_id, "operational_execution_reference_mismatch")
        if reference is not None and reference.stage not in {
            OperationalExecutionStage.EXECUTION_BLOCKED,
            OperationalExecutionStage.SUBMISSION_OUTCOME_UNKNOWN,
        }:
            return await self._reconcile(session, request, reference)

        if not self._execution_policy(request.execution_intent):
            blocked = OperationalExecutionReference(
                request_id=request.request_id,
                request_digest=request.request_digest,
                stage=OperationalExecutionStage.EXECUTION_BLOCKED,
                dispatch_status=None,
                ledger_state=None,
                provider_operation_id=None,
                verification_status=None,
                submitted_at=None,
                last_observed_at=self._now(),
                terminal=False,
                controlled_reason="operational_execution_not_enabled",
                audit_events=("execution_blocked_by_agent_gate",),
            )
            self._store(session, reference=blocked, state=session.state)
            return self._result(session, workflow_id, "operational_execution_not_enabled")

        try:
            dispatch = await self._core_client.dispatch_operational_action(request, approval)
        except AtlasCoreClientError:
            unknown = OperationalExecutionReference(
                request_id=request.request_id,
                request_digest=request.request_digest,
                stage=OperationalExecutionStage.SUBMISSION_OUTCOME_UNKNOWN,
                dispatch_status=None,
                ledger_state=None,
                provider_operation_id=None,
                verification_status=None,
                submitted_at=self._now(),
                last_observed_at=self._now(),
                terminal=False,
                controlled_reason="operational_submission_outcome_unknown",
                audit_events=("authenticated_dispatch_submitted", "submission_outcome_unknown"),
            )
            updated = self._store(session, reference=unknown, state=WorkflowSessionState.EXECUTING)
            return self._result(updated, workflow_id, "operational_submission_outcome_unknown")

        reference, state = self._from_dispatch(request, dispatch)
        updated = self._store(session, reference=reference, state=state)
        return self._result(updated, workflow_id)

    def _validated_approval(
        self,
        session: WorkflowSession,
        request: OperationalActionRequest | None,
    ) -> ApprovalResult | str:
        if request is None or session.operational_action_approval_id is None:
            return "operational_approval_missing"
        approval = self._approvals.get_request(session.operational_action_approval_id)
        if approval is None:
            return "operational_approval_missing"
        decision = approval.decision
        stored = decision.request
        metadata = stored.operational_metadata
        if stored.purpose is not ApprovalPurpose.OPERATIONAL_ACTION or metadata is None:
            return "operational_approval_invalid"
        if (
            stored.identifier != session.operational_action_approval_id
            or stored.workflow_id != session.identifier
        ):
            return "operational_approval_mismatch"
        if decision.status is not ApprovalStatus.APPROVED:
            return "operational_approval_required"
        now = self._now()
        if request.expires_at <= now or metadata.expires_at <= now:
            return "operational_approval_expired"
        expected = (
            (metadata.action_request_id, request.request_id),
            (metadata.action_request_digest, request.request_digest),
            (metadata.candidate_id, request.candidate_id),
            (metadata.candidate_fingerprint, request.candidate_fingerprint),
            (metadata.operational_plan_fingerprint, request.candidate_plan_fingerprint),
            (metadata.provider_id, request.provider_id),
            (metadata.resource_id, request.resource_id),
            (metadata.resource_type, request.resource_type),
            (metadata.target_fingerprint, request.target_fingerprint),
            (metadata.target_version, request.target_version),
            (metadata.operation_intent, request.execution_intent),
            (metadata.disruption_scope, request.disruption_scope),
            (metadata.verification_digest, operational_verification_digest(request.verification)),
            (metadata.generated_at, request.generated_at),
            (metadata.expires_at, request.expires_at),
        )
        if any(actual != wanted for actual, wanted in expected):
            return "operational_approval_mismatch"
        return approval

    async def _reconcile(
        self,
        session: WorkflowSession,
        request: OperationalActionRequest,
        reference: OperationalExecutionReference,
    ) -> WorkflowResult:
        try:
            status = await self._core_client.get_operational_action_status(request.request_id)
        except AtlasCoreClientError:
            return self._result(session, session.identifier, "operational_status_unavailable")
        if status.request_digest != request.request_digest:
            return self._result(session, session.identifier, "operational_core_identity_mismatch")
        updated_reference, workflow_state = self._from_status(reference, status)
        updated = self._store(session, reference=updated_reference, state=workflow_state)
        return self._result(updated, session.identifier)

    def _from_dispatch(
        self, request: OperationalActionRequest, result: CoreOperationalDispatchResult
    ) -> tuple[OperationalExecutionReference, WorkflowSessionState]:
        if result.request_id != request.request_id or result.request_digest != request.request_digest:
            raise ValueError("Core operational dispatch identity mismatch")
        now = self._now()
        succeeded = result.status == "succeeded"
        stage = (
            OperationalExecutionStage.VERIFICATION_PENDING
            if succeeded
            else OperationalExecutionStage.OUTCOME_UNKNOWN
            if result.status == "outcome_unknown"
            else OperationalExecutionStage.FAILED
        )
        return (
            OperationalExecutionReference(
                request_id=request.request_id,
                request_digest=request.request_digest,
                stage=stage,
                dispatch_status=result.status,
                ledger_state="succeeded" if succeeded else result.status,
                provider_operation_id=result.provider_operation_id,
                verification_status=None,
                submitted_at=now,
                last_observed_at=now,
                terminal=not succeeded,
                controlled_reason=result.sanitized_message,
                audit_events=("authenticated_dispatch_submitted", "verification_pending")
                if succeeded
                else ("authenticated_dispatch_submitted", stage.value),
            ),
            WorkflowSessionState.VERIFYING if succeeded else WorkflowSessionState.BLOCKED,
        )

    def _from_status(
        self,
        previous: OperationalExecutionReference,
        status: CoreOperationalLifecycleStatus,
    ) -> tuple[OperationalExecutionReference, WorkflowSessionState]:
        mapping = {
            "claimed": (OperationalExecutionStage.DISPATCH_PENDING, WorkflowSessionState.EXECUTING, False),
            "revalidated": (OperationalExecutionStage.DISPATCH_PENDING, WorkflowSessionState.EXECUTING, False),
            "dispatching": (OperationalExecutionStage.DISPATCH_PENDING, WorkflowSessionState.EXECUTING, False),
            "succeeded": (OperationalExecutionStage.VERIFICATION_PENDING, WorkflowSessionState.VERIFYING, False),
            "verifying": (OperationalExecutionStage.VERIFICATION_PENDING, WorkflowSessionState.VERIFYING, False),
            "verified": (OperationalExecutionStage.VERIFIED, WorkflowSessionState.COMPLETED, True),
            "failed": (OperationalExecutionStage.FAILED, WorkflowSessionState.BLOCKED, True),
            "verification_failed": (OperationalExecutionStage.VERIFICATION_FAILED, WorkflowSessionState.BLOCKED, True),
            "target_replaced": (OperationalExecutionStage.TARGET_REPLACED, WorkflowSessionState.BLOCKED, True),
            "outcome_unknown": (OperationalExecutionStage.OUTCOME_UNKNOWN, WorkflowSessionState.BLOCKED, True),
        }
        stage, workflow_state, terminal = mapping[status.ledger_state]
        dispatch = status.dispatch_result
        verification = status.verification_result
        event = "core_lifecycle_observed"
        if stage is OperationalExecutionStage.VERIFICATION_PENDING:
            event = "verification_pending"
        elif stage is OperationalExecutionStage.VERIFIED:
            event = "verification_succeeded"
        elif stage is OperationalExecutionStage.VERIFICATION_FAILED:
            event = "verification_failed"
        elif stage is OperationalExecutionStage.TARGET_REPLACED:
            event = "target_replaced"
        elif stage is OperationalExecutionStage.OUTCOME_UNKNOWN:
            event = "outcome_unknown"
        return (
            replace(
                previous,
                stage=stage,
                dispatch_status=dispatch.status if dispatch else previous.dispatch_status,
                ledger_state=status.ledger_state,
                provider_operation_id=(dispatch.provider_operation_id if dispatch else previous.provider_operation_id),
                verification_status=verification.status if verification else None,
                last_observed_at=self._now(),
                terminal=terminal,
                controlled_reason=(dispatch.sanitized_message if dispatch else previous.controlled_reason),
                audit_events=(
                    *previous.audit_events,
                    "core_lifecycle_observed",
                    *(() if event == "core_lifecycle_observed" else (event,)),
                ),
            ),
            workflow_state,
        )

    def _store(
        self,
        session: WorkflowSession,
        *,
        reference: OperationalExecutionReference,
        state: WorkflowSessionState,
    ) -> WorkflowSession:
        updated = replace(session, state=state, operational_execution_reference=reference)
        if self._persistence is not None:
            self._persistence.mutate_workflow(
                lambda workflows: workflows.sessions.__setitem__(session.identifier, updated)
            )
        else:
            snapshot = self._workflow_state.export_snapshot()
            sessions = dict(snapshot[3])
            sessions[session.identifier] = updated
            self._workflow_state.replace_snapshot((*snapshot[:3], sessions))
        return updated

    @staticmethod
    def _result(
        session: WorkflowSession | None,
        workflow_id: str,
        error: str | None = None,
    ) -> WorkflowResult:
        state = session.state if session is not None else WorkflowSessionState.BLOCKED
        phase = (
            SprintPhase.COMPLETED
            if state is WorkflowSessionState.COMPLETED
            else SprintPhase.VERIFYING
            if state is WorkflowSessionState.VERIFYING
            else SprintPhase.IN_PROGRESS
            if state is WorkflowSessionState.EXECUTING
            else SprintPhase.BLOCKED
        )
        return WorkflowResult(
            sprint=SprintStatus(
                checkpoint_id=workflow_id,
                title="Operational action",
                goal="Reconcile one exact approved operational action",
                phase=phase,
            ),
            error_message=error,
        )
