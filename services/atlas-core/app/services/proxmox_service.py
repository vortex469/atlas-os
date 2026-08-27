from __future__ import annotations

from typing import Any

from app.clients.proxmox_client import get_proxmox_client
from app.context import AtlasContext
from app.services.atlas_contexts import LegacyAtlasContextResolver

_UNAVAILABLE = object()
_UNKNOWN = object()


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
        except Exception:  # noqa: BLE001 - evidence remains explicitly unavailable
            config = None
        template, _ = _reconcile_template(config, vm)
        lock, lock_resolved = _reconcile_lock(config, vm)
        guests.append(
            {
                "vmid": vmid,
                "name": vm.get("name", f"VM-{vm['vmid']}"),
                "type": "qemu",
                "status": vm.get("status", "unknown"),
                "vmgenid": None if config is None else config.get("vmgenid"),
                "template": template,
                "lock": lock,
                "migrating": lock == "migrate" if lock_resolved else None,
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


def _source_value(source: dict | None, key: str, validator) -> object:
    if source is None or key not in source:
        return _UNAVAILABLE
    value = source[key]
    return value if validator(value) else _UNKNOWN


def _reconcile(
    config_value: object, inventory_value: object
) -> tuple[object | None, bool]:
    if config_value is _UNAVAILABLE:
        candidate = inventory_value
    elif inventory_value is _UNAVAILABLE:
        candidate = config_value
    elif config_value is _UNKNOWN or inventory_value is _UNKNOWN:
        candidate = _UNKNOWN
    elif config_value == inventory_value:
        candidate = config_value
    else:
        candidate = _UNKNOWN
    return (None, False) if candidate in {_UNAVAILABLE, _UNKNOWN} else (candidate, True)


def _reconcile_template(
    config: dict | None, inventory: dict
) -> tuple[bool | None, bool]:
    def normalize(value: object) -> bool | object:
        if type(value) is bool:
            return value
        if type(value) is int and value in {0, 1}:
            return bool(value)
        return _UNKNOWN

    config_value = _source_value(config, "template", lambda value: normalize(value) is not _UNKNOWN)
    inventory_value = _source_value(
        inventory, "template", lambda value: normalize(value) is not _UNKNOWN
    )
    if config_value not in {_UNAVAILABLE, _UNKNOWN}:
        config_value = normalize(config_value)
    if inventory_value not in {_UNAVAILABLE, _UNKNOWN}:
        inventory_value = normalize(inventory_value)
    value, resolved = _reconcile(config_value, inventory_value)
    return value, resolved


def _reconcile_lock(
    config: dict | None, inventory: dict
) -> tuple[str | None, bool]:
    valid = lambda value: value is None or isinstance(value, str)
    config_value = _source_value(config, "lock", valid)
    inventory_value = _source_value(inventory, "lock", valid)
    if "migrate" in {config_value, inventory_value}:
        return "migrate", True
    value, resolved = _reconcile(config_value, inventory_value)
    return value, resolved


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
