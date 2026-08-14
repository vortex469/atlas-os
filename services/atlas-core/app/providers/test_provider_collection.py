from __future__ import annotations

import asyncio
import time
from types import SimpleNamespace

from app.providers import (
    Provider,
    ProviderHealth,
    ProviderMetadata,
    ProviderWorkspace,
    provider_registry,
)
from app.routes import providers as provider_routes


class BlockingHealthProvider(Provider):
    def __init__(self, provider_id: str, delay: float) -> None:
        self._delay = delay
        self._metadata = ProviderMetadata(
            id=provider_id,
            name=provider_id.title(),
            workspace=ProviderWorkspace.OPERATIONS,
        )

    @property
    def metadata(self) -> ProviderMetadata:
        return self._metadata

    async def get_health(self) -> ProviderHealth:
        time.sleep(self._delay)  # noqa: ASYNC251 - models legacy blocking provider
        return ProviderHealth(status="online", message="available")


def test_provider_list_health_is_concurrent_and_deterministically_ordered() -> None:
    previous = provider_registry.all()
    provider_registry.replace_all(
        (
            BlockingHealthProvider("slow-provider", 0.06),
            BlockingHealthProvider("fast-provider", 0.02),
        )
    )
    try:
        started_at = time.perf_counter()
        result = asyncio.run(provider_routes.list_providers())
        duration = time.perf_counter() - started_at
    finally:
        provider_registry.replace_all(previous)

    assert duration < 0.11
    assert [provider["id"] for provider in result] == [
        "fast-provider",
        "slow-provider",
    ]
    assert all(provider["health"]["status"] == "online" for provider in result)


def test_provider_timeout_is_isolated_sanitized_and_off_loop(monkeypatch) -> None:
    previous = provider_registry.all()
    provider_registry.replace_all(
        (
            BlockingHealthProvider("hanging-provider", 0.1),
            BlockingHealthProvider("healthy-provider", 0),
        )
    )
    monkeypatch.setattr(
        provider_routes,
        "settings",
        SimpleNamespace(
            intelligence=SimpleNamespace(provider_timeout_seconds=0.02),
        ),
    )

    async def exercise():
        started_at = time.perf_counter()
        task = asyncio.create_task(provider_routes.list_providers())
        await asyncio.sleep(0.005)
        responsive_at = time.perf_counter() - started_at
        result = await task
        return responsive_at, time.perf_counter() - started_at, result

    try:
        responsive_at, returned_at, result = asyncio.run(exercise())
    finally:
        provider_registry.replace_all(previous)

    assert responsive_at < 0.02
    assert returned_at < 0.06
    by_id = {provider["id"]: provider for provider in result}
    assert by_id["healthy-provider"]["health"]["status"] == "online"
    timeout_health = by_id["hanging-provider"]["health"]
    assert timeout_health["status"] == "offline"
    assert timeout_health["message"] == "Provider health check timed out."
    assert timeout_health["details"] == {"timeout_seconds": 0.02}
