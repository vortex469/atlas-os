from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any, Protocol, runtime_checkable

from app.context import AtlasContext
from app.providers.base import Provider
from app.providers.frigate import FrigateProvider
from app.providers.homeassistant import HomeAssistantProvider
from app.providers.inventory_provider import InventoryServiceProvider
from app.providers.n8n import N8nProvider
from app.providers.obsidian import ObsidianProvider
from app.providers.ollama import OllamaProvider
from app.providers.opnsense import OPNsenseProvider
from app.providers.proxmox import ProxmoxProvider
from app.providers.qdrant import QdrantProvider


class ProviderFactoryNotFoundError(KeyError):
    """Raised when no provider factory can build a provider type."""


@runtime_checkable
class ContextAwareProvider(Protocol):
    """Optional protocol for providers backed by immutable AtlasContext."""

    @property
    def atlas_context(self) -> AtlasContext:
        """Return the immutable AtlasContext used to construct the provider."""


@runtime_checkable
class ProviderFactory(Protocol):
    """Build a provider from an immutable AtlasContext."""

    provider_type: str

    def build(self, atlas_context: AtlasContext) -> Provider:
        """Return a provider initialized from AtlasContext."""


class LegacyProviderFactory:
    """Factory that preserves existing provider constructor behavior."""

    def __init__(
        self,
        provider_type: str,
        builder: Callable[[AtlasContext, Mapping[str, Any]], Provider],
    ) -> None:
        self.provider_type = provider_type
        self._builder = builder

    def build(self, atlas_context: AtlasContext) -> Provider:
        service = legacy_service_from_context(atlas_context)
        provider = self._builder(atlas_context, service)
        provider.atlas_context = atlas_context  # type: ignore[attr-defined]
        return provider


class ProviderFactoryRegistry:
    """Registry of factories keyed by Atlas provider type."""

    def __init__(
        self,
        factories: Mapping[str, ProviderFactory] | None = None,
        fallback_factory: ProviderFactory | None = None,
    ) -> None:
        self._factories = dict(factories or {})
        self._fallback_factory = fallback_factory

    def get(self, provider_type: str) -> ProviderFactory:
        factory = self._factories.get(provider_type)
        if factory is not None:
            return factory
        if self._fallback_factory is not None:
            return self._fallback_factory
        raise ProviderFactoryNotFoundError(
            f"No provider factory is registered for '{provider_type}'.",
        )

    def register(self, factory: ProviderFactory) -> None:
        self._factories[factory.provider_type] = factory


def provider_type_from_context(atlas_context: AtlasContext) -> str:
    provider_type = atlas_context.metadata.metadata.get("provider_type")
    if isinstance(provider_type, str) and provider_type:
        return provider_type
    return atlas_context.consumer_id


def legacy_service_from_context(
    atlas_context: AtlasContext,
) -> Mapping[str, Any]:
    service = atlas_context.metadata.metadata.get("legacy_service")
    if isinstance(service, Mapping):
        return service
    return {}


def default_provider_factory_registry() -> ProviderFactoryRegistry:
    inventory_factory = LegacyProviderFactory(
        "inventory",
        lambda context, service: InventoryServiceProvider(
            context.consumer_id,
            context,
        ),
    )
    factories: dict[str, ProviderFactory] = {
        "frigate": LegacyProviderFactory(
            "frigate",
            lambda context, service: FrigateProvider(context),
        ),
        "home_assistant": LegacyProviderFactory(
            "home_assistant",
            lambda context, service: HomeAssistantProvider(context),
        ),
        "n8n": LegacyProviderFactory(
            "n8n",
            lambda context, service: N8nProvider(context),
        ),
        "obsidian": LegacyProviderFactory(
            "obsidian",
            lambda context, service: ObsidianProvider(context),
        ),
        "ollama": LegacyProviderFactory(
            "ollama",
            lambda context, service: OllamaProvider(context),
        ),
        "opnsense": LegacyProviderFactory(
            "opnsense",
            lambda context, service: OPNsenseProvider(context),
        ),
        "proxmox": LegacyProviderFactory(
            "proxmox",
            lambda context, service: ProxmoxProvider(context),
        ),
        "qdrant": LegacyProviderFactory(
            "qdrant",
            lambda context, service: QdrantProvider(context),
        ),
        "inventory": inventory_factory,
    }
    return ProviderFactoryRegistry(
        factories=factories,
        fallback_factory=inventory_factory,
    )
