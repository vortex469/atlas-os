from __future__ import annotations

from datetime import datetime, timezone
from time import perf_counter
from typing import TYPE_CHECKING
from uuid import uuid4

from app.actions.exceptions import (
    ProviderActionConfirmationRequiredError,
    ProviderActionDisabledError,
    ProviderActionNotFoundError,
)
from app.actions.models import (
    ProviderActionAuditEntry,
    ProviderActionRequest,
    ProviderActionResult,
)
from app.actions.history import provider_action_history
from app.providers.models import ProviderAction

if TYPE_CHECKING:
    from app.providers.base import Provider


async def find_provider_action(
    provider: Provider,
    action_id: str,
) -> ProviderAction:
    """Resolve an action from the provider's advertised actions."""

    actions = await provider.get_actions()

    for action in actions:
        if action.id == action_id:
            return action

    raise ProviderActionNotFoundError(
        provider_id=provider.metadata.id,
        action_id=action_id,
    )


async def execute_provider_action(
    provider: Provider,
    action_id: str,
    request: ProviderActionRequest,
    request_id: str | None = None,
) -> ProviderActionResult:
    """Validate and execute a provider action through one safe path."""

    action = await find_provider_action(provider, action_id)

    if not action.enabled:
        raise ProviderActionDisabledError(
            provider_id=provider.metadata.id,
            action_id=action.id,
        )

    if action.requires_confirmation and not request.confirmed:
        raise ProviderActionConfirmationRequiredError(
            provider_id=provider.metadata.id,
            action_id=action.id,
        )

    started_at = datetime.now(timezone.utc)
    started_timer = perf_counter()

    try:
        result = await provider.execute_action(
            action_id=action.id,
            parameters=request.parameters,
        )
    except Exception:
        completed_at = datetime.now(timezone.utc)
        provider_action_history.append(
            ProviderActionAuditEntry(
                id=uuid4().hex,
                provider_id=provider.metadata.id,
                provider_name=provider.metadata.name,
                action_id=action.id,
                action_label=action.label,
                status="failed",
                success=False,
                message="Action execution raised an exception.",
                confirmed=request.confirmed,
                destructive=action.destructive,
                parameter_names=sorted(request.parameters),
                request_id=request_id,
                started_at=started_at,
                completed_at=completed_at,
                duration_ms=round(
                    (perf_counter() - started_timer) * 1000,
                    2,
                ),
            ),
        )
        raise

    completed_at = datetime.now(timezone.utc)
    provider_action_history.append(
        ProviderActionAuditEntry(
            id=uuid4().hex,
            provider_id=provider.metadata.id,
            provider_name=provider.metadata.name,
            action_id=action.id,
            action_label=action.label,
            status=result.status,
            success=result.success,
            message=result.message,
            confirmed=request.confirmed,
            destructive=action.destructive,
            parameter_names=sorted(request.parameters),
            request_id=request_id,
            started_at=started_at,
            completed_at=completed_at,
            duration_ms=round(
                (perf_counter() - started_timer) * 1000,
                2,
            ),
        ),
    )

    return result
