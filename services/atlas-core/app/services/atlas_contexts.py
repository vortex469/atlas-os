from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from app.config.inventory import load_inventory
from app.config.settings import Settings
from app.config.settings import settings as default_settings
from app.context import (
    AtlasContext,
    AtlasContextDiagnostics,
    ConnectionContext,
    DiagnosticsContextItem,
    MetadataContext,
    RuntimeContext,
    SecretContext,
)
from app.services.connection_resolver import ConnectionContextResolver
from app.services.runtime_resolver import RuntimeContextResolver
from app.services.secret_resolver import SecretContextResolver


class AtlasContextResolutionError(KeyError):
    """Raised when Atlas cannot resolve context for a consumer."""


class LegacyAtlasContextResolver:
    """Resolve AtlasContext objects from the current legacy configuration."""

    def __init__(
        self,
        settings: Settings = default_settings,
        inventory: Mapping[str, Any] | None = None,
        environ: Mapping[str, str] | None = None,
        data_root: Path | str = Path("/opt/atlas/data"),
        runtime_connection_overrides: Mapping[
            str,
            Mapping[str, Any],
        ] | None = None,
        runtime_secret_overrides: Mapping[
            str,
            Mapping[str, str],
        ] | None = None,
    ) -> None:
        self._settings = settings
        self._inventory = inventory
        self._environ = environ
        self._data_root = Path(data_root)
        self._runtime_connection_overrides = runtime_connection_overrides or {}
        self._runtime_secret_overrides = runtime_secret_overrides or {}

    def resolve_context(self, consumer_id: str) -> AtlasContext:
        declarations = self._provider_declarations()
        if consumer_id not in declarations:
            raise AtlasContextResolutionError(
                f"Atlas context consumer '{consumer_id}' is not declared.",
            )

        metadata = _metadata_from_declaration(
            consumer_id,
            declarations[consumer_id],
        )
        connection = self._connection_resolver().resolve_connection(metadata)
        secrets = self._secret_resolver().resolve_secrets(metadata)
        runtime = self._runtime_resolver().resolve_runtime(metadata)
        diagnostics = self.validate_context_parts(
            metadata=metadata,
            connection=connection,
            secrets=secrets,
            runtime=runtime,
        )
        generation = _stable_generation(
            metadata=metadata,
            connection=connection,
            secrets=secrets,
            runtime=runtime,
            diagnostics=diagnostics,
        )

        return AtlasContext(
            metadata=metadata,
            connection=connection,
            secrets=secrets,
            runtime=runtime,
            diagnostics=diagnostics,
            generation=generation,
        )

    def resolve_all_contexts(self) -> tuple[AtlasContext, ...]:
        return tuple(
            self.resolve_context(provider_id)
            for provider_id in self._provider_declarations()
        )

    def validate_context(self, context: AtlasContext) -> AtlasContextDiagnostics:
        return self.validate_context_parts(
            metadata=context.metadata,
            connection=context.connection,
            secrets=context.secrets,
            runtime=context.runtime,
        )

    def validate_context_parts(
        self,
        metadata: MetadataContext,
        connection: ConnectionContext | None,
        secrets: Mapping[str, SecretContext],
        runtime: RuntimeContext,
    ) -> AtlasContextDiagnostics:
        items: list[DiagnosticsContextItem] = []
        if connection is None:
            items.append(
                DiagnosticsContextItem(
                    code="connection-missing",
                    message="No connection context is configured.",
                    severity="warning",
                    source="missing",
                    field="connection",
                ),
            )
        else:
            items.append(
                DiagnosticsContextItem(
                    code="connection-resolved",
                    message=(
                        "Connection context resolved from "
                        f"{connection.source}."
                    ),
                    severity="info",
                    source=connection.source,
                    field="connection",
                ),
            )

        for secret_name, secret in secrets.items():
            if secret.configured:
                items.append(
                    DiagnosticsContextItem(
                        code="secret-configured",
                        message=(
                            f"Secret '{secret_name}' is configured from "
                            f"{secret.source}."
                        ),
                        severity="info",
                        source=secret.source,
                        field=f"secrets.{secret_name}",
                    ),
                )
            else:
                items.append(
                    DiagnosticsContextItem(
                        code="secret-missing",
                        message=f"Secret '{secret_name}' is not configured.",
                        severity="warning",
                        source="missing",
                        field=f"secrets.{secret_name}",
                    ),
                )

        items.append(
            DiagnosticsContextItem(
                code="runtime-resolved",
                message="Runtime paths resolved without mutation.",
                severity="info",
                source="computed",
                field="runtime",
            ),
        )

        return AtlasContextDiagnostics(items=tuple(items))

    def _provider_declarations(self) -> dict[str, Mapping[str, Any]]:
        inventory = self._load_inventory()
        services = inventory.get("services", {})
        declarations: dict[str, Mapping[str, Any]] = {}
        if isinstance(services, Mapping):
            declarations.update(
                (str(provider_id), service)
                for provider_id, service in services.items()
                if isinstance(service, Mapping)
            )

        if "proxmox" not in declarations:
            declarations["proxmox"] = {
                "name": "Proxmox",
                "description": "Virtualization provider for Proxmox guests.",
                "critical": True,
            }

        return declarations

    def _load_inventory(self) -> Mapping[str, Any]:
        if self._inventory is not None:
            return self._inventory
        loaded = load_inventory()
        if isinstance(loaded, Mapping):
            return loaded
        return {}

    def _connection_resolver(self) -> ConnectionContextResolver:
        return ConnectionContextResolver(
            settings=self._settings,
            inventory=self._load_inventory(),
            runtime_overrides=self._runtime_connection_overrides,
        )

    def _secret_resolver(self) -> SecretContextResolver:
        return SecretContextResolver(
            environ=self._environ,
            runtime_secrets=self._runtime_secret_overrides,
        )

    def _runtime_resolver(self) -> RuntimeContextResolver:
        return RuntimeContextResolver(data_root=self._data_root)


def _metadata_from_declaration(
    provider_id: str,
    service: Mapping[str, Any],
) -> MetadataContext:
    legacy_service = dict(service)
    critical = _critical_for_provider(provider_id, service)
    return MetadataContext(
        consumer_id=provider_id,
        consumer_type="provider",
        name=str(service.get("name") or _display_name(provider_id)),
        description=str(service.get("description") or ""),
        version="1.0.0",
        workspace=_workspace_for_provider(provider_id),
        priority=_priority_for_provider(provider_id, critical),
        icon=_icon_for_provider(provider_id),
        capabilities=frozenset(_capabilities_for_provider(provider_id)),
        source="inventory" if service else "defaults",
        metadata={
            "critical": critical,
            "role": service.get("role"),
            "provider_type": _provider_type_for_provider(provider_id),
            "legacy_service": legacy_service,
        },
    )


def _provider_type_for_provider(provider_id: str) -> str:
    known_provider_types = {
        "frigate",
        "home_assistant",
        "n8n",
        "obsidian",
        "ollama",
        "opnsense",
        "proxmox",
        "qdrant",
    }
    if provider_id in known_provider_types:
        return provider_id
    return "inventory"

def _display_name(provider_id: str) -> str:
    names = {
        "opnsense": "OPNsense",
        "n8n": "n8n",
    }
    if provider_id in names:
        return names[provider_id]
    return provider_id.replace("_", " ").replace("-", " ").title()


def _workspace_for_provider(provider_id: str) -> str:
    if provider_id in {"home_assistant", "n8n", "frigate"}:
        return "automation"
    if provider_id in {"obsidian", "qdrant"}:
        return "knowledge"
    if provider_id == "ollama":
        return "developer"
    return "operations"


def _critical_for_provider(
    provider_id: str,
    service: Mapping[str, Any],
) -> bool:
    default = provider_id == "opnsense"
    return bool(service.get("critical", default))


def _priority_for_provider(provider_id: str, critical: bool) -> str:
    if critical:
        return "critical"
    if provider_id in {"frigate", "n8n", "qdrant", "ollama", "opnsense"}:
        return "high"
    return "normal"


def _icon_for_provider(provider_id: str) -> str:
    icons = {
        "proxmox": "server",
        "home_assistant": "home",
        "opnsense": "shield",
        "frigate": "camera",
        "n8n": "workflow",
        "obsidian": "book-open",
        "qdrant": "database",
        "ollama": "brain",
    }
    return icons.get(provider_id, "box")


def _capabilities_for_provider(provider_id: str) -> tuple[str, ...]:
    if provider_id == "proxmox":
        return (
            "health",
            "discovery",
            "resources",
            "monitoring",
            "diagnostics",
            "actions",
        )
    if provider_id == "opnsense":
        return ("health", "actions", "configuration")
    if provider_id == "home_assistant":
        return ("health", "findings", "metrics", "configuration")
    if provider_id in {"frigate", "n8n", "qdrant", "obsidian", "ollama"}:
        return ("health", "findings", "actions", "metrics", "configuration")
    return ("health",)


def _stable_generation(
    metadata: MetadataContext,
    connection: ConnectionContext | None,
    secrets: Mapping[str, SecretContext],
    runtime: RuntimeContext,
    diagnostics: AtlasContextDiagnostics,
) -> str:
    payload = {
        "metadata": metadata.model_dump(mode="json"),
        "connection": (
            connection.model_dump(mode="json") if connection is not None else None
        ),
        "secrets": {
            name: {
                "name": secret.name,
                "source": secret.source,
                "configured": secret.configured,
                "redacted": secret.redacted,
            }
            for name, secret in sorted(secrets.items())
        },
        "runtime": runtime.model_dump(mode="json"),
        "diagnostics": diagnostics.model_dump(mode="json"),
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()[:16]


__all__ = [
    "AtlasContextResolutionError",
    "LegacyAtlasContextResolver",
]
