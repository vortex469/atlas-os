from __future__ import annotations

from collections.abc import Mapping
from typing import Any
from urllib.parse import urljoin

from app.context import AtlasContext
from app.providers.capabilities import (
    ProviderCapability,
    ProviderPriority,
    ProviderWorkspace,
)
from app.providers.models import ProviderMetadata
from app.services.atlas_contexts import LegacyAtlasContextResolver

_DESCRIPTION_BY_PROVIDER = {
    "frigate": "NVR health, camera telemetry, and version provider.",
    "n8n": "Workflow automation health and inventory provider.",
    "obsidian": "Local Obsidian vault availability and metadata provider.",
    "ollama": "Local model inference, model inventory, and model lifecycle provider.",
    "opnsense": "Firewall health and firmware status provider.",
    "qdrant": "Vector database health and collection inventory provider.",
}


def context_from_legacy_service(
    provider_id: str,
    service: Mapping[str, Any],
    *,
    environ: Mapping[str, str] | None = None,
) -> AtlasContext:
    """Temporary seam for legacy provider tests and direct constructors."""

    return LegacyAtlasContextResolver(
        inventory={"services": {provider_id: dict(service)}},
        environ=environ or {},
    ).resolve_context(provider_id)


def metadata_from_context(
    atlas_context: AtlasContext,
    *,
    default_description: str | None = None,
    default_workspace: str = "operations",
    default_icon: str = "box",
    default_priority: str = "normal",
    default_capabilities: frozenset[ProviderCapability] | set[ProviderCapability],
) -> ProviderMetadata:
    metadata = atlas_context.metadata
    capabilities = frozenset(
        ProviderCapability(capability) for capability in metadata.capabilities
    )
    return ProviderMetadata(
        id=metadata.consumer_id.replace("_", "-"),
        name=metadata.name,
        version=metadata.version,
        description=metadata.description
        or default_description
        or _DESCRIPTION_BY_PROVIDER.get(metadata.consumer_id, ""),
        workspace=ProviderWorkspace(metadata.workspace or default_workspace),
        icon=metadata.icon or default_icon,
        priority=ProviderPriority(metadata.priority or default_priority),
        capabilities=capabilities or frozenset(default_capabilities),
    )


def base_url_from_context(
    atlas_context: AtlasContext,
    *,
    default_port: int,
) -> str:
    connection = atlas_context.connection
    if connection is None:
        raise ValueError(f"{atlas_context.consumer_id} connection is not configured.")
    if connection.base_url:
        return connection.base_url.rstrip("/") + "/"
    if not connection.host:
        raise ValueError(f"{atlas_context.consumer_id} host is not configured.")
    port = connection.port or default_port
    return f"{connection.mode}://{connection.host}:{port}/"


def tls_verification_from_context(atlas_context: AtlasContext) -> bool | str:
    connection = atlas_context.connection
    if connection is None:
        return True
    if connection.ca_bundle:
        return connection.ca_bundle
    return connection.verify_tls


def timeout_from_context(atlas_context: AtlasContext, default: float = 10.0) -> float:
    connection = atlas_context.connection
    if connection is None:
        return default
    return connection.timeout_seconds or default


def secret_value(atlas_context: AtlasContext, name: str) -> str | None:
    secret = atlas_context.secrets.get(name)
    if secret is None:
        return None
    return secret.reveal()


def legacy_service(atlas_context: AtlasContext) -> Mapping[str, Any]:
    value = atlas_context.metadata.metadata.get("legacy_service")
    if isinstance(value, Mapping):
        return value
    return {}


def context_url(atlas_context: AtlasContext, path: str, *, default_port: int) -> str:
    return urljoin(base_url_from_context(atlas_context, default_port=default_port), path.lstrip("/"))
