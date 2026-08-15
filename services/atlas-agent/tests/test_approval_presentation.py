"""Effect-aware approval presentation regression tests."""

from datetime import UTC, datetime, timedelta

from app.approval.models import (
    ApprovalDecision,
    ApprovalPurpose,
    ApprovalRequest,
    ApprovalResult,
    ApprovalStatus,
    OperationalApprovalMetadata,
)
from app.approval.presentation import (
    ApprovalPresentationState,
    classify_approval,
)
from app.candidate_planning.models import (
    OperationalActionRequest,
    operational_verification_digest,
)
from app.workflow.models import (
    CandidateWorkflowMetadata,
    WorkflowEffectKind,
    WorkflowSession,
    WorkflowSessionState,
)
from tests.candidate_planning.test_operational_models import operational_request


def workflow(
    *,
    effect: WorkflowEffectKind = WorkflowEffectKind.REPOSITORY_CHANGE,
    state: WorkflowSessionState = WorkflowSessionState.AWAITING_IMPLEMENTATION_APPROVAL,
    action: OperationalActionRequest | None = None,
) -> WorkflowSession:
    metadata = (
        CandidateWorkflowMetadata(
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
        if action is not None
        else None
    )
    return WorkflowSession(
        identifier=action.workflow_session_id if action is not None else "workflow-1",
        request=None,
        plan=None,
        state=state,
        effect_kind=effect,
        candidate_metadata=metadata,
        candidate_implementation_approval_id=(
            "approval-implementation"
            if effect is WorkflowEffectKind.REPOSITORY_CHANGE
            else None
        ),
        operational_action_approval_id=(
            "approval-operational"
            if effect is WorkflowEffectKind.OPERATIONAL_ACTION
            else None
        ),
        operational_action_request=action,
    )


def result(
    *,
    purpose: ApprovalPurpose = ApprovalPurpose.IMPLEMENTATION,
    identifier: str = "approval-implementation",
    workflow_id: str = "workflow-1",
    status: ApprovalStatus = ApprovalStatus.PENDING,
    operational_metadata: OperationalApprovalMetadata | None = None,
) -> ApprovalResult:
    request = ApprovalRequest(
        identifier=identifier,
        checkpoint_id="plan-1",
        title="Approval",
        requested_tool="semantic-action",
        requested_command=(),
        rationale="Review the exact immutable request.",
        workflow_id=workflow_id,
        purpose=purpose,
        operational_metadata=operational_metadata,
    )
    return ApprovalResult(
        ApprovalDecision(request=request, status=status, reviewer="reviewer")
    )


def test_valid_repository_approval_is_actionable() -> None:
    presentation = classify_approval(result(), workflow())

    assert presentation.state is ApprovalPresentationState.ACTIONABLE
    assert presentation.actionable is True


def test_valid_operational_approval_is_actionable() -> None:
    action = operational_request()
    session = workflow(effect=WorkflowEffectKind.OPERATIONAL_ACTION, action=action)
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

    presentation = classify_approval(
        result(
            purpose=ApprovalPurpose.OPERATIONAL_ACTION,
            identifier="approval-operational",
            workflow_id=action.workflow_session_id,
            operational_metadata=metadata,
        ),
        session,
        now=action.generated_at,
    )

    assert presentation.state is ApprovalPresentationState.ACTIONABLE
    assert presentation.actionable is True


def test_operational_workflow_never_presents_commit_approval() -> None:
    presentation = classify_approval(
        result(purpose=ApprovalPurpose.COMMIT, identifier="approval-commit-workflow-1"),
        workflow(effect=WorkflowEffectKind.OPERATIONAL_ACTION),
    )

    assert presentation.state is ApprovalPresentationState.HISTORICAL
    assert presentation.actionable is False


def test_repository_workflow_never_presents_operational_action_approval() -> None:
    presentation = classify_approval(
        result(
            purpose=ApprovalPurpose.OPERATIONAL_ACTION,
            identifier="approval-operational",
        ),
        workflow(),
    )

    assert presentation.state is ApprovalPresentationState.HISTORICAL
    assert presentation.actionable is False


def test_resolved_and_superseded_approvals_are_non_actionable() -> None:
    resolved = classify_approval(
        result(status=ApprovalStatus.APPROVED),
        workflow(),
    )
    superseded = classify_approval(result(), workflow(), successor_exists=True)

    assert resolved.state is ApprovalPresentationState.RESOLVED
    assert resolved.actionable is False
    assert superseded.state is ApprovalPresentationState.SUPERSEDED
    assert superseded.actionable is False


def test_expired_operational_approval_is_non_actionable() -> None:
    now = datetime(2026, 8, 15, tzinfo=UTC)
    metadata = OperationalApprovalMetadata(
        action_request_id="request-1",
        action_request_digest="digest-1",
        candidate_id="candidate-1",
        candidate_fingerprint="candidate-fingerprint-1",
        operational_plan_fingerprint="plan-fingerprint-1",
        provider_id="proxmox",
        resource_id="110",
        resource_type="qemu",
        target_fingerprint="target-fingerprint-1",
        target_version=None,
        operation_intent="restart-service",
        disruption_scope="brief interruption",
        verification_digest="verification-1",
        generated_at=now - timedelta(minutes=2),
        expires_at=now - timedelta(minutes=1),
    )
    presentation = classify_approval(
        result(
            purpose=ApprovalPurpose.OPERATIONAL_ACTION,
            identifier="approval-operational",
            operational_metadata=metadata,
        ),
        workflow(effect=WorkflowEffectKind.OPERATIONAL_ACTION),
        now=now,
    )

    assert presentation.state is ApprovalPresentationState.EXPIRED
    assert presentation.actionable is False


def test_approval_from_another_workflow_is_historical() -> None:
    presentation = classify_approval(
        result(workflow_id="workflow-2"),
        workflow(),
    )

    assert presentation.state is ApprovalPresentationState.HISTORICAL
    assert presentation.actionable is False
