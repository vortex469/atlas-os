"""Strict disposable-only execution-worker configuration."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path


class WorkerConfigurationError(ValueError):
    """Worker configuration is missing or unsafe."""


def write_git_config(repository_paths: list[Path], config_path: Path) -> Path:
    """Write a private deterministic Git config containing only trusted sources."""

    config_path.parent.mkdir(parents=True, mode=0o700, exist_ok=True)
    entries = [
        entry
        for path in repository_paths
        for entry in (path.resolve(), path.resolve() / ".git")
    ]
    content = "[safe]\n" + "".join(f"\tdirectory = {entry}\n" for entry in entries)
    temporary = config_path.with_suffix(".tmp")
    temporary.write_text(content, encoding="utf-8")
    temporary.chmod(0o600)
    temporary.replace(config_path)
    config_path.chmod(0o600)
    return config_path


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
    *,
    git_config_path: Path | None = None,
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
        if token in mapping:
            raise WorkerConfigurationError("repository map contains duplicate token")
        mapping[token] = resolved
    if git_config_path is not None:
        write_git_config(list(mapping.values()), git_config_path)
    for resolved in mapping.values():
        command = [
            "git",
            "-C",
            str(resolved),
            "rev-parse",
            "--is-inside-work-tree",
        ]
        environment = None
        if git_config_path is not None:
            environment = os.environ.copy()
            environment["GIT_CONFIG_GLOBAL"] = str(git_config_path)
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=False,
            env=environment,
        )
        if result.returncode != 0 or result.stdout.strip() != "true":
            raise WorkerConfigurationError("repository map source must be a git worktree")
        if result.returncode != 0 or result.stdout.strip() != "true":
            raise WorkerConfigurationError("repository map source must be a git worktree")
    return mapping


class WorkerSettings:
    """Validated worker runtime settings."""

    def __init__(self, *, enabled: bool, repository_mapping: dict[str, Path]) -> None:
        self.execution_enabled = enabled
        self.repository_mapping = repository_mapping

    @classmethod
    def from_environment(cls, *, git_config_path: Path | None = None) -> WorkerSettings:
        enabled = parse_bool(os.getenv("ATLAS_EXECUTION_WORKER_EXECUTION_ENABLED"))
        mapping = load_repository_mapping(git_config_path=git_config_path)
        if enabled and not mapping:
            raise WorkerConfigurationError(
                "execution enablement requires ATLAS_EXECUTION_WORKER_REPOSITORY_MAP"
            )
        return cls(enabled=enabled, repository_mapping=mapping)
