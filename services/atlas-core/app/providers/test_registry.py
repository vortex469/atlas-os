import pytest

from app.providers import (
    Provider,
    ProviderAlreadyRegisteredError,
    ProviderCapability,
    ProviderHealth,
    ProviderMetadata,
    ProviderNotFoundError,
    ProviderPriority,
    ProviderRegistry,
    ProviderWorkspace,
)


class MockProvider(Provider):
    def __init__(
        self,
        provider_id: str = "mock-provider",
        name: str = "Mock Provider",
        workspace: ProviderWorkspace = ProviderWorkspace.DEVELOPER,
    ) -> None:
        self._metadata = ProviderMetadata(
            id=provider_id,
            name=name,
            version="1.0.0",
            description="Provider used by unit tests.",
            workspace=workspace,
            icon="test-tube",
            priority=ProviderPriority.NORMAL,
            capabilities=frozenset(
                {
                    ProviderCapability.HEALTH,
                    ProviderCapability.FINDINGS,
                },
            ),
        )

    @property
    def metadata(self) -> ProviderMetadata:
        return self._metadata

    async def get_health(self) -> ProviderHealth:
        return ProviderHealth(
            status="online",
            latency_ms=1,
            http_status=200,
        )


def test_register_and_lookup_provider() -> None:
    registry = ProviderRegistry()
    provider = MockProvider()

    registry.register(provider)

    assert len(registry) == 1
    assert registry.contains("mock-provider")
    assert registry.get("mock-provider") is provider


def test_duplicate_provider_id_is_rejected() -> None:
    registry = ProviderRegistry()

    registry.register(MockProvider())

    with pytest.raises(
        ProviderAlreadyRegisteredError,
        match="already registered",
    ):
        registry.register(MockProvider())


def test_unknown_provider_raises_clear_error() -> None:
    registry = ProviderRegistry()

    with pytest.raises(
        ProviderNotFoundError,
        match="not registered",
    ):
        registry.get("missing-provider")


def test_unregister_removes_provider() -> None:
    registry = ProviderRegistry()
    provider = MockProvider()

    registry.register(provider)
    removed = registry.unregister("mock-provider")

    assert removed is provider
    assert len(registry) == 0
    assert not registry.contains("mock-provider")


def test_registry_returns_stable_workspace_order() -> None:
    registry = ProviderRegistry()

    registry.register_many(
        [
            MockProvider(
                provider_id="developer-provider",
                name="Developer",
                workspace=ProviderWorkspace.DEVELOPER,
            ),
            MockProvider(
                provider_id="automation-provider",
                name="Automation",
                workspace=ProviderWorkspace.AUTOMATION,
            ),
            MockProvider(
                provider_id="operations-provider",
                name="Operations",
                workspace=ProviderWorkspace.OPERATIONS,
            ),
        ],
    )

    assert [
        provider.metadata.id
        for provider in registry.all()
    ] == [
        "automation-provider",
        "developer-provider",
        "operations-provider",
    ]


def test_provider_health_contract() -> None:
    import asyncio

    provider = MockProvider()

    health = asyncio.run(provider.get_health())

    assert health.status == "online"
    assert health.latency_ms == 1
    assert health.http_status == 200
