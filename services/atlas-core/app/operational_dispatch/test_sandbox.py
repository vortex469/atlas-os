from datetime import UTC, datetime, timedelta

import pytest

from app.operational_dispatch.ledger import (
    OperationalDispatchLedger,
    OperationalLedgerState,
)
from app.operational_dispatch.models import (
    OperationalDispatchAuditEvent,
    OperationalDispatchAuditStatus,
    OperationalDispatchResult,
)
from app.operational_dispatch.sandbox import (
    SandboxAuthorization,
    print_sandbox_evidence,
    print_sandbox_preflight,
    validate_sandbox_scope,
)
from app.operational_dispatch.test_support import make_request


def authorization(request, **changes) -> SandboxAuthorization:
    values = {
        "purpose": "approved-non-critical-qemu-graceful-restart",
        "node": "pve1",
        "vmid": request.resource_id,
        "request_digest": request.request_digest,
        "resource_fingerprint": request.target_fingerprint,
        "expires_at": datetime.now(UTC) + timedelta(minutes=5),
        "maximum_attempts": 1,
    }
    values.update(changes)
    return SandboxAuthorization.model_validate(values)


def test_sandbox_scope_binds_exact_target_and_single_attempt() -> None:
    request = make_request(resource_id="101")
    approval = authorization(request)
    validate_sandbox_scope(
        request,
        approval,
        node="pve1",
        vmid="101",
        fingerprint=request.target_fingerprint,
    )
    with pytest.raises(ValueError, match="exact request target"):
        validate_sandbox_scope(
            request,
            approval,
            node="pve2",
            vmid="101",
            fingerprint=request.target_fingerprint,
        )
    with pytest.raises(ValueError, match="exactly one attempt"):
        authorization(request, maximum_attempts=2)


def test_sandbox_rejects_unapproved_or_expired_noncritical_assertion() -> None:
    request = make_request(resource_id="101")
    with pytest.raises(ValueError, match="not approved as non-critical"):
        authorization(request, purpose="generic-restart")
    with pytest.raises(ValueError, match="expired"):
        authorization(request, expires_at=datetime.now(UTC) - timedelta(seconds=1))


def test_sandbox_preflight_prints_exact_action_and_ledger_path(capsys, tmp_path) -> None:
    request = make_request()
    ledger_path = tmp_path / "sandbox.db"

    print_sandbox_preflight(
        request,
        ledger_path=ledger_path,
        node="pve1",
        vmid="101",
        display_name="sandbox VM",
        current_state="running",
        resource_fingerprint=request.target_fingerprint,
    )

    output = capsys.readouterr().out
    assert f"provider action ID: {request.provider_action_id}" in output
    assert f"sandbox ledger path: {ledger_path}" in output


def test_sandbox_prints_durable_transitions_and_sanitized_audit(
    tmp_path, capsys
) -> None:
    request = make_request()
    ledger = OperationalDispatchLedger(tmp_path / "sandbox.db")
    ledger.claim(request)
    ledger.mark_revalidated(request)
    now = datetime.now(UTC)
    ledger.persist_dispatch_result(
        request,
        OperationalDispatchResult(
            status="failed",
            request_id=request.request_id,
            request_digest=request.request_digest,
            target_fingerprint=request.target_fingerprint,
            started_at=now,
            completed_at=now,
            sanitized_message="must-not-print",
        ),
        state=OperationalLedgerState.FAILED,
    )
    ledger.append_event(
        OperationalDispatchAuditEvent(
            event_id="event-1",
            status=OperationalDispatchAuditStatus.DISPATCH_RESULT,
            occurred_at=now,
            request_id=request.request_id,
        )
    )

    print_sandbox_evidence(ledger, request)

    output = capsys.readouterr().out
    assert "durable ledger transitions:" in output
    assert "initial -> claimed" in output
    assert "claimed -> revalidated" in output
    assert "revalidated -> failed" in output
    assert "sanitized operational audit events:" in output
    assert "dispatch_result at" in output
    assert "must-not-print" not in output
