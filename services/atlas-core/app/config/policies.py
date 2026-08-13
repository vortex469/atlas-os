from __future__ import annotations

import os
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter

import yaml
from pydantic import ValidationError

from app.config.policy_models import (
    FrigatePolicy,
    IntelligencePolicy,
    N8nPolicy,
    ObsidianPolicy,
    OPNsensePolicy,
    Policies,
    PolicyReloadHealth,
    PolicyValidationDiagnostic,
    QdrantPolicy,
)

ATLAS_ROOT = Path("/opt/atlas")
DEFAULT_POLICY_FILE = ATLAS_ROOT / "data" / "config" / "policies.yaml"
DEFAULT_POLICY_TEMPLATE_FILE = ATLAS_ROOT / "config" / "policies.yaml"
POLICY_FILE = DEFAULT_POLICY_FILE
POLICY_TEMPLATE_FILE = DEFAULT_POLICY_TEMPLATE_FILE
POLICY_FILE_ENV = "ATLAS_POLICY_FILE"
POLICY_TEMPLATE_FILE_ENV = "ATLAS_POLICY_TEMPLATE_FILE"


class PolicyLoadError(RuntimeError):
    """Raised when Atlas cannot read or validate its policy file."""


def get_policy_file() -> Path:
    """Return the configured runtime policy file path."""

    if POLICY_FILE != DEFAULT_POLICY_FILE:
        return POLICY_FILE

    return Path(os.environ.get(POLICY_FILE_ENV, str(POLICY_FILE)))


def get_policy_template_file() -> Path:
    """Return the configured shipped policy template path."""

    if POLICY_TEMPLATE_FILE != DEFAULT_POLICY_TEMPLATE_FILE:
        return POLICY_TEMPLATE_FILE

    return Path(
        os.environ.get(
            POLICY_TEMPLATE_FILE_ENV,
            str(POLICY_TEMPLATE_FILE),
        ),
    )


def load_policies(
    policy_file: Path | None = None,
) -> Policies:
    """Load and validate Atlas operational policies."""

    if policy_file is not None:
        resolved_policy_file = policy_file
        if not resolved_policy_file.exists():
            return Policies()
        return _load_policy_file(resolved_policy_file)

    resolved_policy_file = ensure_runtime_policy_file()

    if not resolved_policy_file.exists():
        return Policies()

    return _load_policy_file(resolved_policy_file)


def ensure_runtime_policy_file() -> Path:
    """Initialize the configured runtime policy file from its template."""

    policy_file = get_policy_file()
    if POLICY_FILE != DEFAULT_POLICY_FILE:
        return policy_file

    if policy_file.exists():
        return policy_file

    template_file = get_policy_template_file()
    if not template_file.exists():
        return policy_file

    try:
        template_text = template_file.read_text(encoding="utf-8")
        _validate_policy_text(template_text)
        policy_file.parent.mkdir(parents=True, exist_ok=True)
        _atomic_create_policy_file(policy_file, template_text)
        _load_policy_file(policy_file)
    except FileExistsError:
        return policy_file
    except (OSError, ValidationError, yaml.YAMLError) as error:
        raise PolicyLoadError(
            "Atlas policy initialization failed for "
            f"{policy_file} from template {template_file}: {error}",
        ) from error

    return policy_file


def _load_policy_file(policy_file: Path) -> Policies:
    try:
        with policy_file.open(
            "r",
            encoding="utf-8",
        ) as policy_stream:
            data = yaml.safe_load(policy_stream) or {}

        return Policies.model_validate(data)
    except (OSError, ValidationError, yaml.YAMLError) as error:
        raise PolicyLoadError(
            f"Atlas policy reload failed for "
            f"{policy_file}: {error}",
        ) from error


def _validate_policy_text(policy_text: str) -> Policies:
    data = yaml.safe_load(policy_text) or {}
    return Policies.model_validate(data)


def _atomic_create_policy_file(
    policy_file: Path,
    policy_text: str,
) -> None:
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    file_descriptor = os.open(policy_file, flags, 0o600)
    try:
        with os.fdopen(
            file_descriptor,
            "w",
            encoding="utf-8",
        ) as policy_stream:
            policy_stream.write(policy_text)
            policy_stream.flush()
            os.fsync(policy_stream.fileno())
    except Exception:
        try:
            policy_file.unlink()
        except FileNotFoundError:
            pass
        raise

    _fsync_directory(policy_file.parent)


def _fsync_directory(directory: Path) -> None:
    directory_fd = os.open(directory, os.O_DIRECTORY)
    try:
        os.fsync(directory_fd)
    finally:
        os.close(directory_fd)


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


def get_intelligence_policy() -> IntelligencePolicy:
    return load_policies().intelligence


def get_policy_reload_health(
    policy_file: Path | None = None,
) -> PolicyReloadHealth:
    """Validate the current policy source and report reload health."""

    resolved_policy_file = policy_file or get_policy_file()
    checked_at = datetime.now(UTC)
    started_at = perf_counter()

    try:
        load_policies(policy_file)
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
