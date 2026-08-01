from __future__ import annotations

from time import perf_counter

from app.context import AtlasContext
from app.providers import (
    Provider,
    ProviderCapability,
    ProviderHealth,
    ProviderPriority,
    ProviderWorkspace,
)
from app.providers.context_helpers import metadata_from_context
from app.services.docker_service import (
    get_docker_connection_diagnostics,
    get_docker_status,
)


class DockerProvider(Provider):
    """Docker provider backed by a fixed privileged local Unix socket."""

    def __init__(self, atlas_context: AtlasContext) -> None:
        self.atlas_context = atlas_context
        self._metadata = metadata_from_context(
            atlas_context,
            default_description="Docker engine health and container inventory provider.",
            default_workspace=ProviderWorkspace.OPERATIONS,
            default_icon="container",
            default_priority=ProviderPriority.HIGH,
            default_capabilities=frozenset(
                {
                    ProviderCapability.HEALTH,
                    ProviderCapability.FINDINGS,
                    ProviderCapability.METRICS,
                    ProviderCapability.CONNECTION,
                    ProviderCapability.DIAGNOSTICS,
                },
            ),
        )

    @property
    def metadata(self):
        return self._metadata

    async def get_health(self) -> ProviderHealth:
        started_at = perf_counter()
        status = get_docker_status(self.atlas_context)
        health_status = "online" if status.get("status") == "online" else "offline"
        details = dict(status)
        details["connection"] = get_docker_connection_diagnostics(self.atlas_context)
        return ProviderHealth(
            status=health_status,
            latency_ms=round((perf_counter() - started_at) * 1000, 2),
            message=(
                "Docker engine is available."
                if health_status == "online"
                else "Docker engine is unavailable."
            ),
            details=details,
        )
