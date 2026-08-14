"""Focused tests for dormant Agent operational orchestration."""

import asyncio
from dataclasses import replace
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.approval.models import (
    ApprovalDecision,
    ApprovalPurpose,
    ApprovalRequest,
    ApprovalResult,
    ApprovalStatus,
    OperationalApprovalMetadata,
)
from app.approval.repository import ApprovalRepository
from app.candidate_planning.models import (
    OPERATIONAL_EXECUTION_INTENTS,
    operational_verification_digest,
)
from app.core_client.exceptions import AtlasCoreTimeoutError
from app.core_client.models import (
    CoreOperationalDispatchResult,
    CoreOperationalLifecycleStatus,
    CoreOperationalVerificationResult,
)
from app.routes.workflow import resume_workflow
from app.workflow.models import (
    CandidateWorkflowMetadata,
    OperationalExecutionStage,
    WorkflowEffectKind,
    WorkflowSession,
    WorkflowSessionState,
    WorkflowSource,
)
from app.workflow.operational_execution import OperationalExecutionOrchestrator
from app.workflow.state import WorkflowStateStore
from tests.candidate_planning.test_operational_models import NOW, operational_request


def _session() -> WorkflowSession:
    action = operational_request()
    metadata = CandidateWorkflowMetadata(
        candidate_planning_session_id=action.candidate_planning_session_id,
        candidate_id=action.candidate_id,
        candidate_fingerprint=action.candidate_fingerprint,
        candidate_plan_id=action.candidate_plan_id,
        candidate_plan_fingerprint=action.candidate_plan_fingerprint,
        source_recommendation_id="recommendation-1",
        source_subsystem="orion",
        catalog_item_id=None,
        target_id=action.resource_id,
        target_type=action.resource_type,
        execution_category="restart",
        execution_intent=action.execution_intent,
        evidence_ids=action.evidence_ids,
        compatibility_assessment_id=None,
        compatibility_status=None,
        relationship_ids=(),
        conversion_timestamp=action.generated_at,
        core_revalidation_status="accepted_for_planning",
        core_revalidation_fingerprint=action.candidate_fingerprint,
        effect_kind=WorkflowEffectKind.OPERATIONAL_ACTION,
    )
    return WorkflowSession(
        identifier=action.workflow_session_id,
        request=None,
        plan=None,
        state=WorkflowSessionState.AWAITING_IMPLEMENTATION_APPROVAL,
        effect_kind=WorkflowEffectKind.OPERATIONAL_ACTION,
        source=WorkflowSource.CANDIDATE,
        candidate_metadata=metadata,
        operational_action_request=action,
        operational_action_approval_id="approval-operational-workflow-1",
    )


def _approval(session: WorkflowSession, status=ApprovalStatus.APPROVED) -> ApprovalResult:
    action = session.operational_action_request
    assert action is not None
    metadata = OperationalApprovalMetadata(
        action_request_id=action.request_id,
        action_request_digest=action.request_digest,
        candidate_id=action.candidate_id,
        candidate_fingerprint=action.candidate_fingerprint,
        operational_plan_fingerprint=action.candidate_plan_fingerprint,
        provider_id=action.provider_id,
        resource_id=action.resource_id,
        resource_type=action.resource_type,
        target_fingerprint=action.target_fingerprint,
        target_version=action.target_version,
        operation_intent=action.execution_intent,
        disruption_scope=action.disruption_scope,
        verification_digest=operational_verification_digest(action.verification),
        generated_at=action.generated_at,
        expires_at=action.expires_at,
    )
    return ApprovalResult(
        decision=ApprovalDecision(
            request=ApprovalRequest(
                identifier="approval-operational-workflow-1",
                workflow_id=session.identifier,
                checkpoint_id=action.request_id,
                title="Approve exact operational action",
                requested_tool="atlas-agent-operational-contract",
                requested_command=(),
                rationale="Exact semantic approval",
                purpose=ApprovalPurpose.OPERATIONAL_ACTION,
                operational_metadata=metadata,
            ),
            status=status,
        )
    )


def _orchestrator(*, enabled=False, approval=None):
    session = _session()
    state = WorkflowStateStore()
    state.create_session(session)
    approvals = ApprovalRepository()
    if approval is not None:
        approvals.replace_snapshot({"approval-operational-workflow-1": approval})
    core = AsyncMock()
    service = OperationalExecutionOrchestrator(
        core_client=core,
        approval_repository=approvals,
        workflow_state=state,
        execution_policy=lambda intent: enabled and intent == "restart-service",
        now=lambda: NOW + timedelta(minutes=1),
    )
    return service, core, state, session


def test_production_gate_remains_empty_and_makes_no_core_call() -> None:
    session = _session()
    service, core, state, _ = _orchestrator(approval=_approval(session))

    result = asyncio.run(service.resume(session.identifier))

    assert OPERATIONAL_EXECUTION_INTENTS == frozenset()
    assert result.error_message == "operational_execution_not_enabled"
    core.dispatch_operational_action.assert_not_awaited()
    reference = state.get_session(session.identifier).operational_execution_reference
    assert reference.stage is OperationalExecutionStage.EXECUTION_BLOCKED


@pytest.mark.parametrize(
    ("approval", "reason"),
    [(None, "operational_approval_missing"), (ApprovalStatus.REJECTED, "operational_approval_required")],
)
def test_missing_and_denied_approval_fail_before_dispatch(approval, reason) -> None:
    session = _session()
    stored = _approval(session, approval) if approval is not None else None
    service, core, _, _ = _orchestrator(enabled=True, approval=stored)
    assert asyncio.run(service.resume(session.identifier)).error_message == reason
    core.dispatch_operational_action.assert_not_awaited()


@pytest.mark.parametrize(
    "field",
    [
        "action_request_id",
        "action_request_digest",
        "candidate_id",
        "candidate_fingerprint",
        "operational_plan_fingerprint",
        "provider_id",
        "resource_id",
        "resource_type",
        "target_fingerprint",
        "target_version",
        "operation_intent",
        "disruption_scope",
        "verification_digest",
    ],
)
def test_mismatched_exact_approval_binding_fails_before_dispatch(field) -> None:
    session = _session()
    approval = _approval(session)
    request = approval.decision.request
    metadata = request.operational_metadata
    mismatched = replace(
        approval,
        decision=replace(
            approval.decision,
            request=replace(request, operational_metadata=replace(metadata, **{field: "mismatch"})),
        ),
    )
    service, core, _, _ = _orchestrator(enabled=True, approval=mismatched)
    assert asyncio.run(service.resume(session.identifier)).error_message == "operational_approval_mismatch"
    core.dispatch_operational_action.assert_not_awaited()


def test_expired_approval_fails_before_dispatch() -> None:
    session = _session()
    approval = _approval(session)
    service, core, _, _ = _orchestrator(enabled=True, approval=approval)
    service._now = lambda: NOW + timedelta(minutes=6)
    assert asyncio.run(service.resume(session.identifier)).error_message == "operational_approval_expired"
    core.dispatch_operational_action.assert_not_awaited()


def test_synthetic_policy_dispatches_exact_persisted_artifacts() -> None:
    session = _session()
    approval = _approval(session)
    service, core, state, _ = _orchestrator(enabled=True, approval=approval)
    action = session.operational_action_request
    core.dispatch_operational_action.return_value = CoreOperationalDispatchResult(
        status="succeeded",
        request_id=action.request_id,
        request_digest=action.request_digest,
        target_fingerprint=action.target_fingerprint,
        provider_operation_id="UPID:sanitized",
        started_at=NOW,
        completed_at=NOW + timedelta(seconds=1),
        sanitized_message="Accepted for verification.",
    )

    asyncio.run(service.resume(session.identifier))

    core.dispatch_operational_action.assert_awaited_once_with(action, approval)
    stored = state.get_session(session.identifier)
    assert stored.state is WorkflowSessionState.VERIFYING
    assert stored.operational_execution_reference.stage is OperationalExecutionStage.VERIFICATION_PENDING


def test_lost_response_retry_preserves_exact_request_identity() -> None:
    session = _session()
    approval = _approval(session)
    service, core, state, _ = _orchestrator(enabled=True, approval=approval)
    action = session.operational_action_request
    accepted = CoreOperationalDispatchResult(
        status="succeeded",
        request_id=action.request_id,
        request_digest=action.request_digest,
        target_fingerprint=action.target_fingerprint,
        provider_operation_id="UPID:sanitized",
        started_at=NOW,
        completed_at=NOW + timedelta(seconds=1),
    )
    core.dispatch_operational_action.side_effect = [AtlasCoreTimeoutError("lost"), accepted]

    asyncio.run(service.resume(session.identifier))
    assert state.get_session(session.identifier).operational_execution_reference.stage is OperationalExecutionStage.SUBMISSION_OUTCOME_UNKNOWN
    asyncio.run(service.resume(session.identifier))

    assert core.dispatch_operational_action.await_count == 2
    assert all(call.args == (action, approval) for call in core.dispatch_operational_action.await_args_list)


def test_resume_route_awaits_operational_orchestrator_without_repository_engine() -> None:
    session = _session()
    operational = AsyncMock()
    operational.resume.return_value = OperationalExecutionOrchestrator._result(
        session, session.identifier
    )
    workflow_engine = SimpleNamespace(resume=lambda _workflow_id: pytest.fail("repository engine called"))
    request = SimpleNamespace(
        app=SimpleNamespace(
            state=SimpleNamespace(
                container=SimpleNamespace(
                    workflow_state=SimpleNamespace(get_session=lambda _workflow_id: session),
                    operational_execution_orchestrator=operational,
                    workflow_engine=workflow_engine,
                )
            )
        )
    )

    asyncio.run(resume_workflow(request, session.identifier))

    operational.resume.assert_awaited_once_with(session.identifier)


@pytest.mark.parametrize(
    ("ledger_state", "stage", "workflow_state"),
    [
        ("claimed", OperationalExecutionStage.DISPATCH_PENDING, WorkflowSessionState.EXECUTING),
        ("revalidated", OperationalExecutionStage.DISPATCH_PENDING, WorkflowSessionState.EXECUTING),
        ("dispatching", OperationalExecutionStage.DISPATCH_PENDING, WorkflowSessionState.EXECUTING),
        ("succeeded", OperationalExecutionStage.VERIFICATION_PENDING, WorkflowSessionState.VERIFYING),
        ("verifying", OperationalExecutionStage.VERIFICATION_PENDING, WorkflowSessionState.VERIFYING),
        ("verified", OperationalExecutionStage.VERIFIED, WorkflowSessionState.COMPLETED),
        ("failed", OperationalExecutionStage.FAILED, WorkflowSessionState.BLOCKED),
        ("verification_failed", OperationalExecutionStage.VERIFICATION_FAILED, WorkflowSessionState.BLOCKED),
        ("target_replaced", OperationalExecutionStage.TARGET_REPLACED, WorkflowSessionState.BLOCKED),
        ("outcome_unknown", OperationalExecutionStage.OUTCOME_UNKNOWN, WorkflowSessionState.BLOCKED),
    ],
)
def test_repeated_resume_reconciles_status_without_redispatch(
    ledger_state, stage, workflow_state
) -> None:
    session = _session()
    approval = _approval(session)
    service, core, state, _ = _orchestrator(enabled=True, approval=approval)
    action = session.operational_action_request
    core.dispatch_operational_action.return_value = CoreOperationalDispatchResult(
        status="succeeded",
        request_id=action.request_id,
        request_digest=action.request_digest,
        target_fingerprint=action.target_fingerprint,
        provider_operation_id="UPID:sanitized",
        started_at=NOW,
        completed_at=NOW + timedelta(seconds=1),
    )
    asyncio.run(service.resume(session.identifier))
    verification = None
    if ledger_state in {"verified", "verification_failed", "target_replaced"}:
        verification = CoreOperationalVerificationResult(
            status={"verified": "succeeded", "verification_failed": "verification_failed", "target_replaced": "target_replaced"}[ledger_state],
            request_id=action.request_id,
            started_at=NOW,
            completed_at=NOW + timedelta(seconds=2),
            deadline=action.expires_at,
        )
    core.get_operational_action_status.return_value = CoreOperationalLifecycleStatus(
        request_id=action.request_id,
        request_digest=action.request_digest,
        ledger_state=ledger_state,
        dispatch_result=core.dispatch_operational_action.return_value,
        verification_result=verification,
        verification_resumable=not ledger_state.startswith("verif"),
    )

    asyncio.run(service.resume(session.identifier))

    core.dispatch_operational_action.assert_awaited_once()
    assert state.get_session(session.identifier).state is workflow_state
    assert state.get_session(session.identifier).operational_execution_reference.stage is stage
