"""Sanitized operational lifecycle read-model tests."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.operational_dispatch.ledger import (
    OperationalDispatchLedger,
    OperationalLedgerState,
)
from app.operational_dispatch.models import (
    OperationalDispatchAuditEvent,
    OperationalDispatchAuditStatus,
    OperationalDispatchResult,
    OperationalDispatchStatus,
    OperationalVerificationResult,
    OperationalVerificationStatus,
)
from app.operational_dispatch.read_model import project_operational_lifecycle
from app.operational_dispatch.test_support import make_request


def _verifying_ledger(tmp_path):
    ledger = OperationalDispatchLedger(tmp_path / "read-model.db")
    request = make_request()
    now = datetime.now(UTC)
    ledger.claim(request)
    ledger.mark_revalidated(request)
    ledger.mark_dispatching(request)
    ledger.persist_dispatch_result(
        request,
        OperationalDispatchResult(
            status=OperationalDispatchStatus.SUCCEEDED,
            request_id=request.request_id,
            request_digest=request.request_digest,
            target_fingerprint=request.target_fingerprint,
            provider_operation_id="UPID:sanitized",
            started_at=now,
            completed_at=now,
        ),
        state=OperationalLedgerState.SUCCEEDED,
    )
    ledger.append_event(
        OperationalDispatchAuditEvent(
            event_id=uuid4().hex,
            status=OperationalDispatchAuditStatus.PROVIDER_OPERATION_CAPTURED,
            occurred_at=now,
            request_id=request.request_id,
            request_digest=request.request_digest,
        )
    )
    ledger.begin_verification(request)
    return ledger, request, now


def test_verification_pending_projection_is_nonterminal(tmp_path) -> None:
    ledger, request, _now = _verifying_ledger(tmp_path)

    result = project_operational_lifecycle(ledger, request.request_id)

    assert result is not None
    assert result.ledger_state == "verifying"
    assert result.terminal is False
    assert result.barrier_crossing_count == 1
    assert result.provider_operation_capture_count == 1
    assert [item.sequence for item in result.transitions] == sorted(
        item.sequence for item in result.transitions
    )


@pytest.mark.parametrize(
    ("status", "state", "reason"),
    [
        (OperationalVerificationStatus.SUCCEEDED, "verified", None),
        (
            OperationalVerificationStatus.VERIFICATION_FAILED,
            "verification_failed",
            "verification_failed",
        ),
        (
            OperationalVerificationStatus.TARGET_REPLACED,
            "target_replaced",
            "target_replaced",
        ),
        (
            OperationalVerificationStatus.OUTCOME_UNKNOWN,
            "outcome_unknown",
            "outcome_unknown",
        ),
    ],
)
def test_terminal_verification_outcomes_are_distinct(
    tmp_path, status, state, reason
) -> None:
    ledger, request, now = _verifying_ledger(tmp_path)
    ledger.persist_verification_result(
        request,
        OperationalVerificationResult(
            status=status,
            request_id=request.request_id,
            observed_target_fingerprint=request.target_fingerprint,
            observed_state="running",
            health_status="running",
            started_at=now,
            completed_at=now,
            deadline=request.expires_at,
        ),
    )

    result = project_operational_lifecycle(ledger, request.request_id)

    assert result is not None
    assert result.ledger_state == state
    assert result.controlled_reason == reason
    assert result.terminal is True
