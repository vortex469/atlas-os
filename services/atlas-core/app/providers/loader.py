from app.config.inventory import load_inventory
from app.providers.frigate import FrigateProvider
from app.providers.inventory_provider import InventoryServiceProvider
from app.providers.obsidian import ObsidianProvider
from app.providers.ollama import OllamaProvider
from app.providers.opnsense import OPNsenseProvider
from app.providers.qdrant import QdrantProvider
from app.providers.registry import provider_registry


def load_provider_registry():
    """Populate the registry from inventory."""

    provider_registry.clear()

    inventory = load_inventory()

    for service_id, service in inventory.get(
        "services",
        {},
    ).items():
        if service_id == "ollama":
            provider = OllamaProvider(service)
        elif service_id == "opnsense":
            provider = OPNsenseProvider(service)
        elif service_id == "frigate":
            provider = FrigateProvider(service)
        elif service_id == "obsidian":
            provider = ObsidianProvider(service)
        elif service_id == "qdrant":
            provider = QdrantProvider(service)
        else:
            provider = InventoryServiceProvider(
                service_id,
                service,
            )

        provider_registry.register(provider)

    return provider_registry
