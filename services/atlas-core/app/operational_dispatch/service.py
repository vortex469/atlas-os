"""Fail-closed Core operational dispatch trust boundary."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from uuid import uuid4

from app.operational_dispatch.ledger import (
    OperationalDispatchLedger,
    OperationalLedgerState,
)
from app.operational_dispatch.models import (
    OperationalDispatchAuditEvent,
    OperationalDispatchAuditStatus,
    OperationalDispatchRequest,
    OperationalDispatchResult,
    OperationalDispatchStatus,
)
from app.operational_dispatch.registry import (
    OPERATIONAL_EXECUTION_INTENTS,
    OperationalHandlerRegistry,
    production_operational_handler_registry,
)
from app.providers import ProviderNotFoundError
from app.services.provider_resource_identity import (
    OperationalTargetResolutionError,
    ProviderResourceOperationError,
    ProviderResourcesNotSupportedError,
    ResolvedOperationalTarget,
    resolve_operational_target,
)

TargetResolver = Callable[[str, str, str], Awaitable[ResolvedOperationalTarget]]


class OperationalDispatchService:
    """Claim, revalidate, and stop unless both independent gates authorize."""

    def __init__(
        self,
        *,
        ledger: OperationalDispatchLedger,
        registry: OperationalHandlerRegistry = production_operational_handler_registry,
        execution_intents: frozenset[str] = OPERATIONAL_EXECUTION_INTENTS,
        resolver: TargetResolver = resolve_operational_target,
    ) -> None:
        self._ledger = ledger
        self._registry = registry
        self._execution_intents = execution_intents
        self._resolver = resolver

    def capability_boundary(
        self, execution_intent: str, provider_id: str, resource_type: str
    ) -> tuple[bool, bool]:
        """Describe independent Core gates without granting or registering anything."""

        return (
            execution_intent in self._execution_intents,
            self._registry.resolve(execution_intent, provider_id, resource_type)
            is not None,
        )

    async def dispatch(
        self, request: OperationalDispatchRequest
    ) -> OperationalDispatchResult:
        entry = self._ledger.claim(request)
        if entry.dispatch_result is not None:
            return entry.dispatch_result
        now = datetime.now(UTC)
        if request.expires_at <= now:
            return self._terminal_failure(request, now, "Operational request expired.")
        handler = self._registry.resolve(
            request.execution_intent,
            request.provider_id,
            request.resource_type,
        )
        if request.execution_intent not in self._execution_intents:
            self._audit(request, OperationalDispatchAuditStatus.EXECUTION_DISABLED)
            return self._terminal_failure(
                request, now, "Operational execution capability is disabled."
            )
        if handler is None:
            self._audit(request, OperationalDispatchAuditStatus.NO_HANDLER)
            return self._terminal_failure(
                request, now, "No exact operational handler is registered."
            )

        try:
            target = await self._resolver(
                request.provider_id,
                request.resource_id,
                request.resource_type,
            )
        except (
            OperationalTargetResolutionError,
            ProviderNotFoundError,
            ProviderResourcesNotSupportedError,
        ):
            self._audit(request, OperationalDispatchAuditStatus.TARGET_BLOCKED)
            return self._target_replaced(request, now)
        except ProviderResourceOperationError:
            # The durable claim remains pre-dispatch and may be retried safely.
            self._audit(request, OperationalDispatchAuditStatus.TARGET_BLOCKED)
            return OperationalDispatchResult(
                status=OperationalDispatchStatus.FAILED,
                request_id=request.request_id,
                request_digest=request.request_digest,
                target_fingerprint=request.target_fingerprint,
                started_at=now,
                completed_at=datetime.now(UTC),
                sanitized_message="Operational target is temporarily unavailable.",
            )
        if not self._target_matches(request, target):
            self._audit(request, OperationalDispatchAuditStatus.TARGET_BLOCKED)
            return self._target_replaced(request, now)

        self._ledger.mark_revalidated(request)
        entry, owner = self._ledger.mark_dispatching(request)
        if not owner:
            if entry.dispatch_result is not None:
                return entry.dispatch_result
            return OperationalDispatchResult(
                status=OperationalDispatchStatus.OUTCOME_UNKNOWN,
                request_id=request.request_id,
                request_digest=request.request_digest,
                target_fingerprint=request.target_fingerprint,
                started_at=entry.dispatch_started_at or now,
                sanitized_message="Operational dispatch is already in progress.",
            )
        self._audit(request, OperationalDispatchAuditStatus.BARRIER_CROSSED)
        try:
            result = await handler(request, target)
            if (
                result.request_id != request.request_id
                or result.request_digest != request.request_digest
                or result.target_fingerprint != request.target_fingerprint
            ):
                raise ValueError("operational handler result identity mismatch")
        except Exception:  # noqa: BLE001 - any post-barrier failure is ambiguous
            result = OperationalDispatchResult(
                status=OperationalDispatchStatus.OUTCOME_UNKNOWN,
                request_id=request.request_id,
                request_digest=request.request_digest,
                target_fingerprint=request.target_fingerprint,
                started_at=entry.dispatch_started_at or now,
                completed_at=datetime.now(UTC),
                sanitized_message="Operational dispatch outcome is unknown.",
            )
        state = (
            OperationalLedgerState.SUCCEEDED
            if result.status is OperationalDispatchStatus.SUCCEEDED
            else OperationalLedgerState.FAILED
            if result.status is OperationalDispatchStatus.FAILED
            else OperationalLedgerState.OUTCOME_UNKNOWN
        )
        if result.provider_operation_id is not None:
            self._audit(
                request, OperationalDispatchAuditStatus.PROVIDER_OPERATION_CAPTURED
            )
        if result.status is OperationalDispatchStatus.OUTCOME_UNKNOWN:
            self._audit(request, OperationalDispatchAuditStatus.OUTCOME_UNKNOWN)
        self._audit(request, OperationalDispatchAuditStatus.DISPATCH_RESULT)
        return self._ledger.persist_dispatch_result(
            request, result, state=state
        ).dispatch_result  # type: ignore[return-value]

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
    def _target_matches(
        request: OperationalDispatchRequest,
        target: ResolvedOperationalTarget,
    ) -> bool:
        resource_version = (
            target.resource.identity.token_version
            if target.resource.identity is not None
            else None
        )
        return (
            target.provider.id == request.provider_id
            and target.resource.provider_id == request.provider_id
            and target.resource.resource_id == request.resource_id
            and target.resource.resource_type == request.resource_type
            and target.resource_fingerprint == request.target_fingerprint
            and (
                request.target_version is None
                or resource_version == request.target_version
            )
        )

    def _terminal_failure(
        self,
        request: OperationalDispatchRequest,
        started_at: datetime,
        message: str,
    ) -> OperationalDispatchResult:
        result = OperationalDispatchResult(
            status=OperationalDispatchStatus.FAILED,
            request_id=request.request_id,
            request_digest=request.request_digest,
            target_fingerprint=request.target_fingerprint,
            started_at=started_at,
            completed_at=datetime.now(UTC),
            sanitized_message=message,
        )
        return self._ledger.persist_dispatch_result(
            request, result, state=OperationalLedgerState.FAILED
        ).dispatch_result  # type: ignore[return-value]

    def _target_replaced(
        self, request: OperationalDispatchRequest, started_at: datetime
    ) -> OperationalDispatchResult:
        result = OperationalDispatchResult(
            status=OperationalDispatchStatus.FAILED,
            request_id=request.request_id,
            request_digest=request.request_digest,
            target_fingerprint=request.target_fingerprint,
            started_at=started_at,
            completed_at=datetime.now(UTC),
            sanitized_message="Authoritative operational target was replaced or unavailable.",
        )
        return self._ledger.persist_dispatch_result(
            request, result, state=OperationalLedgerState.TARGET_REPLACED
        ).dispatch_result  # type: ignore[return-value]
