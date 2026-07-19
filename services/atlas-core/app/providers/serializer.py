from app.providers import Provider, ProviderAction


def serialize_action(action: ProviderAction) -> dict:
    """Convert a provider action into its public API representation."""

    return action.model_dump()


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
