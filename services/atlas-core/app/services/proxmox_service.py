from __future__ import annotations

from typing import Any

from app.clients.proxmox_client import get_proxmox_client
from app.context import AtlasContext
from app.services.atlas_contexts import LegacyAtlasContextResolver


def bytes_to_gib(value: float) -> float:
    return round(value / (1024**3), 2)


def get_proxmox_status(
    atlas_context: AtlasContext | None = None,
    client: Any | None = None,
) -> dict:
    context = _proxmox_context(atlas_context)
    proxmox_client = client or get_proxmox_client(context)
    node = _proxmox_node(context)
    status = proxmox_client.nodes(node).status.get()

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


def get_proxmox_guests(
    atlas_context: AtlasContext | None = None,
    client: Any | None = None,
) -> dict:
    context = _proxmox_context(atlas_context)
    proxmox_client = client or get_proxmox_client(context)
    node = _proxmox_node(context)
    guests = []

    for vm in proxmox_client.nodes(node).qemu.get():
        vmid = vm["vmid"]
        try:
            config = proxmox_client.nodes(node).qemu(vmid).config.get()
        except Exception:  # noqa: BLE001 - optional identity enrichment fails closed
            config = {}
        guests.append(
            {
                "vmid": vmid,
                "name": vm.get("name", f"VM-{vm['vmid']}"),
                "type": "qemu",
                "status": vm.get("status", "unknown"),
                "vmgenid": config.get("vmgenid"),
                "template": bool(config.get("template", vm.get("template", 0))),
                "lock": config.get("lock") or vm.get("lock"),
                "cpu_percent": round(vm.get("cpu", 0) * 100, 2),
                "memory_used_gib": bytes_to_gib(vm.get("mem", 0)),
                "memory_total_gib": bytes_to_gib(vm.get("maxmem", 0)),
                "uptime_seconds": vm.get("uptime", 0),
            }
        )

    for container in proxmox_client.nodes(node).lxc.get():
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


def _proxmox_context(
    atlas_context: AtlasContext | None,
) -> AtlasContext:
    # Temporary compatibility seam for legacy routes and tests that call this
    # service directly before all callers are context-aware.
    return atlas_context or LegacyAtlasContextResolver().resolve_context(
        "proxmox",
    )


def _proxmox_node(atlas_context: AtlasContext) -> str:
    connection = atlas_context.connection
    if connection is None or not connection.node:
        raise RuntimeError("Proxmox node is not configured.")
    return connection.node
