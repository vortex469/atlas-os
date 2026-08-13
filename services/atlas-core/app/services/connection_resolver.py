from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from app.config.provider_connections import (
    ProviderConnectionStoreError,
    get_provider_connection_values,
)
from app.config.settings import Settings
from app.config.settings import settings as default_settings
from app.context import ConnectionContext, MetadataContext

_CONNECTION_FIELDS = frozenset(
    {
        "mode",
        "host",
        "port",
        "base_url",
        "path",
        "node",
        "health_endpoint",
        "expected_status",
        "verify_tls",
        "ca_bundle",
        "timeout_seconds",
    },
)


class ConnectionContextResolver:
    """Resolve Atlas connection context from runtime stores and legacy sources."""

    def __init__(
        self,
        settings: Settings = default_settings,
        inventory: Mapping[str, Any] | None = None,
        runtime_overrides: Mapping[str, Mapping[str, Any]] | None = None,
        runtime_connection_file: Path | None = None,
    ) -> None:
        self._settings = settings
        self._inventory = inventory or {}
        self._runtime_overrides = runtime_overrides or {}
        self._runtime_connection_file = runtime_connection_file

    def resolve_connection(
        self,
        metadata: MetadataContext,
    ) -> ConnectionContext | None:
        provider_id = metadata.consumer_id
        legacy_connection = self._legacy_connection(metadata)
        runtime_values = self._runtime_values(provider_id)
        if not runtime_values:
            return legacy_connection
        if legacy_connection is None:
            return _connection_from_mapping(runtime_values, "runtime")
        return _merge_runtime_connection(legacy_connection, runtime_values)

    def _runtime_values(self, provider_id: str) -> Mapping[str, Any]:
        runtime_values: dict[str, Any] = {}
        try:
            runtime_values.update(
                get_provider_connection_values(
                    provider_id,
                    self._runtime_connection_file,
                ),
            )
        except ProviderConnectionStoreError as error:
            raise RuntimeError("runtime provider connection store is invalid.") from error
        runtime_values.update(self._runtime_overrides.get(provider_id, {}))
        return runtime_values

    def _legacy_connection(
        self,
        metadata: MetadataContext,
    ) -> ConnectionContext | None:
        provider_id = metadata.consumer_id
        if provider_id == "proxmox":
            return ConnectionContext(
                mode="https",
                configured=True,
                source="atlas_yaml",
                host=self._settings.proxmox.host,
                port=self._settings.proxmox.port,
                node=self._settings.proxmox.node,
                verify_tls=self._settings.proxmox.verify_ssl,
                metadata={
                    "field_sources": {
                        "mode": "atlas_yaml",
                        "host": "atlas_yaml",
                        "port": "atlas_yaml",
                        "node": "atlas_yaml",
                        "verify_tls": "atlas_yaml",
                    },
                },
            )

        if provider_id == "home_assistant":
            parsed_url = urlparse(self._settings.home_assistant.url)
            mode = "https" if parsed_url.scheme == "https" else "http"
            return ConnectionContext(
                mode=mode,
                configured=True,
                source="atlas_yaml",
                base_url=self._settings.home_assistant.url,
                host=parsed_url.hostname,
                port=parsed_url.port,
                verify_tls=mode == "https",
                metadata={
                    "field_sources": {
                        "mode": "atlas_yaml",
                        "base_url": "atlas_yaml",
                        "host": "atlas_yaml",
                        "port": "atlas_yaml" if parsed_url.port is not None else "missing",
                        "verify_tls": "atlas_yaml",
                    },
                },
            )

        if provider_id == "docker":
            socket_uri = self._settings.docker.socket
            socket_path = socket_uri.removeprefix("unix://")
            return ConnectionContext(
                mode="unix",
                configured=bool(socket_path),
                source="atlas_yaml",
                path=socket_path,
                timeout_seconds=10.0,
                metadata={
                    "socket_uri": socket_uri,
                    "privileged_local_runtime": True,
                    "editable": False,
                    "permission_model": "supplemental_group",
                    "warning": (
                        "Docker socket access is privileged even when the "
                        "bind mount is read-only."
                    ),
                    "field_sources": {
                        "mode": "atlas_yaml",
                        "path": "atlas_yaml",
                        "timeout_seconds": "default",
                    },
                },
            )

        service = self._service(provider_id)
        if service is None:
            return None

        return _connection_from_mapping(service, "inventory")

    def _service(self, provider_id: str) -> Mapping[str, Any] | None:
        services = self._inventory.get("services", {})
        if not isinstance(services, Mapping):
            return None
        service = services.get(provider_id)
        if not isinstance(service, Mapping):
            return None
        return service


def _connection_from_mapping(
    value: Mapping[str, Any],
    source: str,
) -> ConnectionContext:
    protocol = str(value.get("protocol", value.get("mode", "http"))).lower()
    mode = "https" if protocol == "https" else "http"
    if protocol in {"unix", "local", "custom"}:
        mode = protocol
    expected_status = _expected_status(value.get("expected_status"))
    expected_statuses = _expected_statuses(value.get("expected_status"))
    verify_tls = bool(value.get("verify_tls", mode == "https"))
    field_sources = _field_sources_from_mapping(value, source)
    if "mode" not in field_sources:
        field_sources["mode"] = source if ("protocol" in value or "mode" in value) else "default"
    if "verify_tls" not in field_sources:
        field_sources["verify_tls"] = source if "verify_tls" in value else "default"
    return ConnectionContext(
        mode=mode,
        configured=True,
        source=source,  # type: ignore[arg-type]
        host=_string_or_none(value.get("host")),
        port=_int_or_none(value.get("port")),
        base_url=_string_or_none(value.get("base_url")),
        path=_string_or_none(value.get("path")),
        node=_string_or_none(value.get("node")),
        health_endpoint=_string_or_none(value.get("health_endpoint")),
        expected_status=expected_status,
        verify_tls=verify_tls,
        ca_bundle=_string_or_none(value.get("ca_bundle")),
        timeout_seconds=float(value.get("timeout_seconds", 10.0)),
        metadata={
            "role": value.get("role"),
            "expected_statuses": expected_statuses,
            "field_sources": field_sources,
        },
    )


def _merge_runtime_connection(
    legacy_connection: ConnectionContext,
    runtime_values: Mapping[str, Any],
) -> ConnectionContext:
    updates = _sparse_connection_updates(runtime_values)
    if not updates:
        return legacy_connection

    connection_data = legacy_connection.model_dump()
    field_sources = dict(connection_data.get("metadata", {}).get("field_sources", {}))
    for key, value in updates.items():
        connection_data[key] = value
        field_sources[key] = "runtime"

    connection_data["source"] = "runtime"
    metadata = dict(connection_data.get("metadata", {}))
    metadata["field_sources"] = field_sources
    connection_data["metadata"] = metadata
    return ConnectionContext.model_validate(connection_data)


def _sparse_connection_updates(value: Mapping[str, Any]) -> dict[str, Any]:
    updates: dict[str, Any] = {}
    if "mode" in value or "protocol" in value:
        protocol = str(value.get("mode", value.get("protocol"))).lower()
        updates["mode"] = "https" if protocol == "https" else "http"
        if protocol in {"unix", "local", "custom"}:
            updates["mode"] = protocol
    for key in _CONNECTION_FIELDS - {"mode"}:
        if key not in value:
            continue
        if key in {"host", "base_url", "path", "node", "health_endpoint", "ca_bundle"}:
            updates[key] = _string_or_none(value.get(key))
        elif key in {"port", "expected_status"}:
            updates[key] = _int_or_none(value.get(key))
        elif key == "verify_tls":
            updates[key] = bool(value.get(key))
        elif key == "timeout_seconds":
            updates[key] = float(value.get(key))
    return updates


def _field_sources_from_mapping(value: Mapping[str, Any], source: str) -> dict[str, str]:
    field_sources: dict[str, str] = {}
    for key in _CONNECTION_FIELDS:
        if key in value:
            field_sources[key] = source
    if "protocol" in value:
        field_sources["mode"] = source
    return field_sources


def _string_or_none(value: object) -> str | None:
    if value is None:
        return None
    return str(value)


def _int_or_none(value: object) -> int | None:
    if value is None:
        return None
    return int(value)


def _expected_status(value: object) -> int | None:
    if isinstance(value, list) and value:
        return int(value[0])
    if isinstance(value, int):
        return value
    return None


def _expected_statuses(value: object) -> tuple[int, ...]:
    if isinstance(value, list):
        return tuple(int(item) for item in value)
    if isinstance(value, int):
        return (int(value),)
    return (200,)
