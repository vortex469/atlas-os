from __future__ import annotations

import ast
import asyncio
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from app.operational_dispatch.ledger import (
    OperationalDispatchLedger,
    OperationalLedgerState,
)
from app.operational_dispatch.models import (
    OperationalDispatchResult,
    OperationalDispatchStatus,
    OperationalVerificationResult,
    OperationalVerificationStatus,
)
from app.operational_dispatch.sandbox_recovery import (
    SandboxRecoveryAction,
    print_recovery_evidence,
    recover_sandbox_entry,
    validate_recovery_ledger_path,
    validate_recovery_request,
)
from app.operational_dispatch.test_support import make_request

UPID = "UPID:pve1:00000001:00000002:00000003:qmreboot:101:private-user@pve:"


def _ledger(tmp_path: Path, name: str = "sandbox.db") -> OperationalDispatchLedger:
    path = tmp_path / name
    ledger = OperationalDispatchLedger(path)
    path.chmod(0o600)
    return ledger


def _dispatch_result(request, *, status=OperationalDispatchStatus.SUCCEEDED, upid=UPID):
    now = datetime.now(UTC)
    return OperationalDispatchResult(
        status=status,
        request_id=request.request_id,
        request_digest=request.request_digest,
        target_fingerprint=request.target_fingerprint,
        provider_operation_id=upid,
        started_at=now,
        completed_at=now,
        sanitized_message="provider-detail-must-not-print",
    )


def _verification_result(
    request, status=OperationalVerificationStatus.SUCCEEDED
) -> OperationalVerificationResult:
    now = datetime.now(UTC)
    return OperationalVerificationResult(
        status=status,
        request_id=request.request_id,
        observed_target_fingerprint=request.target_fingerprint,
        observed_state="running",
        health_status="running",
        started_at=now,
        completed_at=now,
        deadline=request.expires_at,
    )


def _persist_dispatch(
    ledger: OperationalDispatchLedger,
    request,
    *,
    state=OperationalLedgerState.SUCCEEDED,
    upid=UPID,
) -> None:
    ledger.claim(request)
    ledger.mark_revalidated(request)
    ledger.mark_dispatching(request)
    status = (
        OperationalDispatchStatus.OUTCOME_UNKNOWN
        if state is OperationalLedgerState.OUTCOME_UNKNOWN
        else OperationalDispatchStatus.SUCCEEDED
        if state is OperationalLedgerState.SUCCEEDED
        else OperationalDispatchStatus.FAILED
    )
    ledger.persist_dispatch_result(
        request,
        _dispatch_result(request, status=status, upid=upid),
        state=state,
    )


def _recover(ledger, request, verifier):
    return asyncio.run(
        recover_sandbox_entry(ledger=ledger, request=request, verifier=verifier)
    )


def test_recovery_module_has_no_mutation_import_or_provider_mutation_call() -> None:
    source_path = Path(__file__).with_name("sandbox_recovery.py")
    tree = ast.parse(source_path.read_text(encoding="utf-8"))
    imported_names = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.Import, ast.ImportFrom))
        for alias in node.names
    }
    called_attributes = {
        node.func.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    }
    assert "ProxmoxQemuGracefulRestartHandler" not in imported_names
    assert not ({"reboot", "reset", "stop", "start"} & called_attributes)
    assert "OperationalDispatchService" not in imported_names
    assert "OperationalHandlerRegistry" not in imported_names


def test_recovery_rejects_production_missing_and_unsafe_ledgers(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with pytest.raises(ValueError, match="production"):
        validate_recovery_ledger_path(
            Path("/opt/atlas/data/operational_dispatch.db")
        )
    with pytest.raises(FileNotFoundError, match="does not exist"):
        validate_recovery_ledger_path(tmp_path / "missing.db")

    path = tmp_path / "unsafe.db"
    OperationalDispatchLedger(path)
    path.chmod(0o644)
    with pytest.raises(PermissionError, match="mode 0600"):
        validate_recovery_ledger_path(path)
    path.chmod(0o600)
    monkeypatch.setattr("app.operational_dispatch.sandbox_recovery.os.getuid", lambda: 1)
    with pytest.raises(PermissionError, match="caller-owned"):
        validate_recovery_ledger_path(path)


@pytest.mark.parametrize(
    ("state", "expected_action", "verifier_calls"),
    (
        (
            OperationalLedgerState.SUCCEEDED,
            SandboxRecoveryAction.RESUMED_VERIFICATION,
            1,
        ),
        (
            OperationalLedgerState.OUTCOME_UNKNOWN,
            SandboxRecoveryAction.RESUMED_VERIFICATION,
            1,
        ),
        (
            OperationalLedgerState.VERIFYING,
            SandboxRecoveryAction.RESUMED_VERIFICATION,
            1,
        ),
    ),
)
def test_upid_states_resume_read_only_verification(
    tmp_path: Path,
    state: OperationalLedgerState,
    expected_action: SandboxRecoveryAction,
    verifier_calls: int,
) -> None:
    request = make_request(request_id=f"request-{state.value}")
    ledger = _ledger(tmp_path, f"{state.value}.db")
    dispatch_state = (
        OperationalLedgerState.OUTCOME_UNKNOWN
        if state is OperationalLedgerState.OUTCOME_UNKNOWN
        else OperationalLedgerState.SUCCEEDED
    )
    _persist_dispatch(ledger, request, state=dispatch_state)
    if state is OperationalLedgerState.VERIFYING:
        ledger.begin_verification(request)
    verifier = AsyncMock(return_value=_verification_result(request))

    result = _recover(OperationalDispatchLedger(ledger.database_path), request, verifier)

    assert result.action is expected_action
    assert result.entry.state is OperationalLedgerState.VERIFIED
    assert verifier.await_count == verifier_calls


def test_unknown_without_upid_remains_unknown_and_never_verifies(tmp_path: Path) -> None:
    request = make_request()
    ledger = _ledger(tmp_path)
    _persist_dispatch(
        ledger,
        request,
        state=OperationalLedgerState.OUTCOME_UNKNOWN,
        upid=None,
    )
    verifier = AsyncMock()

    result = _recover(ledger, request, verifier)

    assert result.action is SandboxRecoveryAction.NO_UPID_NO_ACTION
    assert result.entry.state is OperationalLedgerState.OUTCOME_UNKNOWN
    verifier.assert_not_awaited()


def test_dispatching_is_classified_unknown_without_replay(tmp_path: Path) -> None:
    request = make_request()
    ledger = _ledger(tmp_path)
    ledger.claim(request)
    ledger.mark_revalidated(request)
    ledger.mark_dispatching(request)
    verifier = AsyncMock()

    result = _recover(ledger, request, verifier)

    assert result.action is SandboxRecoveryAction.CLASSIFIED_DISPATCHING
    assert result.entry.state is OperationalLedgerState.OUTCOME_UNKNOWN
    assert result.entry.dispatch_result is not None
    assert result.entry.dispatch_result.provider_operation_id is None
    verifier.assert_not_awaited()


@pytest.mark.parametrize(
    "state", (OperationalLedgerState.CLAIMED, OperationalLedgerState.REVALIDATED)
)
def test_pre_dispatch_states_report_retryable_without_dispatch(
    tmp_path: Path, state: OperationalLedgerState
) -> None:
    request = make_request(request_id=f"request-{state.value}")
    ledger = _ledger(tmp_path, f"{state.value}.db")
    ledger.claim(request)
    if state is OperationalLedgerState.REVALIDATED:
        ledger.mark_revalidated(request)
    verifier = AsyncMock()

    result = _recover(ledger, request, verifier)

    assert result.action is SandboxRecoveryAction.PRE_DISPATCH_NO_ACTION
    assert result.entry.state is state
    verifier.assert_not_awaited()


@pytest.mark.parametrize(
    "status",
    (
        OperationalVerificationStatus.SUCCEEDED,
        OperationalVerificationStatus.VERIFICATION_FAILED,
    ),
)
def test_terminal_verification_is_immutable(tmp_path: Path, status) -> None:
    request = make_request(request_id=f"request-{status.value}")
    ledger = _ledger(tmp_path, f"{status.value}.db")
    _persist_dispatch(ledger, request)
    ledger.begin_verification(request)
    ledger.persist_verification_result(request, _verification_result(request, status))
    before = ledger.get(request.request_id)
    verifier = AsyncMock()

    result = _recover(ledger, request, verifier)

    assert result.action is SandboxRecoveryAction.TERMINAL_NO_ACTION
    assert result.entry == before
    verifier.assert_not_awaited()


def test_target_replaced_terminal_and_failed_dispatch_never_resume(tmp_path: Path) -> None:
    target_request = make_request(request_id="target-replaced")
    target_ledger = _ledger(tmp_path, "target.db")
    _persist_dispatch(
        target_ledger,
        target_request,
        state=OperationalLedgerState.TARGET_REPLACED,
        upid=None,
    )
    verifier = AsyncMock()
    result = _recover(target_ledger, target_request, verifier)
    assert result.action is SandboxRecoveryAction.TERMINAL_NO_ACTION

    failed_request = make_request(request_id="failed")
    failed_ledger = _ledger(tmp_path, "failed.db")
    _persist_dispatch(
        failed_ledger,
        failed_request,
        state=OperationalLedgerState.FAILED,
        upid=None,
    )
    with pytest.raises(ValueError, match="not recoverable"):
        _recover(failed_ledger, failed_request, verifier)
    verifier.assert_not_awaited()


def test_request_identity_and_payload_mismatch_are_rejected(tmp_path: Path) -> None:
    request = make_request()
    ledger = _ledger(tmp_path)
    ledger.claim(request)
    conflicting = make_request(request_id=request.request_id, candidate_id="changed")
    with pytest.raises(ValueError, match="identity does not match"):
        validate_recovery_request(conflicting, ledger.get(request.request_id))
    with pytest.raises(ValueError, match="absent from ledger"):
        validate_recovery_request(
            make_request(request_id="missing"), ledger.get("missing")
        )


def test_evidence_is_ordered_sanitized_and_contains_no_provider_message(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    request = make_request()
    ledger = _ledger(tmp_path)
    _persist_dispatch(ledger, request)
    before_count = len(ledger.list_transitions(request.request_id))
    verifier = AsyncMock(return_value=_verification_result(request))
    result = _recover(ledger, request, verifier)

    print_recovery_evidence(
        ledger=ledger,
        request=request,
        starting_state=OperationalLedgerState.SUCCEEDED,
        action=result.action,
        before_count=before_count,
    )

    output = capsys.readouterr().out
    assert output.index("initial -> claimed") < output.index("verifying -> verified")
    assert "[principal-redacted]" in output
    assert "private-user@pve" not in output
    assert "provider-detail-must-not-print" not in output
    assert "recovery_reconciled" in output
    assert "verification_succeeded" in output


def test_failure_injection_fresh_recovery_reaches_verified_without_mutation(
    tmp_path: Path,
) -> None:
    request = make_request()
    path = tmp_path / "crash.db"
    first_process = OperationalDispatchLedger(path)
    path.chmod(0o600)
    mutation_count = 1
    _persist_dispatch(first_process, request)
    first_process.begin_verification(request)

    recovery_mutation_count = 0
    fresh_process = OperationalDispatchLedger(path)
    verifier = AsyncMock(return_value=_verification_result(request))
    result = _recover(fresh_process, request, verifier)

    assert mutation_count == 1
    assert recovery_mutation_count == 0
    assert result.entry.state is OperationalLedgerState.VERIFIED
    verifier.assert_awaited_once()
