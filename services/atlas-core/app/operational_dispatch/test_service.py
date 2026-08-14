import asyncio
from datetime import UTC, datetime
from unittest.mock import AsyncMock

from app.operational_dispatch.ledger import (
    OperationalDispatchLedger,
    OperationalLedgerState,
)
from app.operational_dispatch.models import (
    OperationalDispatchResult,
    OperationalDispatchStatus,
)
from app.operational_dispatch.registry import (
    OperationalHandlerRegistration,
    OperationalHandlerRegistry,
)
from app.operational_dispatch.service import OperationalDispatchService
from app.operational_dispatch.test_support import make_request, make_target
from app.providers.proxmox_operational import ProxmoxQemuGracefulRestartHandler
from app.services.provider_resources import ProviderResourceOperationError


def test_explicit_empty_gate_fails_closed_without_resolving_or_mutating(
    tmp_path,
) -> None:
    resolver = AsyncMock()
    ledger = OperationalDispatchLedger(tmp_path / "operational.db")
    result = asyncio.run(OperationalDispatchService(
        ledger=ledger,
        execution_intents=frozenset(),
        resolver=resolver,
    ).dispatch(make_request()))
    assert result.status is OperationalDispatchStatus.FAILED
    assert result.sanitized_message == "Operational execution capability is disabled."
    resolver.assert_not_awaited()
    assert ledger.get(result.request_id).state is OperationalLedgerState.FAILED  # type: ignore[union-attr]


def test_explicit_empty_gate_blocks_even_an_injected_proxmox_handler(tmp_path) -> None:
    client_factory = AsyncMock()
    handler = ProxmoxQemuGracefulRestartHandler(
        AsyncMock(), client_factory=client_factory
    )
    registry = OperationalHandlerRegistry(
        (
            OperationalHandlerRegistration(
                "restart-service", "proxmox", "qemu", handler
            ),
        )
    )
    resolver = AsyncMock()
    result = asyncio.run(
        OperationalDispatchService(
            ledger=OperationalDispatchLedger(tmp_path / "operational.db"),
            registry=registry,
            execution_intents=frozenset(),
            resolver=resolver,
        ).dispatch(make_request())
    )
    assert result.sanitized_message == "Operational execution capability is disabled."
    resolver.assert_not_awaited()
    client_factory.assert_not_called()


def test_target_replacement_blocks_before_dispatch_barrier(tmp_path) -> None:
    handler = AsyncMock()
    registry = OperationalHandlerRegistry(
        (
            OperationalHandlerRegistration(
                "restart-service", "proxmox", "qemu", handler
            ),
        )
    )
    resolver = AsyncMock(
        return_value=make_target(resource_id="qemu/101")
    )
    replacement = resolver.return_value.__class__(
        provider=resolver.return_value.provider,
        resource=resolver.return_value.resource,
        resource_fingerprint="target-fingerprint-v1:replaced",
    )
    resolver.return_value = replacement
    ledger = OperationalDispatchLedger(tmp_path / "operational.db")
    result = asyncio.run(OperationalDispatchService(
        ledger=ledger,
        registry=registry,
        execution_intents=frozenset({"restart-service"}),
        resolver=resolver,
    ).dispatch(make_request()))
    assert result.status is OperationalDispatchStatus.FAILED
    assert ledger.get(result.request_id).state is OperationalLedgerState.TARGET_REPLACED  # type: ignore[union-attr]
    handler.assert_not_awaited()


def test_enabled_intent_still_fails_closed_without_exact_handler(tmp_path) -> None:
    resolver = AsyncMock()
    result = asyncio.run(
        OperationalDispatchService(
            ledger=OperationalDispatchLedger(tmp_path / "operational.db"),
            execution_intents=frozenset({"restart-service"}),
            resolver=resolver,
        ).dispatch(make_request())
    )
    assert result.status is OperationalDispatchStatus.FAILED
    assert result.sanitized_message == "No exact operational handler is registered."
    resolver.assert_not_awaited()


def test_temporary_unavailability_stays_retryable_before_dispatch(tmp_path) -> None:
    handler = AsyncMock()
    now = datetime.now(UTC)
    request = make_request()
    handler.return_value = OperationalDispatchResult(
        status=OperationalDispatchStatus.SUCCEEDED,
        request_id="operational-action-1",
        request_digest=request.request_digest,
        target_fingerprint="target-fingerprint-v1:aaa",
        started_at=now,
        completed_at=now,
    )
    registry = OperationalHandlerRegistry(
        (OperationalHandlerRegistration("restart-service", "proxmox", "qemu", handler),)
    )
    unavailable = AsyncMock(
        side_effect=ProviderResourceOperationError("provider unavailable")
    )
    ledger = OperationalDispatchLedger(tmp_path / "operational.db")
    service = OperationalDispatchService(
        ledger=ledger,
        registry=registry,
        execution_intents=frozenset({"restart-service"}),
        resolver=unavailable,
    )
    first = asyncio.run(service.dispatch(request))
    assert first.status is OperationalDispatchStatus.FAILED
    assert ledger.get(request.request_id).state is OperationalLedgerState.CLAIMED  # type: ignore[union-attr]
    handler.assert_not_awaited()

    service = OperationalDispatchService(
        ledger=ledger,
        registry=registry,
        execution_intents=frozenset({"restart-service"}),
        resolver=AsyncMock(return_value=make_target()),
    )
    second = asyncio.run(service.dispatch(request))
    assert second.status is OperationalDispatchStatus.SUCCEEDED
    assert handler.await_count == 1


def test_unknown_outcome_record_is_returned_without_handler_replay(tmp_path) -> None:
    path = tmp_path / "operational.db"
    request = make_request()
    ledger = OperationalDispatchLedger(path)
    ledger.claim(request)
    ledger.mark_revalidated(request)
    ledger.mark_dispatching(request)
    OperationalDispatchLedger(path).reconcile_startup()
    handler = AsyncMock()
    registry = OperationalHandlerRegistry(
        (OperationalHandlerRegistration("restart-service", "proxmox", "qemu", handler),)
    )
    result = asyncio.run(OperationalDispatchService(
        ledger=OperationalDispatchLedger(path),
        registry=registry,
        execution_intents=frozenset({"restart-service"}),
        resolver=AsyncMock(return_value=make_target()),
    ).dispatch(request))
    assert result.status is OperationalDispatchStatus.OUTCOME_UNKNOWN
    handler.assert_not_awaited()


def test_revalidated_pre_dispatch_record_can_retry_after_restart(tmp_path) -> None:
    path = tmp_path / "operational.db"
    request = make_request()
    ledger = OperationalDispatchLedger(path)
    ledger.claim(request)
    ledger.mark_revalidated(request)
    summary = OperationalDispatchLedger(path).reconcile_startup()
    assert summary["retryable_pre_dispatch"] == 1

    now = datetime.now(UTC)
    handler = AsyncMock(
        return_value=OperationalDispatchResult(
            status=OperationalDispatchStatus.SUCCEEDED,
            request_id=request.request_id,
            request_digest=request.request_digest,
            target_fingerprint=request.target_fingerprint,
            started_at=now,
            completed_at=now,
        )
    )
    registry = OperationalHandlerRegistry(
        (OperationalHandlerRegistration("restart-service", "proxmox", "qemu", handler),)
    )
    result = asyncio.run(
        OperationalDispatchService(
            ledger=OperationalDispatchLedger(path),
            registry=registry,
            execution_intents=frozenset({"restart-service"}),
            resolver=AsyncMock(return_value=make_target()),
        ).dispatch(request)
    )
    assert result.status is OperationalDispatchStatus.SUCCEEDED
    assert handler.await_count == 1
