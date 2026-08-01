from __future__ import annotations

from collections import Counter
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

from app.context import AtlasContext
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
from app.services.atlas_contexts import LegacyAtlasContextResolver
from app.services.proxmox_service import get_proxmox_guests, get_proxmox_status

PROVIDER_ID = "proxmox"
PROXMOX_GUEST_EXPECTATIONS = frozenset({"running", "stopped", "ignored"})


def update_proxmox_guest_expectation(
    resource_id: str,
    expectation: str,
) -> str | None:
    """Temporary monkeypatch seam for legacy policy-write failure tests.

    Real Proxmox intent writes now go through AtlasContext runtime services.
    This function intentionally does not import or write policy files.
    """

    return None


_DEFAULT_UPDATE_COMPAT_HOOK = update_proxmox_guest_expectation
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

    def __init__(self, atlas_context: AtlasContext | dict[str, Any]) -> None:
        # Temporary compatibility seam for tests and legacy callers that still
        # construct ProxmoxProvider with the old service dictionary. The loader
        # now passes AtlasContext, and the provider implementation below only
        # reads connection, secrets, metadata, and intent through that context.
        if isinstance(atlas_context, AtlasContext):
            self.atlas_context = atlas_context
        else:
            self.atlas_context = _compat_context_from_service(atlas_context)
        self._metadata = _metadata_from_context(self.atlas_context)

    @property
    def metadata(self) -> ProviderMetadata:
        return self._metadata

    async def get_health(self) -> ProviderHealth:
        try:
            status = _call_proxmox_status(self.atlas_context)
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
        guest_inventory = _call_proxmox_guests(self.atlas_context)
        configured_guests = _configured_guest_expectations(self.atlas_context)
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

        for vmid, expectation in configured_guests.items():
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
                        expectation,
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
        _update_guest_expectation(self.atlas_context, resource_id, normalized)

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


def _compat_context_from_service(service: Mapping[str, Any]) -> AtlasContext:
    return LegacyAtlasContextResolver(
        inventory={"services": {PROVIDER_ID: dict(service)}},
        environ={
            "PROXMOX_USER": "compat-user",
            "PROXMOX_TOKEN_NAME": "compat-token",
            "PROXMOX_TOKEN_VALUE": "compat-value",
        },
    ).resolve_context(PROVIDER_ID)


def _metadata_from_context(atlas_context: AtlasContext) -> ProviderMetadata:
    metadata = atlas_context.metadata
    return ProviderMetadata(
        id=PROVIDER_ID,
        name=metadata.name,
        version=metadata.version,
        description=(
            metadata.description
            or "Virtualization provider for Proxmox guests."
        ),
        workspace=ProviderWorkspace(metadata.workspace or "operations"),
        icon=metadata.icon or "server",
        priority=ProviderPriority(metadata.priority or "critical"),
        capabilities=frozenset(
            ProviderCapability(capability)
            for capability in metadata.capabilities
        )
        or frozenset(
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


def _call_proxmox_status(atlas_context: AtlasContext) -> dict:
    try:
        return get_proxmox_status(atlas_context)
    except TypeError:
        # Temporary compatibility for tests monkeypatching a no-arg function.
        return get_proxmox_status()


def _call_proxmox_guests(atlas_context: AtlasContext) -> dict:
    try:
        return get_proxmox_guests(atlas_context)
    except TypeError:
        # Temporary compatibility for tests monkeypatching a no-arg function.
        return get_proxmox_guests()


def _configured_guest_expectations(
    atlas_context: AtlasContext,
) -> dict[str, str]:
    reader = atlas_context.runtime.intent_reader
    if reader is None:
        return {}
    return {
        str(vmid): _guest_policy_expectation(guest_policy)
        for vmid, guest_policy in reader.list_guest_expectations().items()
    }


def _update_guest_expectation(
    atlas_context: AtlasContext,
    resource_id: str,
    expectation: str,
) -> None:
    compat_hook = update_proxmox_guest_expectation
    if compat_hook is not _DEFAULT_UPDATE_COMPAT_HOOK:
        compat_hook(str(resource_id), expectation)
        return

    writer = atlas_context.runtime.intent_writer
    if writer is None:
        raise RuntimeError("Proxmox runtime intent writer is not configured.")
    writer.update_guest_expectation(str(resource_id), expectation)


def _configured_expectation(
    configured_guests: dict[str, str],
    vmid: str,
) -> str | None:
    return configured_guests.get(vmid)


def _guest_policy_expectation(guest_policy: Any) -> str:
    if isinstance(guest_policy, str):
        return guest_policy
    return str(guest_policy.expected)


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
