from concurrent.futures import ThreadPoolExecutor

import pytest

from app.discovery.dynamic_health import DynamicSourceHealthRegistry
from app.discovery.dynamic_sources import DynamicSourceHealth


def test_health_registry_is_absent_until_an_observation_is_recorded() -> None:
    registry = DynamicSourceHealthRegistry()

    assert registry.read_health("unknown") is None
    registry.record("frigate-github-latest-release-v1", DynamicSourceHealth.HEALTHY)
    assert (
        registry.read_health("frigate-github-latest-release-v1")
        is DynamicSourceHealth.HEALTHY
    )


def test_health_registry_rejects_untyped_observations() -> None:
    registry = DynamicSourceHealthRegistry()

    with pytest.raises(TypeError, match="DynamicSourceHealth"):
        registry.record("frigate-github-latest-release-v1", "healthy")  # type: ignore[arg-type]


def test_health_registry_serializes_concurrent_reads_and_writes() -> None:
    registry = DynamicSourceHealthRegistry()
    source_id = "frigate-github-latest-release-v1"

    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = [
            executor.submit(registry.record, source_id, health)
            for health in DynamicSourceHealth
            for _ in range(20)
        ]
        futures.extend(
            executor.submit(registry.read_health, source_id) for _ in range(60)
        )
        for future in futures:
            future.result()

    assert isinstance(registry.read_health(source_id), DynamicSourceHealth)
