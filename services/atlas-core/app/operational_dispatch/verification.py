"""Bounded read-only operational verification framework."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import UTC, datetime

from app.operational_dispatch.models import (
    OperationalDispatchRequest,
    OperationalVerificationResult,
    OperationalVerificationStatus,
)
from app.providers import ProviderNotFoundError
from app.services.provider_resources import (
    OperationalTargetResolutionError,
    ProviderResourceOperationError,
    ProviderResourcesNotSupportedError,
    ResolvedOperationalTarget,
    resolve_operational_target,
)

TargetResolver = Callable[[str, str, str], Awaitable[ResolvedOperationalTarget]]


class OperationalVerificationService:
    """Observe exact current identity without invoking any mutation."""

    def __init__(self, *, resolver: TargetResolver = resolve_operational_target) -> None:
        self._resolver = resolver

    async def verify(
        self,
        request: OperationalDispatchRequest,
        *,
        started_at: datetime,
        deadline: datetime,
    ) -> OperationalVerificationResult:
        now = datetime.now(UTC)
        if deadline <= started_at:
            raise ValueError("verification deadline must follow start")
        if now >= deadline:
            return OperationalVerificationResult(
                status=OperationalVerificationStatus.OUTCOME_UNKNOWN,
                request_id=request.request_id,
                started_at=started_at,
                completed_at=now,
                deadline=deadline,
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
            return OperationalVerificationResult(
                status=OperationalVerificationStatus.TARGET_REPLACED,
                request_id=request.request_id,
                started_at=started_at,
                completed_at=datetime.now(UTC),
                deadline=deadline,
            )
        except ProviderResourceOperationError:
            return OperationalVerificationResult(
                status=OperationalVerificationStatus.OUTCOME_UNKNOWN,
                request_id=request.request_id,
                started_at=started_at,
                completed_at=datetime.now(UTC),
                deadline=deadline,
            )
        if target.resource_fingerprint != request.target_fingerprint:
            status = OperationalVerificationStatus.TARGET_REPLACED
        else:
            # P1.3b has no provider-specific success policy. Preserve the exact
            # observation without claiming the requested post-state was proven.
            status = OperationalVerificationStatus.OUTCOME_UNKNOWN
        return OperationalVerificationResult(
            status=status,
            request_id=request.request_id,
            observed_target_fingerprint=target.resource_fingerprint,
            observed_state=target.resource.current_state,
            health_status=target.resource.current_state,
            started_at=started_at,
            completed_at=datetime.now(UTC),
            deadline=deadline,
        )
