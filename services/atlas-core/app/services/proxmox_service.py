import os

from app.clients.proxmox_client import get_client


def bytes_to_gib(value: int | float) -> float:
    return round(value / (1024 ** 3), 2)


def get_proxmox_status() -> dict:
    client = get_client()
    node = os.environ["PROXMOX_NODE"]

    status = client.nodes(node).status.get()

    memory = status.get("memory", {})
    used_memory = memory.get("used", 0)
    total_memory = memory.get("total", 0)

    return {
        "status": "online",
        "node": node,
        "cpu_percent": round(status.get("cpu", 0) * 100, 2),
        "memory": {
            "used_gib": bytes_to_gib(used_memory),
            "total_gib": bytes_to_gib(total_memory),
            "percent": (
                round((used_memory / total_memory) * 100, 2)
                if total_memory
                else 0
            ),
        },
        "uptime_seconds": status.get("uptime", 0),
        "load_average": status.get("loadavg", []),
    }


def get_proxmox_guests() -> dict:
    client = get_client()
    node = os.environ["PROXMOX_NODE"]

    guests = []

    for vm in client.nodes(node).qemu.get():
        guests.append(
            {
                "vmid": vm["vmid"],
                "name": vm.get("name", f"VM-{vm['vmid']}"),
                "type": "vm",
                "status": vm.get("status", "unknown"),
                "cpu_percent": round(vm.get("cpu", 0) * 100, 2),
                "memory_used_gib": bytes_to_gib(vm.get("mem", 0)),
                "memory_total_gib": bytes_to_gib(vm.get("maxmem", 0)),
                "uptime_seconds": vm.get("uptime", 0),
            }
        )

    for container in client.nodes(node).lxc.get():
        guests.append(
            {
                "vmid": container["vmid"],
                "name": container.get(
                    "name",
                    f"CT-{container['vmid']}",
                ),
                "type": "lxc",
                "status": container.get("status", "unknown"),
                "cpu_percent": round(container.get("cpu", 0) * 100, 2),
                "memory_used_gib": bytes_to_gib(
                    container.get("mem", 0)
                ),
                "memory_total_gib": bytes_to_gib(
                    container.get("maxmem", 0)
                ),
                "uptime_seconds": container.get("uptime", 0),
            }
        )

    guests.sort(key=lambda guest: guest["vmid"])

    return {
        "node": node,
        "running": sum(
            guest["status"] == "running"
            for guest in guests
        ),
        "stopped": sum(
            guest["status"] != "running"
            for guest in guests
        ),
        "guests": guests,
    }
