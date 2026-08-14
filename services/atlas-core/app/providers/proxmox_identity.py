"""Opaque authoritative identity for Proxmox QEMU guests."""

from __future__ import annotations

import hashlib
import json

from app.models.resources import ProviderResourceIdentity

PROXMOX_QEMU_IDENTITY_VERSION = "proxmox-qemu-identity-v1"


def build_proxmox_qemu_identity(
    *, node: str, vmid: int | str, vmgenid: str
) -> ProviderResourceIdentity:
    values = {
        "node": str(node),
        "provider": "proxmox",
        "resource_type": "qemu",
        "vmgenid": str(vmgenid),
        "vmid": str(vmid),
        "version": PROXMOX_QEMU_IDENTITY_VERSION,
    }
    if any(not value or value != value.strip() for value in values.values()):
        raise ValueError("Proxmox QEMU identity fields must be exact and nonblank.")
    encoded = json.dumps(values, sort_keys=True, separators=(",", ":")).encode()
    return ProviderResourceIdentity(
        token=f"{PROXMOX_QEMU_IDENTITY_VERSION}:{hashlib.sha256(encoded).hexdigest()}",
        token_version=PROXMOX_QEMU_IDENTITY_VERSION,
    )
