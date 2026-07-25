from pathlib import Path

import yaml
from pydantic import ValidationError

from app.config.policy_models import (
    FrigatePolicy,
    ObsidianPolicy,
    OPNsensePolicy,
    Policies,
    QdrantPolicy,
)

ATLAS_ROOT = Path("/opt/atlas")
POLICY_FILE = ATLAS_ROOT / "config" / "policies.yaml"


class PolicyLoadError(RuntimeError):
    """Raised when Atlas cannot read or validate its policy file."""


def load_policies(
    policy_file: Path | None = None,
) -> Policies:
    """Load and validate Atlas operational policies."""

    resolved_policy_file = policy_file or POLICY_FILE

    if not resolved_policy_file.exists():
        return Policies()

    try:
        with resolved_policy_file.open(
            "r",
            encoding="utf-8",
        ) as policy_stream:
            data = yaml.safe_load(policy_stream) or {}

        return Policies.model_validate(data)
    except (OSError, ValidationError, yaml.YAMLError) as error:
        raise PolicyLoadError(
            f"Atlas policy reload failed for "
            f"{resolved_policy_file}: {error}"
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

def get_expected_container_states() -> dict[str, str]:
    """Return expected states for all configured Docker containers."""

    policies = load_policies()

    return {
        name: container.expected
        for name, container in policies.docker.containers.items()
    }


def get_opnsense_policy() -> OPNsensePolicy:
    return load_policies().opnsense


def get_frigate_policy() -> FrigatePolicy:
    return load_policies().frigate


def get_obsidian_policy() -> ObsidianPolicy:
    return load_policies().obsidian


def get_qdrant_policy() -> QdrantPolicy:
    return load_policies().qdrant
