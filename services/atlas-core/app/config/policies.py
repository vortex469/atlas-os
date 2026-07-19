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


def get_expected_guest_state(vmid: int) -> str | None:
    """Return the expected state for a Proxmox guest."""

    policies = load_policies()

    return (
        policies
        .get("proxmox", {})
        .get("guests", {})
        .get(str(vmid), {})
        .get("expected")
    )


def is_expected_guest(vmid: int, state: str) -> bool:
    expected = get_expected_guest_state(vmid)

    if expected is None:
        return False

    return expected == state


def get_ignored_entities() -> list[str]:
    policies = load_policies()

    return (
        policies
        .get("homeassistant", {})
        .get("ignored_entities", [])
    )


def get_expected_container_state(name: str) -> str | None:
    policies = load_policies()

    return (
        policies
        .get("docker", {})
        .get("containers", {})
        .get(name, {})
        .get("expected")
    )