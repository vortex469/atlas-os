from __future__ import annotations

from app.providers import (
    Provider,
    ProviderCapability,
    ProviderHealth,
    ProviderMetadata,
    ProviderPriority,
    ProviderWorkspace,
)
from app.services.health_service import (
    build_service_url,
    check_service,
)


class InventoryServiceProvider(Provider):
    """Provider backed by a service entry in inventory/services.yaml."""

    def __init__(self, service_id: str, service: dict):
        self._service_id = service_id
        self._service = service

        self._metadata = ProviderMetadata(
            id=service_id.replace("_", "-"),
            name=service.get("name", service_id),
            version="1.0.0",
            description=f"Inventory-backed provider for {service.get('name', service_id)}",
            workspace=ProviderWorkspace.OPERATIONS,
            priority=(
                ProviderPriority.CRITICAL
                if service.get("critical", False)
                else ProviderPriority.NORMAL
            ),
            capabilities=frozenset(
                {
                    ProviderCapability.HEALTH,
                }
            ),
        )

    @property
    def metadata(self) -> ProviderMetadata:
        return self._metadata

    async def get_health(self) -> ProviderHealth:
        url = build_service_url(self._service)

        if url is None:
            return ProviderHealth(
                status="offline",
                message="No health endpoint configured.",
            )

        result = check_service(
            url=url,
            expected_statuses=self._service.get(
                "expected_status",
                [200],
            ),
            critical=self._service.get(
                "critical",
                False,
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
