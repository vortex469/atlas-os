from __future__ import annotations

from typing import TYPE_CHECKING

from app.actions.exceptions import (
    ProviderActionConfirmationRequiredError,
    ProviderActionDisabledError,
    ProviderActionNotFoundError,
)
from app.actions.models import (
    ProviderActionRequest,
    ProviderActionResult,
)
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

    return await provider.execute_action(
        action_id=action.id,
        parameters=request.parameters,
    )
