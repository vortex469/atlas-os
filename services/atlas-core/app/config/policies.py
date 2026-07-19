from pathlib import Path

import yaml
from pydantic import ValidationError

from app.config.policy_models import Policies

ATLAS_ROOT = Path("/opt/atlas")
POLICY_FILE = ATLAS_ROOT / "config" / "policies.yaml"


def load_policies() -> Policies:
    """Load and validate Atlas operational policies."""

    if not POLICY_FILE.exists():
        return Policies()

    with POLICY_FILE.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    try:
        return Policies.model_validate(data)
    except ValidationError as error:
        raise RuntimeError(
            f"Policy validation failed:\n{error}"
        ) from error


def get_expected_guest_state(vmid: int) -> str | None:
    policies = load_policies()

    guest = policies.proxmox.guests.get(str(vmid))

    if guest is None:
        return None

    return guest.expected


def is_expected_guest(vmid: int, state: str) -> bool:
    expected = get_expected_guest_state(vmid)

    if expected is None:
        return False

    return expected == state


def get_ignored_entities() -> list[str]:
    policies = load_policies()

    return policies.homeassistant.ignored_entities


def get_expected_container_state(name: str) -> str | None:
    policies = load_policies()

    container = policies.docker.containers.get(name)

    if container is None:
        return None

    return container.expected