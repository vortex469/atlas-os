from __future__ import annotations

from collections import Counter
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

from app.context import AtlasContext, ConnectionContext, SecretContext
from app.models.connections import (
    ProviderConnectionField,
    ProviderConnectionSchema,
    TestProviderConnectionRequest,
    TestProviderConnectionResult,
    UpdateProviderConnectionRequest,
    UpdateProviderConnectionResult,
)
from app.models.resources import (
    ProviderExpectationOption,
    ProviderResource,
    ProviderResourceCollection,
    ProviderResourceExpectation,
    ProviderResourceIdentity,
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
from app.providers.proxmox_identity import build_proxmox_qemu_identity
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

    def connection_schema(self) -> ProviderConnectionSchema:
        connection = self.atlas_context.connection
        secrets = self.atlas_context.secrets
        field_sources = connection.metadata.get("field_sources", {}) if connection else {}
        return ProviderConnectionSchema(
            provider_id=PROVIDER_ID,
            provider_name=self.metadata.name,
            fields=[
                ProviderConnectionField(
                    key="host",
                    label="Host",
                    kind="host",
                    required=True,
                    current_value=connection.host if connection else None,
                    source=_field_source(field_sources, "host", connection.source if connection else None),
                ),
                ProviderConnectionField(
                    key="port",
                    label="Port",
                    kind="port",
                    required=True,
                    current_value=connection.port if connection else None,
                    source=_field_source(field_sources, "port", connection.source if connection else None),
                    validation={"min": 1, "max": 65535},
                ),
                ProviderConnectionField(
                    key="node",
                    label="Node",
                    kind="string",
                    required=True,
                    current_value=connection.node if connection else None,
                    source=_field_source(field_sources, "node", connection.source if connection else None),
                ),
                ProviderConnectionField(
                    key="verify_tls",
                    label="Verify TLS",
                    kind="boolean",
                    required=True,
                    current_value=connection.verify_tls if connection else None,
                    source=_field_source(field_sources, "verify_tls", connection.source if connection else None),
                ),
                _secret_field("user", "User", secrets),
                _secret_field("token_name", "Token Name", secrets),
                _secret_field("token_value", "Token Value", secrets),
            ],
            editable=True,
            testable=True,
        )

    async def test_connection(
        self,
        request: TestProviderConnectionRequest,
    ) -> TestProviderConnectionResult:
        started_at = datetime.now(UTC)
        try:
            candidate_context = _candidate_context(self.atlas_context, request.values)
            status = _call_proxmox_status(candidate_context)
        except (OSError, RuntimeError, ValueError) as error:
            return TestProviderConnectionResult(
                provider_id=PROVIDER_ID,
                status="failure",
                message="Unable to reach Proxmox with the supplied connection values.",
                tested_at=started_at,
                diagnostics={"error": _sanitize_error(error, request.values)},
            )

        return TestProviderConnectionResult(
            provider_id=PROVIDER_ID,
            status="success",
            message="Proxmox connection test succeeded.",
            tested_at=started_at,
            latency_ms=0.0,
            diagnostics={"status": str(status.get("status", "online"))},
        )

    async def update_connection(
        self,
        request: UpdateProviderConnectionRequest,
    ) -> UpdateProviderConnectionResult:
        raise NotImplementedError(
            "Proxmox connection updates are orchestrated by ProviderConnectionService.",
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
            identity = _qemu_identity(guest, node=node)
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
                    identity=identity,
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
                        "template": bool(guest.get("template", False)),
                        "lock": guest.get("lock"),
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


def _field_source(
    field_sources: Mapping[str, Any],
    field_name: str,
    fallback: str | None,
) -> str | None:
    value = field_sources.get(field_name)
    return str(value) if value is not None else fallback


def _secret_field(
    name: str,
    label: str,
    secrets: Mapping[str, Any],
) -> ProviderConnectionField:
    secret = secrets.get(name)
    configured = bool(secret and secret.configured)
    source = str(secret.source) if secret is not None else "missing"
    return ProviderConnectionField(
        key=name,
        label=label,
        kind="secret",
        required=True,
        editable=True,
        secret=True,
        secret_state="configured" if configured else "missing",
        source=source,
    )


def _candidate_context(
    atlas_context: AtlasContext,
    values: Mapping[str, Any],
) -> AtlasContext:
    connection_updates = {
        key: values[key]
        for key in ("host", "port", "node", "verify_tls")
        if key in values
    }
    secret_updates = {
        key: str(values[key])
        for key in ("user", "token_name", "token_value")
        if values.get(key)
    }
    connection = atlas_context.connection
    connection_data = connection.model_dump() if connection is not None else {}
    connection_data.update(connection_updates)
    connection_data["source"] = "runtime"
    secrets = dict(atlas_context.secrets)
    for name, value in secret_updates.items():
        existing = secrets.get(name)
        secret_data = existing.model_dump() if existing is not None else {"name": name}
        secret_data.update(
            {
                "source": "runtime",
                "configured": True,
                "value": value,
                "redacted": "********",
            },
        )
        secrets[name] = SecretContext.model_validate(secret_data)
    return atlas_context.model_copy(
        update={
            "connection": ConnectionContext.model_validate(connection_data),
            "secrets": secrets,
        },
    )


def _sanitize_error(error: Exception, values: Mapping[str, Any]) -> str:
    message = str(error)
    if not message:
        return error.__class__.__name__
    for value in values.values():
        if isinstance(value, str) and value:
            message = message.replace(value, "[redacted]")
    return message[:240]


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


def _qemu_identity(
    guest: Mapping[str, Any], *, node: str
) -> ProviderResourceIdentity | None:
    if guest.get("type") != "qemu" or not guest.get("vmgenid"):
        return None
    return build_proxmox_qemu_identity(
        node=node,
        vmid=guest.get("vmid"),
        vmgenid=str(guest["vmgenid"]),
    )


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
