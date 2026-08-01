from __future__ import annotations

import copy
import fcntl
import os
import tempfile
from pathlib import Path
from typing import Any

import yaml

from app.config import policies as policy_config
from app.config.policy_models import Policies

PROXMOX_GUEST_EXPECTATIONS = frozenset({"running", "stopped", "ignored"})


class ResourcePolicyValidationError(ValueError):
    """Raised when a resource policy write is invalid."""


def update_proxmox_guest_expectation(
    vmid: int | str,
    expectation: str,
    policy_file: Path | None = None,
) -> str:
    """Atomically persist Proxmox monitoring intent for one guest."""

    normalized_vmid = str(vmid).strip()
    normalized_expectation = expectation.strip().lower()

    if not normalized_vmid:
        raise ResourcePolicyValidationError("resource_id must not be empty.")

    if normalized_expectation not in PROXMOX_GUEST_EXPECTATIONS:
        raise ResourcePolicyValidationError(
            "Proxmox guest expectation must be one of: "
            f"{', '.join(sorted(PROXMOX_GUEST_EXPECTATIONS))}."
        )

    if policy_file is None:
        resolved_policy_file = policy_config.ensure_runtime_policy_file()
    else:
        resolved_policy_file = policy_file
    resolved_policy_file.parent.mkdir(parents=True, exist_ok=True)
    lock_file = resolved_policy_file.with_name(
        f".{resolved_policy_file.name}.lock"
    )

    with lock_file.open("w", encoding="utf-8") as lock_stream:
        fcntl.flock(lock_stream.fileno(), fcntl.LOCK_EX)
        try:
            current_policy = _load_policy_mapping(resolved_policy_file)
            updated_policy = _with_proxmox_guest_expectation(
                current_policy,
                normalized_vmid,
                normalized_expectation,
            )
            Policies.model_validate(updated_policy)
            _atomic_write_policy(updated_policy, resolved_policy_file)
        finally:
            fcntl.flock(lock_stream.fileno(), fcntl.LOCK_UN)

    return normalized_expectation


def _load_policy_mapping(policy_file: Path) -> dict[str, Any]:
    if not policy_file.exists():
        return {}

    policy_config.load_policies(policy_file)

    with policy_file.open("r", encoding="utf-8") as policy_stream:
        data = yaml.safe_load(policy_stream) or {}

    if not isinstance(data, dict):
        raise ResourcePolicyValidationError(
            "Atlas policy file must contain a mapping."
        )

    return data


def _with_proxmox_guest_expectation(
    policy: dict[str, Any],
    vmid: str,
    expectation: str,
) -> dict[str, Any]:
    updated_policy = copy.deepcopy(policy)
    proxmox_policy = updated_policy.setdefault("proxmox", {})

    if not isinstance(proxmox_policy, dict):
        raise ResourcePolicyValidationError(
            "proxmox policy section must be a mapping."
        )

    guests_policy = proxmox_policy.setdefault("guests", {})

    if not isinstance(guests_policy, dict):
        raise ResourcePolicyValidationError(
            "proxmox.guests policy section must be a mapping."
        )

    guests_policy[vmid] = {"expected": expectation}
    return updated_policy


def _atomic_write_policy(
    policy: dict[str, Any],
    policy_file: Path,
) -> None:
    temp_path: Path | None = None

    try:
        file_descriptor, temp_name = tempfile.mkstemp(
            prefix=f".{policy_file.name}.",
            suffix=".tmp",
            dir=policy_file.parent,
        )
        temp_path = Path(temp_name)

        with os.fdopen(
            file_descriptor,
            "w",
            encoding="utf-8",
        ) as policy_stream:
            yaml.safe_dump(
                policy,
                policy_stream,
                sort_keys=False,
            )
            policy_stream.flush()
            os.fsync(policy_stream.fileno())

        policy_config.load_policies(temp_path)
        os.replace(temp_path, policy_file)
        _fsync_directory(policy_file.parent)
    finally:
        if temp_path is not None and temp_path.exists():
            temp_path.unlink()


def _fsync_directory(directory: Path) -> None:
    directory_fd = os.open(directory, os.O_DIRECTORY)
    try:
        os.fsync(directory_fd)
    finally:
        os.close(directory_fd)
