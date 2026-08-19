"""Opt-in startup activation for the single reviewed dynamic Discovery source."""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from app.discovery.dynamic_cache import REGISTERED_SOURCE_IDS, DiscoveryCacheStore
from app.discovery.dynamic_health import dynamic_source_health_registry
from app.discovery.dynamic_refresh import RefreshCoordinator
from app.discovery.dynamic_sources import DynamicSourceHealth
from app.services.discovery_dynamic_projection import DISCOVERY_CACHE_ROOT

logger = logging.getLogger(__name__)


class DynamicDiscoveryActivation:
    def __init__(self, coordinator: RefreshCoordinator | None) -> None:
        self._coordinator = coordinator

    @classmethod
    async def start(cls) -> DynamicDiscoveryActivation:
        store = DiscoveryCacheStore(DISCOVERY_CACHE_ROOT)
        try:
            store.initialize()
        except Exception:  # noqa: BLE001 - optional cache failure must not fail Core
            for source_id in REGISTERED_SOURCE_IDS:
                dynamic_source_health_registry.record(
                    source_id, DynamicSourceHealth.UNAVAILABLE
                )
            logger.warning(
                "Dynamic Discovery cache initialization unavailable; "
                "continuing with curated-only operation"
            )
            return cls(None)
        coordinator = RefreshCoordinator(store)
        batch = await coordinator.refresh(now=datetime.now(UTC))
        for source in batch.sources:
            if source.health is not None:
                dynamic_source_health_registry.record(source.source_id, source.health)
        return cls(coordinator)

    async def aclose(self) -> None:
        if self._coordinator is not None:
            await self._coordinator.aclose()
