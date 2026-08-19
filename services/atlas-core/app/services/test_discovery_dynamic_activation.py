import asyncio
import json
import logging
from types import SimpleNamespace

from app.discovery.dynamic_cache import DiscoveryCacheStore
from app.discovery.dynamic_sources import FRIGATE_ADAPTER_ID, DynamicSourceHealth
from app.services import discovery_dynamic_activation as activation


def test_activation_initializes_refreshes_records_health_and_closes(
    monkeypatch,
) -> None:
    events: list[object] = []

    class FakeStore:
        def __init__(self, root) -> None:
            events.append(("store", root))

        def initialize(self) -> None:
            events.append("initialize")

    class FakeCoordinator:
        def __init__(self, store) -> None:
            events.append(("coordinator", store))

        async def refresh(self, *, now):
            events.append(("refresh", now))
            return SimpleNamespace(
                sources=(
                    SimpleNamespace(
                        source_id="frigate-github-latest-release-v1",
                        health=DynamicSourceHealth.DEGRADED,
                    ),
                )
            )

        async def aclose(self) -> None:
            events.append("close")

    class FakeRegistry:
        def record(self, source_id, health) -> None:
            events.append(("record", source_id, health))

    monkeypatch.setattr(activation, "DiscoveryCacheStore", FakeStore)
    monkeypatch.setattr(activation, "RefreshCoordinator", FakeCoordinator)
    monkeypatch.setattr(activation, "dynamic_source_health_registry", FakeRegistry())

    async def exercise() -> None:
        active = await activation.DynamicDiscoveryActivation.start()
        await active.aclose()

    asyncio.run(exercise())

    assert events[1] == "initialize"
    assert (
        "record",
        "frigate-github-latest-release-v1",
        DynamicSourceHealth.DEGRADED,
    ) in events
    assert events[-1] == "close"


def test_real_incompatible_cache_fails_soft_and_preserves_curated_only_startup(
    monkeypatch,
    tmp_path,
    caplog,
) -> None:
    cache_root = tmp_path / "discovery"
    sources_path = cache_root / "sources"
    sources_path.mkdir(parents=True, mode=0o700)
    format_path = cache_root / "format.json"
    incompatible = {
        "schema_version": "atlas-discovery-cache-v0",
        "registered_source_ids": [FRIGATE_ADAPTER_ID],
    }
    format_path.write_text(json.dumps(incompatible), encoding="utf-8")
    format_path.chmod(0o600)
    before = format_path.read_bytes()
    observed: list[tuple[str, DynamicSourceHealth]] = []

    class RecordingRegistry:
        def record(self, source_id, health) -> None:
            observed.append((source_id, health))

    class ForbiddenCoordinator:
        def __init__(self, store) -> None:
            raise AssertionError("refresh coordinator must not start")

    monkeypatch.setattr(activation, "DISCOVERY_CACHE_ROOT", cache_root)
    monkeypatch.setattr(activation, "dynamic_source_health_registry", RecordingRegistry())
    monkeypatch.setattr(activation, "RefreshCoordinator", ForbiddenCoordinator)
    assert activation.DiscoveryCacheStore is DiscoveryCacheStore

    async def exercise() -> None:
        active = await activation.DynamicDiscoveryActivation.start()
        await active.aclose()

    with caplog.at_level(logging.WARNING, logger=activation.__name__):
        asyncio.run(exercise())

    assert observed == [(FRIGATE_ADAPTER_ID, DynamicSourceHealth.UNAVAILABLE)]
    assert format_path.read_bytes() == before
    assert tuple(sources_path.iterdir()) == ()
    assert len(caplog.records) == 1
    assert caplog.records[0].getMessage() == (
        "Dynamic Discovery cache initialization unavailable; "
        "continuing with curated-only operation"
    )
    assert str(cache_root) not in caplog.text
