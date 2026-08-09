"""Disposable, request-scoped repository workspaces."""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from app.execution.worker_contracts import WorkerExecutionRequest


class WorkspaceError(RuntimeError):
    """The trusted source cannot produce a safe request workspace."""


@dataclass(frozen=True, slots=True)
class WorkerWorkspace:
    request_id: str
    path: Path
    base_head: str


class WorkerWorkspaceManager:
    """Clone one trusted repository source into one disposable request directory."""

    def __init__(self, source_root: Path, workspace_root: Path, repository_token: str) -> None:
        self._source_root_input = source_root
        self._source_root = source_root.resolve()
        self._workspace_root = workspace_root.resolve()
        self._repository_token = repository_token
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
        source_head = self._git(source, "rev-parse", "HEAD")
        if source_head != request.expected_repository_head:
            raise WorkspaceError("stale repository")
        path = self._workspace_root / request.execution_request_id
        if path.exists() or path.is_symlink():
            raise WorkspaceError("request workspace already exists")
        subprocess.run(
            ["git", "clone", "--no-local", "--no-hardlinks", str(source), str(path)],
            check=True,
            capture_output=True,
            text=True,
            shell=False,
        )
        cloned_head = self._git(path, "rev-parse", "HEAD")
        if cloned_head != request.expected_repository_head:
            shutil.rmtree(path, ignore_errors=True)
            raise WorkspaceError("cloned workspace head does not match expected head")
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

    @staticmethod
    def _git(path: Path, *args: str) -> str:
        result = subprocess.run(
            ["git", "-C", str(path), *args],
            check=True,
            capture_output=True,
            text=True,
            shell=False,
        )
        return result.stdout.strip()
