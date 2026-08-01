from __future__ import annotations

from collections.abc import Mapping
from typing import Any
from urllib.parse import urlparse

from app.config.settings import Settings
from app.config.settings import settings as default_settings
from app.context import ConnectionContext, MetadataContext


class ConnectionContextResolver:
    """Resolve Atlas connection context from current legacy sources."""

    def __init__(
        self,
        settings: Settings = default_settings,
        inventory: Mapping[str, Any] | None = None,
        runtime_overrides: Mapping[str, Mapping[str, Any]] | None = None,
    ) -> None:
        self._settings = settings
        self._inventory = inventory or {}
        self._runtime_overrides = runtime_overrides or {}

    def resolve_connection(
        self,
        metadata: MetadataContext,
    ) -> ConnectionContext | None:
        provider_id = metadata.consumer_id
        runtime_override = self._runtime_overrides.get(provider_id)
        if runtime_override is not None:
            return _connection_from_mapping(runtime_override, "runtime")

        if provider_id == "proxmox":
            return ConnectionContext(
                mode="https",
                configured=True,
                source="settings",
                host=self._settings.proxmox.host,
                port=self._settings.proxmox.port,
                node=self._settings.proxmox.node,
                verify_tls=self._settings.proxmox.verify_ssl,
            )

        if provider_id == "home_assistant":
            parsed_url = urlparse(self._settings.home_assistant.url)
            mode = "https" if parsed_url.scheme == "https" else "http"
            return ConnectionContext(
                mode=mode,
                configured=True,
                source="settings",
                base_url=self._settings.home_assistant.url,
                host=parsed_url.hostname,
                port=parsed_url.port,
                verify_tls=mode == "https",
            )

        if provider_id == "docker":
            socket_uri = self._settings.docker.socket
            socket_path = socket_uri.removeprefix("unix://")
            return ConnectionContext(
                mode="unix",
                configured=bool(socket_path),
                source="settings",
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
        expected_status=_expected_status(value.get("expected_status")),
        verify_tls=bool(value.get("verify_tls", mode == "https")),
        ca_bundle=_string_or_none(value.get("ca_bundle")),
        metadata={
            "role": value.get("role"),
            "expected_statuses": _expected_statuses(value.get("expected_status")),
        },
    )


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
