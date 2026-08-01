from __future__ import annotations

from collections.abc import Iterable

from app.config.inventory import load_inventory
from app.context import AtlasContext
from app.providers.base import Provider
from app.providers.factory import (
    ProviderFactoryRegistry,
    default_provider_factory_registry,
    provider_type_from_context,
)
from app.providers.registry import ProviderRegistry, provider_registry
from app.services.atlas_contexts import LegacyAtlasContextResolver


def build_providers_from_contexts(
    contexts: Iterable[AtlasContext],
    factory_registry: ProviderFactoryRegistry | None = None,
) -> list[Provider]:
    """Build provider instances from already resolved Atlas contexts."""

    factories = factory_registry or default_provider_factory_registry()
    providers: list[Provider] = []
    for atlas_context in contexts:
        provider_type = provider_type_from_context(atlas_context)
        factory = factories.get(provider_type)
        provider = factory.build(atlas_context)
        provider.atlas_context = atlas_context  # type: ignore[attr-defined]
        providers.append(provider)
    return providers


def load_provider_registry(
    registry: ProviderRegistry | None = None,
    context_resolver: LegacyAtlasContextResolver | None = None,
    factory_registry: ProviderFactoryRegistry | None = None,
) -> ProviderRegistry:
    """Populate the registry from resolved Atlas contexts atomically."""

    target_registry = provider_registry if registry is None else registry
    resolver = context_resolver or LegacyAtlasContextResolver(
        inventory=load_inventory(),
    )
    contexts = resolver.resolve_all_contexts()
    providers = build_providers_from_contexts(
        contexts,
        factory_registry=factory_registry,
    )
    target_registry.replace_all(providers)
    return target_registry
