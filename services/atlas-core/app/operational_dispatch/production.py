"""Exact provider-aware production wiring for operational dispatch."""

from app.context import AtlasContext
from app.operational_dispatch.registry import (
    OperationalHandlerRegistration,
    OperationalHandlerRegistry,
)
from app.providers.proxmox_operational import ProxmoxQemuGracefulRestartHandler


def build_production_operational_handler_registry(
    atlas_context: AtlasContext,
) -> OperationalHandlerRegistry:
    """Build the one explicitly enabled production handler registration."""

    return OperationalHandlerRegistry(
        (
            OperationalHandlerRegistration(
                operation_intent="restart-service",
                provider_id="proxmox",
                resource_type="qemu",
                handler=ProxmoxQemuGracefulRestartHandler(atlas_context),
            ),
        )
    )
