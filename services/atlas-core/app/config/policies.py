from pathlib import Path
from typing import Any

import yaml

ATLAS_ROOT = Path("/opt/atlas")
POLICY_FILE = ATLAS_ROOT / "config" / "policies.yaml"


def load_policies() -> dict[str, Any]:
    """Load Atlas operational policies."""

    if not POLICY_FILE.exists():
        return {}

    with POLICY_FILE.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    return data or {}


_POLICIES = load_policies()


def get_expected_guest_state(vmid: int) -> str | None:
    """Return the expected state for a Proxmox guest."""

    return (
        _POLICIES
        .get("proxmox", {})
        .get("guests", {})
        .get(str(vmid), {})
        .get("expected")
    )


def is_expected_guest(vmid: int, state: str) -> bool:
    """Return True if the guest is in its expected state."""

    expected = get_expected_guest_state(vmid)

    if expected is None:
        return False

    return expected == state


def get_ignored_entities() -> list[str]:
    return (
        _POLICIES
        .get("homeassistant", {})
        .get("ignored_entities", [])
    )


def get_expected_container_state(name: str) -> str | None:
    return (
        _POLICIES
        .get("docker", {})
        .get("containers", {})
        .get(name, {})
        .get("expected")
    )
