from __future__ import annotations

from typing import Any
from urllib.parse import urljoin

from app.context import AtlasContext
from app.providers import (
    Provider,
    ProviderCapability,
    ProviderHealth,
    ProviderMetadata,
    ProviderPriority,
    ProviderWorkspace,
)
from app.providers.context_helpers import (
    context_from_legacy_service,
    metadata_from_context,
)
from app.services.health_service import check_service


class InventoryServiceProvider(Provider):
    """Provider backed by a service entry in inventory/services.yaml."""

    def __init__(
        self,
        service_id: str,
        service: AtlasContext | dict[str, Any],
    ) -> None:
        self._service_id = service_id
        # Temporary compatibility seam for direct legacy constructors.
        self.atlas_context = (
            service
            if isinstance(service, AtlasContext)
            else context_from_legacy_service(service_id, service)
        )

        self._metadata = metadata_from_context(
            self.atlas_context,
            default_description=(
                f"Inventory-backed provider for {self.atlas_context.metadata.name}"
            ),
            default_workspace=ProviderWorkspace.OPERATIONS,
            default_icon="box",
            default_priority=ProviderPriority.NORMAL,
            default_capabilities=frozenset({ProviderCapability.HEALTH}),
        )

    @property
    def metadata(self) -> ProviderMetadata:
        return self._metadata

    async def get_health(self) -> ProviderHealth:
        url = _health_url(self.atlas_context)

        if url is None:
            return ProviderHealth(
                status="offline",
                message="No health endpoint configured.",
            )

        result = check_service(
            url=url,
            expected_statuses=_expected_statuses(self.atlas_context),
            critical=bool(
                self.atlas_context.metadata.metadata.get("critical", False),
            ),
        )

        return ProviderHealth(
            status=result["status"],
            latency_ms=result.get("latency_ms"),
            http_status=result.get("http_status"),
            details={
                "url": result.get("url"),
                "critical": result.get("critical"),
            },
        )


def _health_url(atlas_context: AtlasContext) -> str | None:
    connection = atlas_context.connection
    if connection is None:
        return None
    if connection.base_url:
        base_url = connection.base_url.rstrip("/") + "/"
    elif connection.host and connection.port:
        base_url = f"{connection.mode}://{connection.host}:{connection.port}/"
    else:
        return None
    endpoint = connection.health_endpoint or "/"
    return urljoin(base_url, endpoint.lstrip("/"))


def _expected_statuses(atlas_context: AtlasContext) -> list[int]:
    connection = atlas_context.connection
    if connection is None:
        return [200]
    value = connection.metadata.get("expected_statuses")
    if isinstance(value, tuple | list):
        return [int(item) for item in value]
    if connection.expected_status is not None:
        return [connection.expected_status]
    return [200]
