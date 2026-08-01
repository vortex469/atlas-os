from __future__ import annotations

import pytest

from app.context import (
    AtlasContext,
    ConnectionContext,
    MetadataContext,
    RuntimeContext,
    SecretContext,
)
from app.providers import (
    Provider,
    ProviderCapability,
    ProviderHealth,
    ProviderMetadata,
    ProviderPriority,
    ProviderWorkspace,
)
from app.providers.factory import (
    ProviderFactoryNotFoundError,
    ProviderFactoryRegistry,
)
from app.providers.frigate import FrigateProvider
from app.providers.inventory_provider import InventoryServiceProvider
from app.providers.loader import build_providers_from_contexts, load_provider_registry
from app.providers.n8n import N8nProvider
from app.providers.obsidian import ObsidianProvider
from app.providers.ollama import OllamaProvider
from app.providers.opnsense import OPNsenseProvider
from app.providers.proxmox import ProxmoxProvider
from app.providers.qdrant import QdrantProvider
from app.providers.registry import ProviderRegistry


class RecordingResolver:
    def __init__(self, contexts: tuple[AtlasContext, ...]) -> None:
        self.contexts = contexts
        self.resolved = False

    def resolve_all_contexts(self) -> tuple[AtlasContext, ...]:
        self.resolved = True
        return self.contexts


class RecordingFactory:
    provider_type = "recording"

    def __init__(self) -> None:
        self.contexts: list[AtlasContext] = []

    def build(self, atlas_context: AtlasContext) -> Provider:
        self.contexts.append(atlas_context)
        return MockProvider(
            provider_id=atlas_context.consumer_id,
            name=atlas_context.metadata.name,
        )


class FailingFactory:
    provider_type = "recording"

    def build(self, atlas_context: AtlasContext) -> Provider:
        raise RuntimeError(f"Cannot build {atlas_context.consumer_id}.")


class MockProvider(Provider):
    def __init__(
        self,
        provider_id: str,
        name: str = "Mock Provider",
    ) -> None:
        self._metadata = ProviderMetadata(
            id=provider_id,
            name=name,
            version="1.0.0",
            description="Provider used by loader tests.",
            workspace=ProviderWorkspace.OPERATIONS,
            icon="test-tube",
            priority=ProviderPriority.NORMAL,
            capabilities=frozenset({ProviderCapability.HEALTH}),
        )

    @property
    def metadata(self) -> ProviderMetadata:
        return self._metadata

    async def get_health(self) -> ProviderHealth:
        return ProviderHealth(status="online")


def atlas_context(
    consumer_id: str,
    *,
    provider_type: str = "recording",
    service: dict | None = None,
    name: str | None = None,
) -> AtlasContext:
    return AtlasContext(
        metadata=MetadataContext(
            consumer_id=consumer_id,
            consumer_type="provider",
            name=name or consumer_id.title(),
            metadata={
                "provider_type": provider_type,
                "legacy_service": service or {"name": name or consumer_id.title()},
            },
        ),
        runtime=RuntimeContext(),
        generation=f"generation-{consumer_id}",
    )


def http_atlas_context(
    consumer_id: str,
    *,
    provider_type: str,
    port: int,
    secrets: dict[str, str] | None = None,
    path: str | None = None,
) -> AtlasContext:
    return AtlasContext(
        metadata=MetadataContext(
            consumer_id=consumer_id,
            consumer_type="provider",
            name=f"Context {consumer_id}",
            metadata={
                "provider_type": provider_type,
                "legacy_service": {
                    "name": f"Legacy {consumer_id}",
                    "host": "legacy.local",
                    "port": 1,
                },
            },
        ),
        connection=ConnectionContext(
            mode="https",
            host=f"{consumer_id}.context.local",
            port=port,
            path=path,
            health_endpoint="/ready",
            expected_status=204,
            verify_tls=False,
            source="runtime",
            metadata={"expected_statuses": (204, 418)},
        ),
        secrets={
            name: SecretContext(
                name=name,
                source="runtime",
                configured=True,
                redacted="********",
                value=value,
            )
            for name, value in (secrets or {}).items()
        },
        runtime=RuntimeContext(),
        generation=f"generation-{consumer_id}",
    )


def test_loader_resolves_contexts_before_constructing_providers() -> None:
    context = atlas_context("alpha")
    resolver = RecordingResolver((context,))
    factory = RecordingFactory()
    registry = ProviderRegistry()

    load_provider_registry(
        registry=registry,
        context_resolver=resolver,  # type: ignore[arg-type]
        factory_registry=ProviderFactoryRegistry({"recording": factory}),
    )

    assert resolver.resolved is True
    assert factory.contexts == [context]
    assert registry.get("alpha").metadata.name == "Alpha"


def test_factory_selected_by_provider_type() -> None:
    context = atlas_context("alpha", provider_type="recording")
    factory = RecordingFactory()

    providers = build_providers_from_contexts(
        (context,),
        factory_registry=ProviderFactoryRegistry({"recording": factory}),
    )

    assert len(providers) == 1
    assert providers[0].metadata.id == "alpha"
    assert factory.contexts == [context]


def test_unknown_provider_type_uses_documented_inventory_fallback() -> None:
    context = atlas_context(
        "custom-service",
        provider_type="not-registered",
        service={
            "name": "Custom Service",
            "host": "10.0.0.1",
            "port": 8080,
            "protocol": "http",
            "health_endpoint": "/health",
            "expected_status": [200],
            "critical": False,
        },
    )

    provider = build_providers_from_contexts((context,))[0]

    assert isinstance(provider, InventoryServiceProvider)
    assert provider.metadata.id == "custom-service"
    assert provider.atlas_context is context  # type: ignore[attr-defined]


def test_provider_receives_expected_atlas_context() -> None:
    context = atlas_context("alpha")
    provider = build_providers_from_contexts(
        (context,),
        factory_registry=ProviderFactoryRegistry({"recording": RecordingFactory()}),
    )[0]

    assert provider.atlas_context is context  # type: ignore[attr-defined]


def test_context_metadata_wins_and_legacy_data_remains_available_for_proxmox() -> None:
    context = atlas_context(
        "proxmox",
        provider_type="proxmox",
        service={
            "name": "Proxmox Legacy",
            "description": "Legacy constructor data.",
            "critical": True,
        },
    )

    provider = build_providers_from_contexts((context,))[0]

    assert isinstance(provider, ProxmoxProvider)
    assert provider.metadata.name == "Proxmox"
    assert provider.metadata.description == (
        "Virtualization provider for Proxmox guests."
    )
    assert provider.atlas_context.metadata.metadata["legacy_service"]["name"] == (
        "Proxmox Legacy"
    )
    assert provider.atlas_context is context  # type: ignore[attr-defined]


def test_http_provider_factories_pass_atlas_context_and_context_values() -> None:
    contexts = (
        http_atlas_context(
            "opnsense",
            provider_type="opnsense",
            port=8443,
            secrets={"api_key": "opn-key", "api_secret": "opn-secret"},
        ),
        http_atlas_context(
            "frigate",
            provider_type="frigate",
            port=8971,
            secrets={"api_token": "frigate-token"},
        ),
        http_atlas_context(
            "n8n",
            provider_type="n8n",
            port=5678,
            secrets={"api_key": "n8n-key"},
        ),
        http_atlas_context(
            "qdrant",
            provider_type="qdrant",
            port=6333,
            secrets={"api_key": "qdrant-key"},
        ),
        http_atlas_context("ollama", provider_type="ollama", port=11434),
        http_atlas_context(
            "obsidian",
            provider_type="obsidian",
            port=1,
            path="/vault/context",
        ),
        http_atlas_context("grafana", provider_type="inventory", port=3000),
    )

    providers = build_providers_from_contexts(contexts)
    providers_by_id = {provider.metadata.id: provider for provider in providers}

    assert isinstance(providers_by_id["opnsense"], OPNsenseProvider)
    assert isinstance(providers_by_id["frigate"], FrigateProvider)
    assert isinstance(providers_by_id["n8n"], N8nProvider)
    assert isinstance(providers_by_id["qdrant"], QdrantProvider)
    assert isinstance(providers_by_id["ollama"], OllamaProvider)
    assert isinstance(providers_by_id["obsidian"], ObsidianProvider)
    assert isinstance(providers_by_id["grafana"], InventoryServiceProvider)

    for context in contexts:
        provider = providers_by_id[context.consumer_id]
        assert provider.atlas_context is context  # type: ignore[attr-defined]
        assert provider.metadata.name == f"Context {context.consumer_id}"

    assert providers_by_id["opnsense"]._base_url == "https://opnsense.context.local:8443/"  # type: ignore[attr-defined]
    assert providers_by_id["frigate"]._headers()["Authorization"] == "Bearer frigate-token"  # type: ignore[attr-defined]
    assert providers_by_id["n8n"]._headers()["X-N8N-API-KEY"] == "n8n-key"  # type: ignore[attr-defined]
    assert providers_by_id["qdrant"]._headers()["api-key"] == "qdrant-key"  # type: ignore[attr-defined]
    assert providers_by_id["ollama"]._base_url == "https://ollama.context.local:11434/"  # type: ignore[attr-defined]
    assert providers_by_id["obsidian"]._vault_path.as_posix() == "/vault/context"  # type: ignore[attr-defined]
    assert providers_by_id["grafana"].atlas_context.connection.health_endpoint == "/ready"  # type: ignore[union-attr]


def test_provider_ordering_remains_deterministic_after_load() -> None:
    registry = ProviderRegistry()
    resolver = RecordingResolver(
        (
            atlas_context("developer", name="Developer"),
            atlas_context("automation", name="Automation"),
        ),
    )

    load_provider_registry(
        registry=registry,
        context_resolver=resolver,  # type: ignore[arg-type]
        factory_registry=ProviderFactoryRegistry({"recording": RecordingFactory()}),
    )

    assert [provider.metadata.id for provider in registry.all()] == [
        "automation",
        "developer",
    ]


def test_failed_provider_build_leaves_old_registry_intact() -> None:
    registry = ProviderRegistry()
    original = MockProvider("original")
    registry.register(original)

    with pytest.raises(RuntimeError, match="Cannot build"):
        load_provider_registry(
            registry=registry,
            context_resolver=RecordingResolver((atlas_context("alpha"),)),  # type: ignore[arg-type]
            factory_registry=ProviderFactoryRegistry({"recording": FailingFactory()}),
        )

    assert registry.ids() == ("original",)
    assert registry.get("original") is original


def test_factory_registry_without_fallback_raises_stable_error() -> None:
    with pytest.raises(ProviderFactoryNotFoundError, match="No provider factory"):
        ProviderFactoryRegistry().get("missing")


def test_duplicate_provider_ids_are_rejected_during_atomic_load() -> None:
    registry = ProviderRegistry()
    original = MockProvider("original")
    registry.register(original)

    with pytest.raises(Exception, match="already registered"):
        load_provider_registry(
            registry=registry,
            context_resolver=RecordingResolver(
                (
                    atlas_context("alpha"),
                    atlas_context("alpha"),
                ),
            ),  # type: ignore[arg-type]
            factory_registry=ProviderFactoryRegistry({"recording": RecordingFactory()}),
        )

    assert registry.ids() == ("original",)
