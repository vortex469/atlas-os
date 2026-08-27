from unittest.mock import MagicMock

import pytest

from app.services.proxmox_service import get_proxmox_guests


def _context():
    context = MagicMock()
    context.connection.node = "pve1"
    return context


def test_qemu_inventory_collects_provider_native_identity_fields() -> None:
    client = MagicMock()
    client.nodes.return_value.qemu.get.return_value = [
        {"vmid": 101, "name": "atlas", "status": "running"}
    ]
    client.nodes.return_value.qemu.return_value.config.get.return_value = {
        "vmgenid": "11111111-1111-1111-1111-111111111111",
        "template": 0,
        "lock": None,
    }
    client.nodes.return_value.lxc.get.return_value = []
    guest = get_proxmox_guests(_context(), client)["guests"][0]
    assert guest["type"] == "qemu"
    assert guest["vmid"] == 101
    assert guest["vmgenid"] == "11111111-1111-1111-1111-111111111111"
    assert guest["template"] is False
    assert guest["lock"] is None
    assert guest["migrating"] is False


def test_unavailable_qemu_config_preserves_inventory_without_identity() -> None:
    client = MagicMock()
    client.nodes.return_value.qemu.get.return_value = [
        {"vmid": 101, "name": "atlas", "status": "running"}
    ]
    client.nodes.return_value.qemu.return_value.config.get.side_effect = RuntimeError(
        "permission denied"
    )
    client.nodes.return_value.lxc.get.return_value = []
    guest = get_proxmox_guests(_context(), client)["guests"][0]
    assert guest["type"] == "qemu"
    assert guest["vmgenid"] is None
    assert guest["template"] is None
    assert guest["lock"] is None
    assert guest["migrating"] is None


@pytest.mark.parametrize(
    ("config", "inventory", "template", "lock", "migrating"),
    [
        ({"template": 0, "lock": None}, {"template": False, "lock": None}, False, None, False),
        ({"template": 1, "lock": "backup"}, {"template": True, "lock": "backup"}, True, "backup", False),
        ({"template": 0, "lock": None}, {"template": True, "lock": "backup"}, None, None, None),
        ({}, {"template": False, "lock": None}, False, None, False),
        ({"template": False}, {"lock": "migrate"}, False, "migrate", True),
        ({"template": False, "lock": None}, {"lock": "migrate"}, False, "migrate", True),
        (None, {"template": False, "lock": "migrate"}, False, "migrate", True),
        (None, {}, None, None, None),
    ],
)
def test_qemu_authoritative_evidence_contradiction_matrix(
    config: dict | None,
    inventory: dict,
    template: bool | None,
    lock: str | None,
    migrating: bool | None,
) -> None:
    client = MagicMock()
    client.nodes.return_value.qemu.get.return_value = [
        {"vmid": 101, "status": "running", **inventory}
    ]
    if config is None:
        client.nodes.return_value.qemu.return_value.config.get.side_effect = RuntimeError
    else:
        client.nodes.return_value.qemu.return_value.config.get.return_value = config
    client.nodes.return_value.lxc.get.return_value = []

    guest = get_proxmox_guests(_context(), client)["guests"][0]

    assert guest["template"] is template
    assert guest["lock"] == lock
    assert guest["migrating"] is migrating
