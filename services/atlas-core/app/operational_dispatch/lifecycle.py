"""Durable read-only verification orchestration for operational dispatch."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from uuid import uuid4

from app.operational_dispatch.ledger import (
    OperationalDispatchLedger,
    OperationalLedgerEntry,
    OperationalLedgerState,
)
from app.operational_dispatch.models import (
    OperationalDispatchAuditEvent,
    OperationalDispatchAuditStatus,
    OperationalDispatchRequest,
    OperationalDispatchResult,
    OperationalDispatchStatus,
    OperationalLifecycleStatus,
    OperationalVerificationResult,
    OperationalVerificationStatus,
)
from app.operational_dispatch.service import OperationalDispatchService

OperationalVerifier = Callable[
    [OperationalDispatchRequest, OperationalDispatchResult, datetime],
    Awaitable[OperationalVerificationResult],
]


class OperationalVerifierRegistry:
    """Exact-key read-only verifier registry, independent of execution gates."""

    def __init__(self) -> None:
        self._verifiers: dict[tuple[str, str, str], OperationalVerifier] = {}

    def register(
        self,
        *,
        execution_intent: str,
        provider_id: str,
        resource_type: str,
        verifier: OperationalVerifier,
    ) -> None:
        key = (execution_intent, provider_id, resource_type)
        if key in self._verifiers:
            raise ValueError("duplicate operational verifier registration")
        self._verifiers[key] = verifier

    def resolve(self, request: OperationalDispatchRequest) -> OperationalVerifier | None:
        return self._verifiers.get(
            (request.execution_intent, request.provider_id, request.resource_type)
        )


class OperationalLifecycleService:
    """Submit once, then schedule only durable read-only reconciliation."""

    def __init__(
        self,
        *,
        ledger: OperationalDispatchLedger,
        dispatcher: OperationalDispatchService,
        verifiers: OperationalVerifierRegistry,
    ) -> None:
        self._ledger = ledger
        self._dispatcher = dispatcher
        self._verifiers = verifiers
        self._tasks: set[asyncio.Task[OperationalLedgerEntry | None]] = set()

    async def dispatch(
        self, request: OperationalDispatchRequest
    ) -> OperationalDispatchResult:
        result = await self._dispatcher.dispatch(request)
        self.schedule_verification(request.request_id)
        return result

    def schedule_verification(self, request_id: str, *, recovery: bool = False) -> bool:
        entry = self._ledger.get(request_id)
        if entry is None or not self._eligible(entry):
            return False
        task = asyncio.create_task(
            self.reconcile(request_id, recovery=recovery),
            name=f"operational-verification-{request_id}",
        )
        self._tasks.add(task)
        task.add_done_callback(self._task_done)
        return True

    def schedule_startup_recovery(self) -> int:
        candidates = self._ledger.list_verification_candidates()
        for entry in candidates:
            self.schedule_verification(entry.request_id, recovery=True)
        return len(candidates)

    async def reconcile(
        self, request_id: str, *, recovery: bool = False
    ) -> OperationalLedgerEntry | None:
        entry = self._ledger.get(request_id)
        if entry is None or not self._eligible(entry):
            return entry
        verifier = self._verifiers.resolve(entry.request)
        if verifier is None or entry.dispatch_result is None:
            return entry
        was_verifying = entry.state is OperationalLedgerState.VERIFYING
        claimed, owner = self._ledger.begin_verification(
            entry.request,
            resume_interrupted=recovery and was_verifying,
        )
        if not owner:
            return claimed
        self._audit(
            entry.request,
            OperationalDispatchAuditStatus.VERIFICATION_RESUMED
            if recovery
            else OperationalDispatchAuditStatus.VERIFICATION_STARTED,
        )
        if recovery:
            self._audit(
                entry.request, OperationalDispatchAuditStatus.RECOVERY_RECONCILED
            )
        try:
            result = await verifier(
                entry.request,
                entry.dispatch_result,
                entry.request.expires_at,
            )
        except Exception:  # noqa: BLE001 - recovery failures remain sanitized/unknown
            now = datetime.now(UTC)
            result = OperationalVerificationResult(
                status=OperationalVerificationStatus.OUTCOME_UNKNOWN,
                request_id=entry.request_id,
                started_at=entry.dispatch_result.started_at,
                completed_at=now,
                deadline=entry.request.expires_at,
            )
        persisted = self._ledger.persist_verification_result(entry.request, result)
        self._audit(entry.request, _audit_status(result.status))
        return persisted

    def status(self, request_id: str) -> OperationalLifecycleStatus | None:
        entry = self._ledger.get(request_id)
        if entry is None:
            return None
        return OperationalLifecycleStatus(
            request_id=entry.request_id,
            request_digest=entry.request_digest,
            ledger_state=entry.state.value,
            dispatch_result=entry.dispatch_result,
            verification_result=entry.verification_result,
            verification_resumable=self._eligible(entry),
        )

    async def close(self) -> None:
        tasks = tuple(self._tasks)
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    def _task_done(self, task: asyncio.Task[OperationalLedgerEntry | None]) -> None:
        self._tasks.discard(task)
        if not task.cancelled():
            task.exception()

    def _audit(
        self,
        request: OperationalDispatchRequest,
        status: OperationalDispatchAuditStatus,
    ) -> None:
        self._ledger.append_event(
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

    @staticmethod
    def _eligible(entry: OperationalLedgerEntry) -> bool:
        return (
            entry.verification_result is None
            and entry.dispatch_result is not None
            and entry.dispatch_result.provider_operation_id is not None
            and entry.dispatch_result.status
            in {
                OperationalDispatchStatus.SUCCEEDED,
                OperationalDispatchStatus.OUTCOME_UNKNOWN,
            }
            and entry.state
            in {
                OperationalLedgerState.SUCCEEDED,
                OperationalLedgerState.OUTCOME_UNKNOWN,
                OperationalLedgerState.VERIFYING,
            }
        )


def _audit_status(
    status: OperationalVerificationStatus,
) -> OperationalDispatchAuditStatus:
    return {
        OperationalVerificationStatus.SUCCEEDED: (
            OperationalDispatchAuditStatus.VERIFICATION_SUCCEEDED
        ),
        OperationalVerificationStatus.VERIFICATION_FAILED: (
            OperationalDispatchAuditStatus.VERIFICATION_FAILED
        ),
        OperationalVerificationStatus.OUTCOME_UNKNOWN: (
            OperationalDispatchAuditStatus.OUTCOME_UNKNOWN
        ),
        OperationalVerificationStatus.TARGET_REPLACED: (
            OperationalDispatchAuditStatus.VERIFICATION_TARGET_REPLACED
        ),
    }[status]
