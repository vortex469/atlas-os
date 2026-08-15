"""Sanitized read-only projection of Core-owned operational lifecycle facts."""

from app.operational_dispatch.ledger import (
    FINAL_STATES,
    OperationalDispatchLedger,
    OperationalLedgerState,
    validate_ledger_transition_sequence,
)
from app.operational_dispatch.models import (
    OperationalDispatchAuditStatus,
    OperationalLifecycleRead,
    OperationalLifecycleTransitionRead,
)


def project_operational_lifecycle(
    ledger: OperationalDispatchLedger, request_id: str
) -> OperationalLifecycleRead | None:
    """Project durable state without reconciliation or provider access."""

    entry = ledger.get(request_id)
    if entry is None:
        return None
    transitions = ledger.list_transitions(request_id)
    events = ledger.list_request_events(request_id)
    barrier_count = sum(
        transition.state is OperationalLedgerState.DISPATCHING
        for transition in transitions
    )
    provider_count = sum(
        event.status is OperationalDispatchAuditStatus.PROVIDER_OPERATION_CAPTURED
        for event in events
    )
    dispatch = entry.dispatch_result
    verification = entry.verification_result
    controlled_reason = _controlled_reason(entry.state, dispatch.status.value if dispatch else None)
    return OperationalLifecycleRead(
        request_id=entry.request_id,
        request_digest=entry.request_digest,
        ledger_state=entry.state.value,
        transitions=tuple(
            OperationalLifecycleTransitionRead(
                sequence=item.sequence,
                state=item.state.value,
                occurred_at=item.occurred_at,
            )
            for item in transitions
        ),
        transition_sequence_valid=validate_ledger_transition_sequence(
            transitions,
            request_id=entry.request_id,
            request_digest=entry.request_digest,
            current_state=entry.state,
        ),
        barrier_crossed=barrier_count > 0,
        barrier_crossing_count=barrier_count,
        provider_operation_captured=provider_count > 0,
        provider_operation_capture_count=provider_count,
        dispatch_status=dispatch.status.value if dispatch else None,
        provider_operation_reference=dispatch.provider_operation_id if dispatch else None,
        dispatch_started_at=entry.dispatch_started_at,
        dispatch_completed_at=dispatch.completed_at if dispatch else None,
        verification_status=verification.status.value if verification else None,
        observed_target_fingerprint=(
            verification.observed_target_fingerprint if verification else None
        ),
        observed_state=verification.observed_state if verification else None,
        observed_health=verification.health_status if verification else None,
        verification_started_at=verification.started_at if verification else None,
        verification_completed_at=verification.completed_at if verification else None,
        verification_deadline=verification.deadline if verification else None,
        terminal=(
            verification is not None
            or entry.state in FINAL_STATES
            or entry.state is OperationalLedgerState.FAILED
        ),
        controlled_reason=controlled_reason,
    )


def _controlled_reason(state: OperationalLedgerState, dispatch_status: str | None) -> str | None:
    if state is OperationalLedgerState.VERIFICATION_FAILED:
        return "verification_failed"
    if state is OperationalLedgerState.TARGET_REPLACED:
        return "target_replaced"
    if state is OperationalLedgerState.OUTCOME_UNKNOWN or dispatch_status == "outcome_unknown":
        return "outcome_unknown"
    if state is OperationalLedgerState.FAILED:
        return "dispatch_failed"
    return None
