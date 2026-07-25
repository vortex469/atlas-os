from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter

import yaml
from pydantic import ValidationError

from app.config.policy_models import (
    FrigatePolicy,
    N8nPolicy,
    ObsidianPolicy,
    OPNsensePolicy,
    Policies,
    PolicyReloadHealth,
    PolicyValidationDiagnostic,
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


def get_n8n_policy() -> N8nPolicy:
    return load_policies().n8n


def get_policy_reload_health(
    policy_file: Path | None = None,
) -> PolicyReloadHealth:
    """Validate the current policy source and report reload health."""

    resolved_policy_file = policy_file or POLICY_FILE
    checked_at = datetime.now(UTC)
    started_at = perf_counter()

    try:
        load_policies(resolved_policy_file)
    except PolicyLoadError as error:
        diagnostics = _policy_diagnostics(error)
        return PolicyReloadHealth(
            status="degraded",
            source_exists=resolved_policy_file.exists(),
            checked_at=checked_at,
            duration_ms=round(
                (perf_counter() - started_at) * 1000,
                2,
            ),
            error=(
                "Policy reload failed with "
                f"{len(diagnostics)} diagnostic(s)."
            ),
            diagnostics=diagnostics,
        )

    return PolicyReloadHealth(
        status="healthy",
        source_exists=resolved_policy_file.exists(),
        checked_at=checked_at,
        loaded_at=datetime.now(UTC),
        duration_ms=round(
            (perf_counter() - started_at) * 1000,
            2,
        ),
    )


def _policy_diagnostics(
    error: PolicyLoadError,
) -> list[PolicyValidationDiagnostic]:
    cause = error.__cause__

    if isinstance(cause, ValidationError):
        return [
            PolicyValidationDiagnostic(
                path=".".join(
                    str(part)
                    for part in item["loc"]
                )
                or "$",
                error_type=str(item["type"]),
                message=str(item["msg"]),
            )
            for item in cause.errors(
                include_url=False,
                include_context=False,
                include_input=False,
            )
        ]

    if isinstance(cause, yaml.MarkedYAMLError):
        mark = cause.problem_mark
        return [
            PolicyValidationDiagnostic(
                path="$",
                error_type="yaml_syntax",
                message=(
                    cause.problem
                    or "The policy file contains invalid YAML."
                ),
                line=mark.line + 1 if mark is not None else None,
                column=(
                    mark.column + 1
                    if mark is not None
                    else None
                ),
            ),
        ]

    if isinstance(cause, OSError):
        return [
            PolicyValidationDiagnostic(
                path="$",
                error_type="file_error",
                message="Atlas could not read the policy file.",
            ),
        ]

    return [
        PolicyValidationDiagnostic(
            path="$",
            error_type="policy_error",
            message="Atlas could not validate the policy file.",
        ),
    ]
