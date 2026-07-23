from app.actions.models import ProviderActionResult
from app.providers import Provider, ProviderAction


def serialize_action(action: ProviderAction) -> dict:
    """Convert a provider action into its public API representation."""

    return action.model_dump()


def serialize_action_result(result: ProviderActionResult) -> dict:
    """Convert an action result into its public API representation."""

    return result.model_dump(mode="json")


async def serialize_provider(provider: Provider) -> dict:
    """Convert a provider and its current health into an API response."""

    health = await provider.get_health()

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
