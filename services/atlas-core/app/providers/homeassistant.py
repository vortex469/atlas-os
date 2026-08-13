from __future__ import annotations

from time import perf_counter

import httpx

from app.context import AtlasContext
from app.providers import (
    Provider,
    ProviderCapability,
    ProviderHealth,
    ProviderPriority,
    ProviderWorkspace,
)
from app.providers.context_helpers import metadata_from_context
from app.services.homeassistant_service import get_homeassistant_status


class HomeAssistantProvider(Provider):
    """Home Assistant provider backed by immutable AtlasContext."""

    def __init__(self, atlas_context: AtlasContext) -> None:
        self.atlas_context = atlas_context
        self._metadata = metadata_from_context(
            atlas_context,
            default_description="Home automation health and entity provider.",
            default_workspace=ProviderWorkspace.AUTOMATION,
            default_icon="home",
            default_priority=ProviderPriority.HIGH,
            default_capabilities=frozenset(
                {
                    ProviderCapability.HEALTH,
                    ProviderCapability.FINDINGS,
                    ProviderCapability.METRICS,
                    ProviderCapability.CONFIGURATION,
                },
            ),
        )

    @property
    def metadata(self):
        return self._metadata

    async def get_health(self) -> ProviderHealth:
        started_at = perf_counter()
        try:
            status = get_homeassistant_status(self.atlas_context)
        except RuntimeError as error:
            return ProviderHealth(
                status="degraded",
                latency_ms=_elapsed_ms(started_at),
                message="Home Assistant API credentials are not configured.",
                details={"credentials_configured": False, "error": str(error)},
            )
        except (httpx.HTTPError, KeyError, TypeError, ValueError) as error:
            return ProviderHealth(
                status="offline",
                latency_ms=_elapsed_ms(started_at),
                message="Home Assistant API is unavailable.",
                details={"credentials_configured": True, "error": str(error)},
            )

        return ProviderHealth(
            status="online",
            latency_ms=_elapsed_ms(started_at),
            message="Home Assistant API is available.",
            details=status,
        )


def _elapsed_ms(started_at: float) -> float:
    return round((perf_counter() - started_at) * 1000, 2)
