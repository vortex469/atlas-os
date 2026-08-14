import asyncio
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

from app.operational_dispatch.ledger import (
    OperationalDispatchLedger,
    OperationalLedgerState,
)
from app.operational_dispatch.lifecycle import (
    OperationalLifecycleService,
    OperationalVerifierRegistry,
)
from app.operational_dispatch.models import (
    OperationalDispatchAuditStatus,
    OperationalDispatchResult,
    OperationalDispatchStatus,
    OperationalVerificationResult,
    OperationalVerificationStatus,
)
from app.operational_dispatch.registry import (
    OperationalHandlerRegistration,
    OperationalHandlerRegistry,
)
from app.operational_dispatch.service import OperationalDispatchService
from app.operational_dispatch.test_support import make_request, make_target

UPID = "UPID:pve1:00000001:00000002:00000003:qmreboot:101:atlas@pve:"


def dispatch_result(request, *, status=OperationalDispatchStatus.SUCCEEDED, upid=UPID):
    now = datetime.now(UTC)
    return OperationalDispatchResult(
        status=status,
        request_id=request.request_id,
        request_digest=request.request_digest,
        target_fingerprint=request.target_fingerprint,
        provider_operation_id=upid,
        started_at=now,
        completed_at=now,
    )


def verification_result(request, status=OperationalVerificationStatus.SUCCEEDED):
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


def registry(verifier) -> OperationalVerifierRegistry:
    verifiers = OperationalVerifierRegistry()
    verifiers.register(
        execution_intent="restart-service",
        provider_id="proxmox",
        resource_type="qemu",
        verifier=verifier,
    )
    return verifiers


def persisted_dispatch(ledger, request, *, state, result):
    ledger.claim(request)
    ledger.mark_revalidated(request)
    ledger.mark_dispatching(request)
    return ledger.persist_dispatch_result(request, result, state=state)


def test_successful_dispatch_schedules_verification_without_mutation_replay(
    tmp_path,
) -> None:
    async def scenario() -> None:
        request = make_request(resource_id="101")
        handler = AsyncMock(return_value=dispatch_result(request))
        handlers = OperationalHandlerRegistry(
            (
                OperationalHandlerRegistration(
                    "restart-service", "proxmox", "qemu", handler
                ),
            )
        )
        ledger = OperationalDispatchLedger(tmp_path / "operational.db")
        dispatcher = OperationalDispatchService(
            ledger=ledger,
            registry=handlers,
            execution_intents=frozenset({"restart-service"}),
            resolver=AsyncMock(return_value=make_target(resource_id="101")),
        )
        verifier = AsyncMock(return_value=verification_result(request))
        lifecycle = OperationalLifecycleService(
            ledger=ledger,
            dispatcher=dispatcher,
            verifiers=registry(verifier),
        )
        result = await lifecycle.dispatch(request)
        assert result.provider_operation_id == UPID
        while lifecycle.status(request.request_id).verification_result is None:  # type: ignore[union-attr]
            await asyncio.sleep(0)
        await lifecycle.close()
        entry = ledger.get(request.request_id)
        assert entry is not None and entry.state is OperationalLedgerState.VERIFIED
        handler.assert_awaited_once()
        verifier.assert_awaited_once_with(request, result, request.expires_at)
        statuses = {event.status for event in ledger.list_events()}
        assert OperationalDispatchAuditStatus.BARRIER_CROSSED in statuses
        assert OperationalDispatchAuditStatus.PROVIDER_OPERATION_CAPTURED in statuses
        assert OperationalDispatchAuditStatus.VERIFICATION_STARTED in statuses
        assert OperationalDispatchAuditStatus.VERIFICATION_SUCCEEDED in statuses

    asyncio.run(scenario())


def test_crash_states_reconcile_without_replaying_mutation(tmp_path) -> None:
    path = tmp_path / "operational.db"
    request = make_request()
    ledger = OperationalDispatchLedger(path)
    ledger.claim(request)
    assert ledger.reconcile_startup()["retryable_pre_dispatch"] == 1
    ledger.mark_revalidated(request)
    assert ledger.reconcile_startup()["retryable_pre_dispatch"] == 1
    ledger.mark_dispatching(request)
    assert ledger.reconcile_startup()["outcome_unknown"] == 1
    recovered = OperationalDispatchLedger(path).get(request.request_id)
    assert recovered is not None
    assert recovered.state is OperationalLedgerState.OUTCOME_UNKNOWN
    assert recovered.dispatch_result is not None
    assert recovered.dispatch_result.provider_operation_id is None
    assert OperationalDispatchLedger(path).list_verification_candidates() == ()
    recovery_statuses = {
        event.status for event in OperationalDispatchLedger(path).list_events()
    }
    assert OperationalDispatchAuditStatus.OUTCOME_UNKNOWN in recovery_statuses
    assert OperationalDispatchAuditStatus.RECOVERY_RECONCILED in recovery_statuses

    handler = AsyncMock()
    result = asyncio.run(
        OperationalDispatchService(
            ledger=OperationalDispatchLedger(path),
            registry=OperationalHandlerRegistry(
                (
                    OperationalHandlerRegistration(
                        "restart-service", "proxmox", "qemu", handler
                    ),
                )
            ),
            execution_intents=frozenset({"restart-service"}),
            resolver=AsyncMock(),
        ).dispatch(request)
    )
    assert result.status is OperationalDispatchStatus.OUTCOME_UNKNOWN
    handler.assert_not_awaited()


def test_startup_resumes_succeeded_unknown_and_interrupted_verification(tmp_path) -> None:
    async def scenario(state: OperationalLedgerState) -> None:
        path = tmp_path / f"{state.value}.db"
        request = make_request(request_id=f"request-{state.value}")
        ledger = OperationalDispatchLedger(path)
        result_status = (
            OperationalDispatchStatus.OUTCOME_UNKNOWN
            if state is OperationalLedgerState.OUTCOME_UNKNOWN
            else OperationalDispatchStatus.SUCCEEDED
        )
        persisted_dispatch(
            ledger,
            request,
            state=(
                OperationalLedgerState.OUTCOME_UNKNOWN
                if result_status is OperationalDispatchStatus.OUTCOME_UNKNOWN
                else OperationalLedgerState.SUCCEEDED
            ),
            result=dispatch_result(request, status=result_status),
        )
        if state is OperationalLedgerState.VERIFYING:
            ledger.begin_verification(request)
        verifier = AsyncMock(return_value=verification_result(request))
        lifecycle = OperationalLifecycleService(
            ledger=OperationalDispatchLedger(path),
            dispatcher=MagicMock(),
            verifiers=registry(verifier),
        )
        assert lifecycle.schedule_startup_recovery() == 1
        while lifecycle.status(request.request_id).ledger_state in {
            state.value,
            "verifying",
        }:  # type: ignore[union-attr]
            await asyncio.sleep(0)
        await lifecycle.close()
        entry = OperationalDispatchLedger(path).get(request.request_id)
        assert entry is not None and entry.state is OperationalLedgerState.VERIFIED
        verifier.assert_awaited_once()

    for state in (
        OperationalLedgerState.SUCCEEDED,
        OperationalLedgerState.OUTCOME_UNKNOWN,
        OperationalLedgerState.VERIFYING,
    ):
        asyncio.run(scenario(state))


def test_verified_unknown_is_immutable_and_no_upid_never_resumes(tmp_path) -> None:
    async def scenario() -> None:
        request = make_request()
        ledger = OperationalDispatchLedger(tmp_path / "operational.db")
        persisted_dispatch(
            ledger,
            request,
            state=OperationalLedgerState.SUCCEEDED,
            result=dispatch_result(request),
        )
        verifier = AsyncMock(
            return_value=verification_result(
                request, OperationalVerificationStatus.OUTCOME_UNKNOWN
            )
        )
        lifecycle = OperationalLifecycleService(
            ledger=ledger,
            dispatcher=MagicMock(),
            verifiers=registry(verifier),
        )
        await lifecycle.reconcile(request.request_id)
        status = lifecycle.status(request.request_id)
        assert status is not None
        assert status.ledger_state == "outcome_unknown"
        assert status.verification_result is not None
        assert status.verification_resumable is False
        await lifecycle.reconcile(request.request_id, recovery=True)
        verifier.assert_awaited_once()

        second = make_request(request_id="without-upid")
        persisted_dispatch(
            ledger,
            second,
            state=OperationalLedgerState.OUTCOME_UNKNOWN,
            result=dispatch_result(
                second,
                status=OperationalDispatchStatus.OUTCOME_UNKNOWN,
                upid=None,
            ),
        )
        assert lifecycle.schedule_verification(second.request_id, recovery=True) is False

    asyncio.run(scenario())
