import asyncio

from app.actions.models import ProviderActionResult
from app.providers import Provider, ProviderAction
from app.providers.models import ProviderHealth


def serialize_action(action: ProviderAction) -> dict:
    """Convert a provider action into its public API representation."""

    return action.model_dump()


def serialize_action_result(result: ProviderActionResult) -> dict:
    """Convert an action result into its public API representation."""

    return result.model_dump(mode="json")


def _provider_health(provider: Provider) -> ProviderHealth:
    return asyncio.run(provider.get_health())


async def serialize_provider(
    provider: Provider,
    *,
    timeout_seconds: float | None = None,
) -> dict:
    """Convert a provider and its current health into an API response."""

    if timeout_seconds is None:
        health = await provider.get_health()
    else:
        try:
            health = await asyncio.wait_for(
                asyncio.to_thread(_provider_health, provider),
                timeout=timeout_seconds,
            )
        except TimeoutError:
            health = ProviderHealth(
                status="offline",
                message="Provider health check timed out.",
                details={"timeout_seconds": timeout_seconds},
            )
        except Exception as error:  # noqa: BLE001
            health = ProviderHealth(
                status="offline",
                message="Provider health check failed.",
                details={"error_type": type(error).__name__},
            )

    return {
        "id": provider.metadata.id,
        "name": provider.metadata.name,
        "workspace": provider.metadata.workspace.value,
        "priority": provider.metadata.priority.value,
        "version": provider.metadata.version,
        "description": provider.metadata.description,
        "icon": provider.metadata.icon,
        "capabilities": sorted(
            capability.value
            for capability in provider.metadata.capabilities
        ),
        "health": health.model_dump(),
    }
