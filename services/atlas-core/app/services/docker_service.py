from app.clients.docker_client import list_containers


def get_docker_status():
    containers = list_containers()

    return {
        "running": sum(c["status"] == "running" for c in containers),
        "stopped": sum(c["status"] != "running" for c in containers),
        "containers": containers,
    }
