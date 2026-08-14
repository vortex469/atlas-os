from unittest.mock import MagicMock

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
    assert guest["template"] is False
    assert guest["lock"] is None
