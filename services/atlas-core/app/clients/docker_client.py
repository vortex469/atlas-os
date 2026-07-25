from datetime import datetime, timezone

import docker


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


def list_containers() -> list[dict]:
    containers = []
    client = docker.from_env()

    for container in client.containers.list(all=True):
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
