from app.config.inventory import load_inventory
from app.providers.inventory_provider import InventoryServiceProvider
from app.providers.registry import provider_registry


def load_provider_registry():
    """Populate the registry from inventory."""

    provider_registry.clear()

    inventory = load_inventory()

    for service_id, service in inventory.get(
        "services",
        {},
    ).items():
        provider_registry.register(
            InventoryServiceProvider(
                service_id,
                service,
            )
        )

    return provider_registry
