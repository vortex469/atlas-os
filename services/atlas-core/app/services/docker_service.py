from docker.errors import DockerException

from app.clients.docker_client import list_containers


def get_docker_status() -> dict:
    try:
        containers = list_containers()

        return {
            "status": "online",
            "running": sum(
                container["status"] == "running"
                for container in containers
            ),
            "stopped": sum(
                container["status"] != "running"
                for container in containers
            ),
            "unhealthy": sum(
                container["health"] == "unhealthy"
                for container in containers
            ),
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
