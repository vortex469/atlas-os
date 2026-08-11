"""Strict disposable-only execution-worker configuration."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path


class WorkerConfigurationError(ValueError):
    """Worker configuration is missing or unsafe."""


def parse_bool(value: str | None, *, default: bool = False) -> bool:
    if value is None:
        return default
    normalized = value.strip().lower()
    if normalized == "true":
        return True
    if normalized == "false":
        return False
    raise WorkerConfigurationError("ATLAS_EXECUTION_WORKER_EXECUTION_ENABLED must be true or false")


def load_repository_mapping(
    value: str | None = None,
) -> dict[str, Path]:
    """Load opaque-token to trusted-git-source mappings from token=path pairs."""

    raw = os.getenv("ATLAS_EXECUTION_WORKER_REPOSITORY_MAP", "") if value is None else value
    mapping: dict[str, Path] = {}
    for item in filter(None, (part.strip() for part in raw.split(","))):
        try:
            token, source = item.split("=", 1)
        except ValueError as exc:
            raise WorkerConfigurationError("repository map entries must be token=path") from exc
        token = token.strip()
        path = Path(source.strip()).expanduser()
        if not token or "/" in token or "\\" in token or not path.is_absolute():
            raise WorkerConfigurationError("repository map token/path is unsafe")
        resolved = path.resolve()
        if path.is_symlink() or not resolved.is_dir():
            raise WorkerConfigurationError("repository map source must be a real directory")
        result = subprocess.run(
            [
                "git",
                "-c",
                f"safe.directory={resolved}",
                "-C",
                str(resolved),
                "rev-parse",
                "--is-inside-work-tree",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0 or result.stdout.strip() != "true":
            raise WorkerConfigurationError("repository map source must be a git worktree")
        if token in mapping:
            raise WorkerConfigurationError("repository map contains duplicate token")
        mapping[token] = resolved
    return mapping


class WorkerSettings:
    """Validated worker runtime settings."""

    def __init__(self, *, enabled: bool, repository_mapping: dict[str, Path]) -> None:
        self.execution_enabled = enabled
        self.repository_mapping = repository_mapping

    @classmethod
    def from_environment(cls) -> WorkerSettings:
        enabled = parse_bool(os.getenv("ATLAS_EXECUTION_WORKER_EXECUTION_ENABLED"))
        mapping = load_repository_mapping()
        if enabled and not mapping:
            raise WorkerConfigurationError(
                "execution enablement requires ATLAS_EXECUTION_WORKER_REPOSITORY_MAP"
            )
        return cls(enabled=enabled, repository_mapping=mapping)
