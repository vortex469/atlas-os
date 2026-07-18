from datetime import datetime, timezone
from typing import Any, Callable

from app.services.docker_service import get_docker_status
from app.services.health_service import get_health
from app.services.proxmox_service import (
    get_proxmox_guests,
    get_proxmox_status,
)
from app.services.system_service import get_system_status


def safely_collect(
    source: str,
    collector: Callable[[], Any],
) -> dict:
    try:
        return {
            "status": "online",
            "data": collector(),
        }
    except Exception as error:
        return {
            "status": "offline",
            "source": source,
            "error": str(error),
        }


def get_ops_summary() -> dict:
    services = safely_collect("service-health", get_health)
    system = safely_collect("system", get_system_status)
    docker = safely_collect("docker", get_docker_status)
    proxmox = safely_collect("proxmox", get_proxmox_status)
    guests = safely_collect("proxmox-guests", get_proxmox_guests)

    sections = {
        "services": services,
        "system": system,
        "docker": docker,
        "proxmox": proxmox,
        "guests": guests,
    }

    failed_sections = [
        name
        for name, section in sections.items()
        if section["status"] == "offline"
    ]

    service_results = services.get("data", {})

    critical_failures = [
        name
        for name, result in service_results.items()
        if result.get("critical") is True
        and result.get("status") != "online"
    ]

    warnings = [
        name
        for name, result in service_results.items()
        if result.get("critical") is not True
        and result.get("status") != "online"
    ]

    docker_data = docker.get("data", {})
    unhealthy_containers = docker_data.get("unhealthy", 0)

    if critical_failures or failed_sections:
        overall_status = "critical"
    elif warnings or unhealthy_containers:
        overall_status = "degraded"
    else:
        overall_status = "healthy"

    return {
        "atlas": overall_status,
        "release": "0.1-foundry",
        "assistant": "Orion",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "alerts": {
            "critical_services": critical_failures,
            "warnings": warnings,
            "failed_sections": failed_sections,
            "unhealthy_containers": unhealthy_containers,
        },
        **sections,
    }
