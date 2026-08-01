from __future__ import annotations

from app.discovery.compatibility import (
    CompatibilityAssessment,
    CompatibilityContextBuilder,
    assess_compatibility,
)
from app.discovery.environment import get_default_context_builder
from app.services.discovery import (
    DiscoveryCatalogService,
    get_discovery_service,
)


class DiscoveryCompatibilityServiceError(RuntimeError):
    """Base Discovery compatibility service error."""


class DiscoveryCompatibilityContextUnavailableError(
    DiscoveryCompatibilityServiceError,
):
    """Raised when a compatibility context cannot be built safely."""


class DiscoveryCompatibilityService:
    """Coordinates read-only Discovery compatibility assessment."""

    def __init__(
        self,
        discovery_service: DiscoveryCatalogService | None = None,
        context_builder: CompatibilityContextBuilder | None = None,
    ) -> None:
        self._discovery_service = discovery_service or get_discovery_service()
        self._context_builder = context_builder or get_default_context_builder()

    def assess_item(
        self,
        item_id: str,
        *,
        target: str = "atlas",
    ) -> CompatibilityAssessment:
        repository = self._discovery_service.repository()
        entry = self._discovery_service.get_entry(item_id)

        try:
            context = self._context_builder.build_context(target)
        except Exception as error:
            raise DiscoveryCompatibilityContextUnavailableError(
                "Discovery compatibility context is unavailable."
            ) from error

        return assess_compatibility(
            entry.item,
            context,
            repository,
        )


_discovery_compatibility_service = DiscoveryCompatibilityService()


def get_discovery_compatibility_service() -> DiscoveryCompatibilityService:
    return _discovery_compatibility_service
