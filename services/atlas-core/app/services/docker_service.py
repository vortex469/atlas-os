from __future__ import annotations

from docker.errors import DockerException

from app.clients.docker_client import docker_connection_diagnostics, list_containers
from app.context import AtlasContext


def get_docker_status(atlas_context: AtlasContext | None = None) -> dict:
    try:
        containers = list_containers(atlas_context)

        return {
            "status": "online",
            "running": sum(container["status"] == "running" for container in containers),
            "stopped": sum(container["status"] != "running" for container in containers),
            "unhealthy": sum(container["health"] == "unhealthy" for container in containers),
            "containers": containers,
        }

    except DockerException as error:
        return {
            "status": "offline",
            "error": str(error),
            "running": 0,
            "stopped": 0,
            "unhealthy": 0,
            "containers": [],
        }


def get_docker_connection_diagnostics(atlas_context: AtlasContext) -> dict:
    return docker_connection_diagnostics(atlas_context)
