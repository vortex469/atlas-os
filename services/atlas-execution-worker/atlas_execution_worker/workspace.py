"""Disposable, request-scoped repository workspaces."""

from __future__ import annotations

import os
import shutil
import subprocess
import time
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from app.execution.worker_contracts import WorkerExecutionRequest

from .process import run_command


class WorkspaceError(RuntimeError):
    """The trusted source cannot produce a safe request workspace."""


class WorkspaceTimeout(WorkspaceError):
    """Workspace preparation exceeded its fixed setup budget."""


@dataclass(frozen=True, slots=True)
class WorkerWorkspace:
    request_id: str
    path: Path
    base_head: str


class WorkerWorkspaceManager:
    """Clone one trusted repository source into one disposable request directory."""

    def __init__(
        self,
        source_root: Path,
        workspace_root: Path,
        repository_token: str,
        *,
        trusted_repository_paths: Iterable[Path],
        git_config_path: Path,
    ) -> None:
        self._source_root_input = source_root
        self._source_root = source_root.resolve()
        self._workspace_root = workspace_root.resolve()
        self._repository_token = repository_token
        self._trusted_repository_paths = {
            path.resolve() for path in trusted_repository_paths
        }
        self._git_config_path = git_config_path.resolve()
        self._active: dict[str, WorkerWorkspace] = {}
        self._workspace_root.mkdir(parents=True, exist_ok=True)

    def prepare(self, request: WorkerExecutionRequest) -> WorkerWorkspace:
        request.validate()
        if request.repository_token != self._repository_token:
            raise WorkspaceError("repository token is not accepted")
        existing = self._active.get(request.execution_request_id)
        if existing is not None:
            if existing.base_head != request.expected_repository_head:
                raise WorkspaceError("request workspace has conflicting base head")
            return existing
        source = self._source_root
        if self._source_root_input.is_symlink() or not source.is_dir():
            raise WorkspaceError("trusted repository source is invalid")
        if source not in self._trusted_repository_paths:
            raise WorkspaceError("repository source is not configured")
        deadline = time.monotonic() + min(30.0, request.timeout_seconds)
        def remaining():
            value = deadline - time.monotonic()
            if value <= 0:
                raise WorkspaceTimeout("workspace preparation deadline exceeded")
            return value
        source_head = self._git(source, "rev-parse", "HEAD", timeout=remaining())
        if source_head != request.expected_repository_head:
            raise WorkspaceError("stale repository")
        path = self._workspace_root / request.execution_request_id
        if path.exists() or path.is_symlink():
            raise WorkspaceError("request workspace already exists")
        try:
            result = run_command(
                ["git", "clone", "--no-local", "--no-hardlinks", str(source), str(path)],
                cwd=self._workspace_root, timeout=remaining(),
                environment={**os.environ, "GIT_CONFIG_GLOBAL": str(self._git_config_path)},
            )
            if result.returncode != 0 or result.stdout.truncated or result.stderr.truncated:
                raise WorkspaceError("workspace clone failed")
            cloned_head = self._git(path, "rev-parse", "HEAD", timeout=remaining())
            if cloned_head != request.expected_repository_head:
                raise WorkspaceError("cloned workspace head does not match expected head")
        except (OSError, subprocess.TimeoutExpired, WorkspaceError) as exc:
            if path.is_dir() and not path.is_symlink():
                shutil.rmtree(path)
            if isinstance(exc, (subprocess.TimeoutExpired, WorkspaceTimeout)):
                raise WorkspaceTimeout("workspace preparation deadline exceeded") from exc
            raise WorkspaceError("workspace preparation failed") from exc
        workspace = WorkerWorkspace(request.execution_request_id, path, cloned_head)
        self._active[request.execution_request_id] = workspace
        return workspace

    def cleanup(self, request_id: str) -> None:
        workspace = self._active.pop(request_id, None)
        path = workspace.path if workspace else self._workspace_root / request_id
        if path.is_symlink() or (path.exists() and not path.is_dir()):
            raise WorkspaceError("refusing to clean non-directory workspace")
        if path.exists():
            shutil.rmtree(path)

    def quarantine(self, request_id: str) -> Path | None:
        """Move an unknown-outcome workspace aside without reusing or deleting it."""

        path = self._workspace_root / request_id
        if path.is_symlink() or (path.exists() and not path.is_dir()):
            raise WorkspaceError("refusing to quarantine non-directory workspace")
        if not path.exists():
            return None
        quarantine_root = self._workspace_root / "quarantine"
        quarantine_root.mkdir(mode=0o700, exist_ok=True)
        destination = quarantine_root / f"{request_id}.unknown"
        if destination.exists() or destination.is_symlink():
            raise WorkspaceError("unknown-outcome workspace already quarantined")
        shutil.move(str(path), str(destination))
        self._active.pop(request_id, None)
        return destination

    def _git(self, path: Path, *args: str, timeout: float = 30.0) -> str:
        try:
            result = run_command(
                ["git", "-C", str(path), *args], cwd=self._workspace_root,
                timeout=timeout, environment={**os.environ, "GIT_CONFIG_GLOBAL": str(self._git_config_path)},
            )
        except subprocess.TimeoutExpired as exc:
            raise WorkspaceTimeout("workspace Git deadline exceeded") from exc
        except OSError as exc:
            raise WorkspaceError("workspace Git unavailable") from exc
        if result.returncode != 0 or result.stdout.truncated:
            raise WorkspaceError("workspace Git failed")
        return result.stdout.text.strip()
