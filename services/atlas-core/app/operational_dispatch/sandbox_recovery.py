"""Verifier-only recovery for an existing non-production sandbox ledger."""

from __future__ import annotations

import argparse
import asyncio
import os
import stat
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from uuid import uuid4

from app.operational_dispatch.ledger import (
    FINAL_STATES,
    OperationalDispatchLedger,
    OperationalLedgerEntry,
    OperationalLedgerState,
)
from app.operational_dispatch.models import (
    OperationalDispatchAuditEvent,
    OperationalDispatchAuditStatus,
    OperationalDispatchRequest,
    OperationalDispatchResult,
    OperationalVerificationResult,
    OperationalVerificationStatus,
)
from app.providers.loader import load_provider_registry
from app.providers.proxmox import ProxmoxProvider
from app.providers.registry import provider_registry

_PRODUCTION_LEDGER = Path("/opt/atlas/data/operational_dispatch.db")
_SUPPORTED_CONTRACT = (
    "restart-service",
    "proxmox",
    "qemu",
    "proxmox-qemu-graceful-restart-v1",
)

Verifier = Callable[
    [OperationalDispatchRequest, OperationalDispatchResult, datetime],
    Awaitable[OperationalVerificationResult],
]


class SandboxRecoveryAction(StrEnum):
    RESUMED_VERIFICATION = "resumed_read_only_verification"
    CLASSIFIED_DISPATCHING = "classified_dispatching_outcome_unknown"
    PRE_DISPATCH_NO_ACTION = "retryable_pre_dispatch_no_action"
    NO_UPID_NO_ACTION = "outcome_unknown_without_upid_no_action"
    TERMINAL_NO_ACTION = "immutable_terminal_no_action"


@dataclass(frozen=True, slots=True)
class SandboxRecoveryResult:
    action: SandboxRecoveryAction
    starting_state: OperationalLedgerState
    entry: OperationalLedgerEntry


def validate_recovery_ledger_path(path: Path) -> None:
    """Reject anything except one caller-owned mode-0600 regular ledger."""

    candidate_literal, candidate_resolved = _normalized_ledger_paths(path)
    production_literal, production_resolved = _normalized_ledger_paths(
        _PRODUCTION_LEDGER
    )
    if (
        candidate_literal == production_literal
        or candidate_resolved == production_resolved
    ):
        raise ValueError("production operational ledger is forbidden")
    try:
        metadata = path.lstat()
    except FileNotFoundError as error:
        raise FileNotFoundError("sandbox recovery ledger does not exist") from error
    if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISREG(metadata.st_mode):
        raise PermissionError("sandbox recovery ledger must be a regular file")
    if metadata.st_uid != os.getuid() or stat.S_IMODE(metadata.st_mode) != 0o600:
        raise PermissionError(
            "sandbox recovery ledger must be caller-owned with mode 0600"
        )


def _normalized_ledger_paths(path: Path) -> tuple[Path, Path]:
    """Return comparable lexical and symlink-resolved absolute paths."""

    lexical = Path(os.path.abspath(path))
    return lexical, lexical.resolve(strict=False)


def load_recovery_request(path: Path) -> OperationalDispatchRequest:
    metadata = path.stat()
    if metadata.st_uid != os.getuid() or stat.S_IMODE(metadata.st_mode) != 0o400:
        raise PermissionError("sandbox recovery request must be caller-owned with mode 0400")
    return OperationalDispatchRequest.model_validate_json(path.read_bytes())


def validate_recovery_request(
    request: OperationalDispatchRequest,
    entry: OperationalLedgerEntry | None,
) -> OperationalLedgerEntry:
    if entry is None:
        raise ValueError("sandbox recovery request is absent from ledger")
    if entry.request_id != request.request_id or entry.request_digest != request.request_digest:
        raise ValueError("sandbox recovery request identity does not match ledger")
    if entry.request != request:
        raise ValueError("sandbox recovery request payload does not match ledger")
    contract = (
        request.execution_intent,
        request.provider_id,
        request.resource_type,
        request.provider_action_id,
    )
    if contract != _SUPPORTED_CONTRACT or not request.target_fingerprint:
        raise ValueError("sandbox recovery request contract is unsupported")
    return entry


async def recover_sandbox_entry(
    *,
    ledger: OperationalDispatchLedger,
    request: OperationalDispatchRequest,
    verifier: Verifier,
) -> SandboxRecoveryResult:
    entry = validate_recovery_request(request, ledger.get(request.request_id))
    starting_state = entry.state

    if entry.verification_result is not None or entry.state in FINAL_STATES:
        return SandboxRecoveryResult(
            SandboxRecoveryAction.TERMINAL_NO_ACTION, starting_state, entry
        )
    if entry.state in {
        OperationalLedgerState.CLAIMED,
        OperationalLedgerState.REVALIDATED,
    }:
        return SandboxRecoveryResult(
            SandboxRecoveryAction.PRE_DISPATCH_NO_ACTION, starting_state, entry
        )
    if entry.state is OperationalLedgerState.DISPATCHING:
        ledger.reconcile_startup()
        entry = validate_recovery_request(request, ledger.get(request.request_id))
        return SandboxRecoveryResult(
            SandboxRecoveryAction.CLASSIFIED_DISPATCHING, starting_state, entry
        )
    if entry.state is OperationalLedgerState.FAILED:
        raise ValueError("failed dispatch is not recoverable")
    if entry.dispatch_result is None:
        raise ValueError("recoverable state is missing a dispatch result")
    if entry.dispatch_result.provider_operation_id is None:
        if entry.state is not OperationalLedgerState.OUTCOME_UNKNOWN:
            raise ValueError("recoverable state is missing a provider operation ID")
        return SandboxRecoveryResult(
            SandboxRecoveryAction.NO_UPID_NO_ACTION, starting_state, entry
        )
    if entry.state not in {
        OperationalLedgerState.SUCCEEDED,
        OperationalLedgerState.OUTCOME_UNKNOWN,
        OperationalLedgerState.VERIFYING,
    }:
        raise ValueError("sandbox ledger record is not verification-resumable")

    _, owner = ledger.begin_verification(
        request,
        resume_interrupted=entry.state is OperationalLedgerState.VERIFYING,
    )
    if not owner:
        raise ValueError("sandbox verification recovery ownership was not acquired")
    _append_audit(ledger, request, OperationalDispatchAuditStatus.VERIFICATION_RESUMED)
    _append_audit(ledger, request, OperationalDispatchAuditStatus.RECOVERY_RECONCILED)
    try:
        verification = await verifier(
            request,
            entry.dispatch_result,
            request.expires_at,
        )
    except Exception:  # noqa: BLE001 - recovery remains sanitized and fail-closed
        now = datetime.now(UTC)
        verification = OperationalVerificationResult(
            status=OperationalVerificationStatus.OUTCOME_UNKNOWN,
            request_id=request.request_id,
            started_at=entry.dispatch_result.started_at,
            completed_at=now,
            deadline=request.expires_at,
        )
    persisted = ledger.persist_verification_result(request, verification)
    _append_audit(ledger, request, _audit_status(verification.status))
    return SandboxRecoveryResult(
        SandboxRecoveryAction.RESUMED_VERIFICATION,
        starting_state,
        persisted,
    )


def print_recovery_evidence(
    *,
    ledger: OperationalDispatchLedger,
    request: OperationalDispatchRequest,
    starting_state: OperationalLedgerState,
    action: SandboxRecoveryAction,
    before_count: int,
) -> None:
    entry = validate_recovery_request(request, ledger.get(request.request_id))
    print(f"sandbox ledger path: {ledger.database_path}")
    print(f"request ID: {request.request_id}")
    print(f"request digest: {request.request_digest}")
    print(f"starting ledger state: {starting_state.value}")
    print(f"persisted provider operation ID: {_sanitized_upid(entry.dispatch_result)}")
    print(f"verification resumable: {action is SandboxRecoveryAction.RESUMED_VERIFICATION}")
    print("ordered transitions before recovery:")
    transitions = ledger.list_transitions(request.request_id)
    for transition in transitions[:before_count]:
        _print_transition(transition)
    print(f"recovery action: {action.value}")
    print("ordered transitions after recovery:")
    for transition in transitions:
        _print_transition(transition)
    verification = entry.verification_result
    print(
        "terminal verification result: "
        + (verification.status.value if verification is not None else "none")
    )
    print("sanitized operational audit events:")
    for event in reversed(ledger.list_events(limit=1000)):
        if event.request_id == request.request_id:
            print(f"  {event.status.value} at {event.occurred_at.isoformat()}")


async def _run(args: argparse.Namespace) -> int:
    validate_recovery_ledger_path(args.ledger)
    request = load_recovery_request(args.request_file)
    ledger = OperationalDispatchLedger(args.ledger)
    entry = validate_recovery_request(request, ledger.get(request.request_id))
    before_count = len(ledger.list_transitions(request.request_id))
    load_provider_registry()
    provider = provider_registry.get("proxmox")
    if not isinstance(provider, ProxmoxProvider):
        raise TypeError("Proxmox provider is unavailable")

    # Imported only in the CLI construction seam; no mutation handler is imported.
    from app.providers.proxmox_operational import ProxmoxQemuVerificationService

    verification_service = ProxmoxQemuVerificationService(provider.atlas_context)

    async def verify(
        approved_request: OperationalDispatchRequest,
        dispatch_result: OperationalDispatchResult,
        deadline: datetime,
    ) -> OperationalVerificationResult:
        return await verification_service.verify(
            approved_request,
            dispatch_result,
            deadline=deadline,
        )

    result = await recover_sandbox_entry(
        ledger=ledger,
        request=request,
        verifier=verify,
    )
    print_recovery_evidence(
        ledger=ledger,
        request=request,
        starting_state=entry.state,
        action=result.action,
        before_count=before_count,
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--request-file", type=Path, required=True)
    parser.add_argument("--ledger", type=Path, required=True)
    return asyncio.run(_run(parser.parse_args()))


def _append_audit(
    ledger: OperationalDispatchLedger,
    request: OperationalDispatchRequest,
    status: OperationalDispatchAuditStatus,
) -> None:
    ledger.append_event(
        OperationalDispatchAuditEvent(
            event_id=uuid4().hex,
            status=status,
            occurred_at=datetime.now(UTC),
            request_id=request.request_id,
            request_digest=request.request_digest,
            workflow_session_id=request.workflow_session_id,
            candidate_planning_session_id=request.candidate_planning_session_id,
            candidate_id=request.candidate_id,
            candidate_plan_id=request.candidate_plan_id,
            provider_id=request.provider_id,
            resource_id=request.resource_id,
            resource_type=request.resource_type,
            target_fingerprint=request.target_fingerprint,
        )
    )


def _audit_status(
    status: OperationalVerificationStatus,
) -> OperationalDispatchAuditStatus:
    return {
        OperationalVerificationStatus.SUCCEEDED: OperationalDispatchAuditStatus.VERIFICATION_SUCCEEDED,
        OperationalVerificationStatus.VERIFICATION_FAILED: OperationalDispatchAuditStatus.VERIFICATION_FAILED,
        OperationalVerificationStatus.OUTCOME_UNKNOWN: OperationalDispatchAuditStatus.OUTCOME_UNKNOWN,
        OperationalVerificationStatus.TARGET_REPLACED: OperationalDispatchAuditStatus.VERIFICATION_TARGET_REPLACED,
    }[status]


def _sanitized_upid(result: OperationalDispatchResult | None) -> str:
    if result is None or result.provider_operation_id is None:
        return "none"
    parts = result.provider_operation_id.split(":")
    if len(parts) >= 9:
        parts[-2] = "[principal-redacted]"
        return ":".join(parts)
    return "present-invalid-format"


def _print_transition(transition) -> None:
    previous = transition.previous_state.value if transition.previous_state else "initial"
    print(
        f"  {transition.sequence}: {previous} -> {transition.state.value} "
        f"at {transition.occurred_at.isoformat()}"
    )


if __name__ == "__main__":
    raise SystemExit(main())
