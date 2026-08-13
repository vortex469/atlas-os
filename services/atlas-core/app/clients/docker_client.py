from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import docker

from app.context import AtlasContext
from app.services.atlas_contexts import LegacyAtlasContextResolver


def format_uptime(started_at: str | None) -> str | None:
    if not started_at:
        return None

    started = datetime.fromisoformat(started_at.replace("Z", "+00:00"))
    elapsed = datetime.now(timezone.utc) - started

    days = elapsed.days
    hours, remainder = divmod(elapsed.seconds, 3600)
    minutes = remainder // 60

    parts = []

    if days:
        parts.append(f"{days}d")
    if hours:
        parts.append(f"{hours}h")
    if minutes or not parts:
        parts.append(f"{minutes}m")

    return " ".join(parts)


def format_ports(port_data: dict | None) -> list[str]:
    if not port_data:
        return []

    ports = []

    for container_port, bindings in port_data.items():
        if not bindings:
            ports.append(container_port)
            continue

        for binding in bindings:
            host_ip = binding.get("HostIp", "")
            host_port = binding.get("HostPort", "")

            if host_ip in {"", "0.0.0.0", "::"}:
                ports.append(f"{host_port}->{container_port}")
            else:
                ports.append(f"{host_ip}:{host_port}->{container_port}")

    return ports


def create_docker_client(atlas_context: AtlasContext) -> docker.DockerClient:
    """Construct Docker client from resolved AtlasContext only.

    Docker socket access is privileged even when the socket is mounted read-only.
    Atlas intentionally does not honor DOCKER_HOST or arbitrary environment
    resolution in this migrated path.
    """

    return docker.DockerClient(base_url=_socket_uri(atlas_context))


def docker_connection_diagnostics(atlas_context: AtlasContext) -> dict[str, Any]:
    connection = atlas_context.connection
    socket_path = _socket_path(atlas_context)
    exists = socket_path.exists()
    permission_available = _permission_available(socket_path) if exists else False
    stat_result = socket_path.stat() if exists else None

    return {
        "socket_configured": connection is not None and bool(connection.path),
        "socket_path": str(socket_path),
        "socket_exists": exists,
        "permission_available": permission_available,
        "effective_uid": _effective_uid(),
        "effective_gids": _effective_gids(),
        "socket_uid": stat_result.st_uid if stat_result is not None else None,
        "socket_gid": stat_result.st_gid if stat_result is not None else None,
        "socket_mode": oct(stat_result.st_mode & 0o777) if stat_result is not None else None,
        "privileged_local_runtime": True,
        "editable": False,
        "permission_model": "supplemental_group",
        "warning": (
            "Docker socket access is privileged; a read-only bind mount does "
            "not make the Docker API read-only."
        ),
    }


def list_containers(
    atlas_context: AtlasContext | None = None,
    client: docker.DockerClient | None = None,
) -> list[dict]:
    context = _docker_context(atlas_context)
    docker_client = client or create_docker_client(context)
    containers = []

    for container in docker_client.containers.list(all=True):
        container.reload()

        state = container.attrs.get("State", {})
        health = state.get("Health", {}).get("Status", "not-configured")

        containers.append(
            {
                "id": container.short_id,
                "name": container.name,
                "image": (
                    container.image.tags[0]
                    if container.image.tags
                    else container.image.short_id
                ),
                "status": container.status,
                "health": health,
                "uptime": (
                    format_uptime(state.get("StartedAt"))
                    if container.status == "running"
                    else None
                ),
                "restart_count": container.attrs.get("RestartCount", 0),
                "ports": format_ports(
                    container.attrs.get("NetworkSettings", {}).get("Ports")
                ),
            }
        )

    return containers


def _docker_context(atlas_context: AtlasContext | None) -> AtlasContext:
    # Temporary compatibility seam for legacy routes and direct service tests.
    # The migrated provider path passes AtlasContext explicitly.
    return atlas_context or LegacyAtlasContextResolver().resolve_context("docker")


def _socket_uri(atlas_context: AtlasContext) -> str:
    connection = atlas_context.connection
    if connection is None or connection.mode != "unix" or not connection.path:
        raise RuntimeError("Docker Unix socket is not configured.")
    return f"unix://{connection.path}"


def _socket_path(atlas_context: AtlasContext) -> Path:
    connection = atlas_context.connection
    if connection is None or not connection.path:
        return Path("/var/run/docker.sock")
    return Path(connection.path)


def _permission_available(socket_path: Path) -> bool:
    try:
        return socket_path.exists() and socket_path.is_socket()
    except OSError:
        return False


def _effective_uid() -> int | None:
    try:
        import os

        return os.geteuid()
    except OSError:
        return None


def _effective_gids() -> list[int]:
    try:
        import os

        return list(os.getgroups())
    except OSError:
        return []
