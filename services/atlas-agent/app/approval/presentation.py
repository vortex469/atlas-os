"""Effect-aware, read-only approval presentation classification."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum

from app.approval.models import (
    ApprovalPurpose,
    ApprovalResult,
    ApprovalStatus,
)
from app.candidate_planning.models import operational_verification_digest
from app.workflow.models import (
    WorkflowEffectKind,
    WorkflowSession,
    WorkflowSessionState,
)


class ApprovalPresentationState(StrEnum):
    ACTIONABLE = "actionable"
    HISTORICAL = "historical"
    EXPIRED = "expired"
    SUPERSEDED = "superseded"
    RESOLVED = "resolved"


@dataclass(frozen=True, slots=True)
class ApprovalPresentation:
    state: ApprovalPresentationState
    actionable: bool
    reason: str


_REPOSITORY_STATES = {
    ApprovalPurpose.CANDIDATE_WORKFLOW_SHELL: WorkflowSessionState.AWAITING_APPROVAL,
    ApprovalPurpose.IMPLEMENTATION: WorkflowSessionState.AWAITING_IMPLEMENTATION_APPROVAL,
    ApprovalPurpose.VERIFICATION: WorkflowSessionState.AWAITING_VERIFICATION_APPROVAL,
    ApprovalPurpose.COMMIT: WorkflowSessionState.AWAITING_COMMIT_APPROVAL,
}
_OPERATIONAL_STATES = {
    ApprovalPurpose.CANDIDATE_WORKFLOW_SHELL: WorkflowSessionState.AWAITING_APPROVAL,
    ApprovalPurpose.OPERATIONAL_ACTION: WorkflowSessionState.AWAITING_IMPLEMENTATION_APPROVAL,
}


def _binding_is_current(result: ApprovalResult, workflow: WorkflowSession) -> bool:
    request = result.decision.request
    if request.workflow_id != workflow.identifier:
        return False
    metadata = workflow.candidate_metadata
    if request.purpose is ApprovalPurpose.CANDIDATE_WORKFLOW_SHELL:
        return metadata is not None and request.checkpoint_id == metadata.candidate_plan_id
    if request.purpose is ApprovalPurpose.IMPLEMENTATION:
        return request.identifier == workflow.candidate_implementation_approval_id
    if request.purpose is ApprovalPurpose.OPERATIONAL_ACTION:
        operational = request.operational_metadata
        action = workflow.operational_action_request
        return (
            request.identifier == workflow.operational_action_approval_id
            and operational is not None
            and action is not None
            and operational.action_request_id == action.request_id
            and operational.action_request_digest == action.request_digest
            and operational.candidate_id == action.candidate_id
            and operational.candidate_fingerprint == action.candidate_fingerprint
            and operational.operational_plan_fingerprint
            == action.candidate_plan_fingerprint
            and operational.provider_id == action.provider_id
            and operational.resource_id == action.resource_id
            and operational.resource_type == action.resource_type
            and operational.target_fingerprint == action.target_fingerprint
            and operational.target_version == action.target_version
            and operational.operation_intent == action.execution_intent
            and operational.disruption_scope == action.disruption_scope
            and operational.verification_digest
            == operational_verification_digest(action.verification)
        )
    if request.purpose is ApprovalPurpose.VERIFICATION:
        return request.identifier == f"approval-verification-{workflow.identifier}"
    if request.purpose is ApprovalPurpose.COMMIT:
        return (
            request.identifier == f"approval-commit-{workflow.identifier}"
            and request.commit_metadata is not None
            and workflow.commit_request is not None
        )
    return False


def classify_approval(
    result: ApprovalResult,
    workflow: WorkflowSession,
    *,
    successor_exists: bool = False,
    now: datetime | None = None,
) -> ApprovalPresentation:
    """Classify presentation without granting or changing approval authority."""

    if result.decision.status is not ApprovalStatus.PENDING:
        return ApprovalPresentation(
            ApprovalPresentationState.RESOLVED,
            False,
            "Approval already has a terminal decision.",
        )
    if successor_exists:
        return ApprovalPresentation(
            ApprovalPresentationState.SUPERSEDED,
            False,
            "A successor planning session replaces this workflow lineage.",
        )
    operational = result.decision.request.operational_metadata
    if operational is not None and operational.expires_at <= (now or datetime.now(UTC)):
        return ApprovalPresentation(
            ApprovalPresentationState.EXPIRED,
            False,
            "The immutable operational approval has expired.",
        )

    expected_states = (
        _OPERATIONAL_STATES
        if workflow.effect_kind is WorkflowEffectKind.OPERATIONAL_ACTION
        else _REPOSITORY_STATES
    )
    expected_state = expected_states.get(result.decision.request.purpose)
    if (
        expected_state is None
        or workflow.state is not expected_state
        or not _binding_is_current(result, workflow)
    ):
        return ApprovalPresentation(
            ApprovalPresentationState.HISTORICAL,
            False,
            "Approval is not valid for the workflow's current effect, state, and binding.",
        )
    return ApprovalPresentation(
        ApprovalPresentationState.ACTIONABLE,
        True,
        "Approval is pending and bound to the current workflow stage.",
    )
