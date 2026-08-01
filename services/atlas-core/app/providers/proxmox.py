from __future__ import annotations

from collections import Counter
from datetime import UTC, datetime
from typing import Any

from app.config import policies as policy_config
from app.config.resource_policies import (
    PROXMOX_GUEST_EXPECTATIONS,
    update_proxmox_guest_expectation,
)
from app.models.resources import (
    ProviderExpectationOption,
    ProviderResource,
    ProviderResourceCollection,
    ProviderResourceExpectation,
    ProviderResourceSummary,
    UpdateResourceExpectationResult,
)
from app.providers.base import Provider
from app.providers.capabilities import (
    ProviderCapability,
    ProviderPriority,
    ProviderWorkspace,
)
from app.providers.models import ProviderHealth, ProviderMetadata
from app.services.proxmox_service import get_proxmox_guests, get_proxmox_status

PROVIDER_ID = "proxmox"
_EXPECTATION_OPTIONS = [
    ProviderExpectationOption(
        value="running",
        label="Expected Running",
        description="Atlas should warn when this guest is not running.",
    ),
    ProviderExpectationOption(
        value="stopped",
        label="Expected Stopped",
        description="Atlas should accept this guest being stopped.",
    ),
    ProviderExpectationOption(
        value="ignored",
        label="Ignore",
        description="Atlas should not monitor this guest state.",
        terminal=True,
    ),
]


class ProxmoxProvider(Provider):
    """Proxmox provider with generic resource management support."""

    def __init__(self, service: dict[str, Any]) -> None:
        self._service = service
        critical = bool(service.get("critical", True))
        self._metadata = ProviderMetadata(
            id=PROVIDER_ID,
            name=str(service.get("name", "Proxmox")),
            version="1.0.0",
            description=str(
                service.get(
                    "description",
                    "Virtualization provider for Proxmox guests.",
                )
            ),
            workspace=ProviderWorkspace.OPERATIONS,
            icon="server",
            priority=(
                ProviderPriority.CRITICAL
                if critical
                else ProviderPriority.HIGH
            ),
            capabilities=frozenset(
                {
                    ProviderCapability.HEALTH,
                    ProviderCapability.DISCOVERY,
                    ProviderCapability.RESOURCES,
                    ProviderCapability.MONITORING,
                    ProviderCapability.DIAGNOSTICS,
                    ProviderCapability.ACTIONS,
                }
            ),
        )

    @property
    def metadata(self) -> ProviderMetadata:
        return self._metadata

    async def get_health(self) -> ProviderHealth:
        try:
            status = get_proxmox_status()
        except (OSError, RuntimeError, ValueError) as error:
            return ProviderHealth(
                status="offline",
                message="Unable to reach Proxmox.",
                details={"error": str(error)},
            )

        return ProviderHealth(
            status=str(status.get("status", "online")),
            message="Proxmox is reachable.",
            details=status,
        )

    def expectation_options(
        self,
        resource_type: str,
    ) -> list[ProviderExpectationOption]:
        return list(_EXPECTATION_OPTIONS)

    def normalize_expectation(
        self,
        resource_type: str,
        expectation: str,
    ) -> str:
        normalized = expectation.strip().lower()
        if normalized not in PROXMOX_GUEST_EXPECTATIONS:
            raise ValueError(
                "Proxmox guest expectation must be one of: "
                f"{', '.join(sorted(PROXMOX_GUEST_EXPECTATIONS))}."
            )
        return normalized

    def expectation_label(
        self,
        resource_type: str,
        expectation: str | None,
    ) -> str:
        if expectation is None:
            return "Needs Review"

        labels = {
            option.value: option.label
            for option in self.expectation_options(resource_type)
        }
        return labels.get(expectation, expectation)

    async def list_resources(self) -> ProviderResourceCollection:
        guest_inventory = get_proxmox_guests()
        policies = policy_config.load_policies()
        configured_guests = policies.proxmox.guests
        node = str(guest_inventory.get("node", "unknown"))
        resources: list[ProviderResource] = []
        seen_vmids: set[str] = set()

        for guest in guest_inventory.get("guests", []):
            vmid = str(guest.get("vmid"))
            seen_vmids.add(vmid)
            resource_type = str(guest.get("type", "unknown"))
            expected = _configured_expectation(configured_guests, vmid)
            resources.append(
                ProviderResource(
                    provider_id=PROVIDER_ID,
                    resource_id=vmid,
                    display_name=str(
                        guest.get("name") or f"Proxmox guest {vmid}"
                    ),
                    resource_type=resource_type,
                    current_state=str(guest.get("status", "unknown")),
                    expectation=self._resource_expectation(
                        resource_type,
                        expected,
                    ),
                    configured=expected is not None,
                    missing=False,
                    metadata={
                        "node": node,
                        "vmid": guest.get("vmid"),
                        "cpu_percent": guest.get("cpu_percent"),
                        "memory_used_gib": guest.get("memory_used_gib"),
                        "memory_total_gib": guest.get("memory_total_gib"),
                        "uptime_seconds": guest.get("uptime_seconds"),
                    },
                )
            )

        for vmid, guest_policy in configured_guests.items():
            if vmid in seen_vmids:
                continue

            resources.append(
                ProviderResource(
                    provider_id=PROVIDER_ID,
                    resource_id=vmid,
                    display_name=f"Missing Proxmox guest {vmid}",
                    resource_type="unknown",
                    current_state="missing",
                    expectation=self._resource_expectation(
                        "unknown",
                        guest_policy.expected,
                    ),
                    configured=True,
                    missing=True,
                    metadata={
                        "node": node,
                        "vmid": _metadata_vmid(vmid),
                    },
                )
            )

        resources.sort(key=lambda resource: _resource_sort_key(resource.resource_id))

        return ProviderResourceCollection(
            provider_id=PROVIDER_ID,
            provider_name=self.metadata.name,
            refreshed_at=datetime.now(UTC),
            resources=resources,
            summary=_resource_summary(resources),
            metadata={
                "node": node,
                "running": guest_inventory.get("running", 0),
                "stopped": guest_inventory.get("stopped", 0),
            },
        )

    async def refresh_resources(self) -> ProviderResourceCollection:
        return await self.list_resources()

    async def update_resource_expectation(
        self,
        resource_id: str,
        expectation: str,
    ) -> UpdateResourceExpectationResult:
        normalized = self.normalize_expectation("unknown", expectation)
        update_proxmox_guest_expectation(resource_id, normalized)

        return UpdateResourceExpectationResult(
            provider_id=PROVIDER_ID,
            resource_id=str(resource_id),
            expectation=self._resource_expectation("unknown", normalized),
            updated_at=datetime.now(UTC),
        )

    def _resource_expectation(
        self,
        resource_type: str,
        expectation: str | None,
    ) -> ProviderResourceExpectation:
        if expectation is None:
            return ProviderResourceExpectation(
                value=None,
                label="Needs Review",
                state="needs_review",
                allowed_values=self.expectation_options(resource_type),
            )

        state = "ignored" if expectation == "ignored" else "configured"
        return ProviderResourceExpectation(
            value=expectation,
            label=self.expectation_label(resource_type, expectation),
            state=state,
            allowed_values=self.expectation_options(resource_type),
        )


def _configured_expectation(
    configured_guests: dict[str, Any],
    vmid: str,
) -> str | None:
    guest_policy = configured_guests.get(vmid)
    if guest_policy is None:
        return None
    return guest_policy.expected


def _metadata_vmid(vmid: str) -> int | str:
    try:
        return int(vmid)
    except ValueError:
        return vmid


def _resource_sort_key(resource_id: str) -> tuple[int, int | str]:
    try:
        return (0, int(resource_id))
    except ValueError:
        return (1, resource_id)


def _resource_summary(
    resources: list[ProviderResource],
) -> ProviderResourceSummary:
    by_type = Counter(resource.resource_type for resource in resources)
    by_state = Counter(resource.current_state for resource in resources)

    return ProviderResourceSummary(
        total=len(resources),
        configured=sum(resource.configured for resource in resources),
        needs_review=sum(resource.needs_review for resource in resources),
        missing=sum(resource.missing for resource in resources),
        ignored=sum(
            resource.expectation.state == "ignored"
            for resource in resources
        ),
        by_type=dict(by_type),
        by_state=dict(by_state),
    )
