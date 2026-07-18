import docker

client = docker.from_env()


def list_containers():
    containers = []

    for container in client.containers.list(all=True):
        containers.append({
            "name": container.name,
            "image": container.image.tags[0] if container.image.tags else "unknown",
            "status": container.status,
        })

    return containers
