"""Read-only dependency construction for dynamic Discovery projections."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from app.discovery.dynamic_cache import DiscoveryCacheStore
from app.discovery.dynamic_projection import (
    DynamicDiscoveryCacheReader,
    DynamicDiscoveryProjectionService,
)
from app.services.discovery import get_discovery_service

DISCOVERY_CACHE_ROOT = Path("/opt/atlas/data/cache/discovery")


def get_discovery_projection_service() -> DynamicDiscoveryProjectionService:
    """Construct the bounded read-only production projection dependency."""
    return DynamicDiscoveryProjectionService(
        get_discovery_service(),
        DynamicDiscoveryCacheReader(DiscoveryCacheStore(DISCOVERY_CACHE_ROOT)),
    )


def get_discovery_request_time() -> datetime:
    """Return the explicit UTC evaluation time for one evidence request."""
    return datetime.now(UTC)
