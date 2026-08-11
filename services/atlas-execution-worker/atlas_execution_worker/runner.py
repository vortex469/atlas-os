"""Disabled-gated workspace runner and deterministic patch collection."""

from __future__ import annotations

import hashlib
import subprocess
import time
from pathlib import Path

from app.execution.worker_contracts import (
    RC1_SMOKE_MARKER,
    RC1_SMOKE_TARGET,
    BoundedOutput,
    WorkerAttestation,
    WorkerExecutionIntent,
    WorkerExecutionRequest,
    WorkerExecutionResult,
    WorkerExecutionStatus,
    WorkerFailureCode,
)

from .workspace import WorkerWorkspaceManager, WorkspaceError

MAX_CAPTURE_BYTES = 1_048_576
MAX_PATCH_BYTES = 4_194_304


class WorkspaceExecutionRunner:
    """Run only in disposable workspaces, and only when explicitly enabled."""

    def __init__(self, manager: WorkerWorkspaceManager, *, enabled: bool = False) -> None:
        self._manager = manager
        self._enabled = enabled

    def execute(self, request: WorkerExecutionRequest) -> WorkerExecutionResult:
        request.validate()
        started = time.monotonic()
        try:
            workspace = self._manager.prepare(request)
        except WorkspaceError as exc:
            failure = (
                WorkerFailureCode.STALE_REPOSITORY
                if "stale" in str(exc)
                else WorkerFailureCode.INVALID_REQUEST
            )
            return self._result(request, failure, started)
        if not self._enabled:
            self._manager.cleanup(request.execution_request_id)
            return self._result(request, WorkerFailureCode.WORKER_UNAVAILABLE, started, base=workspace.base_head)
        try:
            cwd = workspace.path / request.working_directory
            if not cwd.resolve().is_relative_to(workspace.path.resolve()):
                return self._result(request, WorkerFailureCode.INVALID_REQUEST, started, base=workspace.base_head)
            if request.execution_intent == WorkerExecutionIntent.RC1_VALIDATION_SMOKE:
                try:
                    self._run_rc1_smoke(workspace.path)
                except WorkspaceError:
                    return self._result(
                        request,
                        WorkerFailureCode.INVALID_REQUEST,
                        started,
                        base=workspace.base_head,
                        workspace_head=self._git(workspace.path, "rev-parse", "HEAD"),
                    )
                result = self._collect_direct_change(
                    request, workspace.path, workspace.base_head, started
                )
                return result
            process = subprocess.run(
                list(request.argv),
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=request.timeout_seconds,
                shell=False,
                check=False,
            )
            result = self._collect(request, workspace.path, workspace.base_head, process, started)
            return result
        except subprocess.TimeoutExpired as exc:
            return self._result(
                request,
                WorkerFailureCode.TIMEOUT,
                started,
                return_code=None,
                stdout=self._bounded(exc.stdout),
                stderr=self._bounded(exc.stderr),
                base=workspace.base_head,
            )
        finally:
            self._manager.cleanup(request.execution_request_id)

    @staticmethod
    def _run_rc1_smoke(root: Path) -> None:
        target = root / RC1_SMOKE_TARGET
        if not target.is_file() or target.is_symlink():
            raise WorkspaceError("RC1 validation smoke target is missing")
        if not target.resolve().is_relative_to(root.resolve()):
            raise WorkspaceError("RC1 validation smoke target escapes workspace")
        content = target.read_text(encoding="utf-8")
        if RC1_SMOKE_MARKER in content:
            raise WorkspaceError("RC1 validation smoke marker already exists")
        suffix = "" if content.endswith("\n") else "\n"
        target.write_text(
            f"{content}{suffix}{RC1_SMOKE_MARKER}\n",
            encoding="utf-8",
        )

    def _collect_direct_change(
        self,
        request: WorkerExecutionRequest,
        root: Path,
        base_head: str,
        started: float,
    ) -> WorkerExecutionResult:
        changed = self._changed_files(root)
        if changed != (RC1_SMOKE_TARGET,):
            return self._result(
                request,
                WorkerFailureCode.OUT_OF_SCOPE_CHANGES,
                started,
                base=base_head,
                workspace_head=self._git(root, "rev-parse", "HEAD"),
            )
        patch_text = self._patch(root)
        patch = self._bounded(patch_text)
        return self._result(
            request,
            None,
            started,
            status=WorkerExecutionStatus.SUCCEEDED,
            return_code=0,
            base=base_head,
            workspace_head=self._git(root, "rev-parse", "HEAD"),
            changed_files=changed,
            patch=patch,
            patch_digest="sha256:" + hashlib.sha256(patch_text.encode()).hexdigest(),
            patch_size=len(patch_text.encode()),
        )

    def _collect(self, request: WorkerExecutionRequest, root: Path, base_head: str, process: subprocess.CompletedProcess[str], started: float) -> WorkerExecutionResult:
        subprocess.run(["git", "-C", str(root), "add", "--all", "--"], check=True, capture_output=True, text=True, shell=False)
        changed = self._changed_files(root)
        allowed = set(request.allowed_affected_files)
        failure = None
        status = WorkerExecutionStatus.SUCCEEDED if process.returncode == 0 else WorkerExecutionStatus.BLOCKED
        if not set(changed).issubset(allowed):
            failure = WorkerFailureCode.OUT_OF_SCOPE_CHANGES
            status = WorkerExecutionStatus.BLOCKED
        elif process.returncode != 0:
            failure = WorkerFailureCode.CODEX_FAILED
        patch_text = self._patch(root)
        if process.returncode == 0 and not patch_text:
            failure = WorkerFailureCode.NO_COMMITTABLE_CHANGES
            status = WorkerExecutionStatus.BLOCKED
        patch = self._bounded(patch_text)
        return self._result(
            request,
            failure,
            started,
            status=status,
            return_code=process.returncode,
            stdout=self._bounded(process.stdout),
            stderr=self._bounded(process.stderr),
            changed_files=changed,
            patch=patch,
            patch_digest="sha256:" + hashlib.sha256(patch_text.encode()).hexdigest() if patch_text else None,
            patch_size=len(patch_text.encode()) if patch_text else None,
            base=base_head,
            workspace_head=self._git(root, "rev-parse", "HEAD"),
        )

    @staticmethod
    def _changed_files(root: Path) -> tuple[str, ...]:
        result = subprocess.run(["git", "-C", str(root), "status", "--porcelain=v1"], check=True, capture_output=True, text=True, shell=False)
        files = []
        for line in result.stdout.splitlines():
            name = line[3:]
            if " -> " in name:
                name = name.split(" -> ", 1)[1]
            path = Path(name)
            if path.is_absolute() or ".." in path.parts:
                raise WorkspaceError("changed path escapes workspace")
            files.append(path.as_posix())
        return tuple(sorted(set(files)))

    @staticmethod
    def _patch(root: Path) -> str:
        result = subprocess.run(["git", "-C", str(root), "diff", "--binary", "--no-ext-diff", "--no-color", "HEAD"], check=True, capture_output=True, text=True, shell=False)
        return result.stdout

    @staticmethod
    def _git(root: Path, *args: str) -> str:
        return subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True, text=True, shell=False).stdout.strip()

    @staticmethod
    def _bounded(value: str | bytes | None) -> BoundedOutput:
        text = value.decode(errors="replace") if isinstance(value, bytes) else (value or "")
        raw = text.encode()
        if len(raw) <= MAX_CAPTURE_BYTES:
            return BoundedOutput(text, False, len(raw))
        return BoundedOutput(raw[:MAX_CAPTURE_BYTES].decode(errors="ignore"), True, len(raw))

    @staticmethod
    def _result(request: WorkerExecutionRequest, failure: WorkerFailureCode | None, started: float, *, status: WorkerExecutionStatus = WorkerExecutionStatus.BLOCKED, return_code: int | None = None, stdout: BoundedOutput | None = None, stderr: BoundedOutput | None = None, changed_files: tuple[str, ...] = (), patch: BoundedOutput | None = None, patch_digest: str | None = None, patch_size: int | None = None, base: str | None = None, workspace_head: str | None = None) -> WorkerExecutionResult:
        return WorkerExecutionResult(
            schema_version=1,
            execution_request_id=request.execution_request_id,
            status=status,
            return_code=return_code,
            stdout=stdout or BoundedOutput(""),
            stderr=stderr or BoundedOutput(""),
            changed_files=tuple(sorted(changed_files)),
            patch_digest=patch_digest,
            patch_size_bytes=patch_size,
            patch_truncated=patch.truncated if patch else False,
            duration_seconds=max(0.0, time.monotonic() - started),
            failure_code=failure,
            workspace_head=workspace_head,
            worker_attestation=WorkerAttestation(10001, True, True, "0000000000000000", "runsc-squid"),
            base_repository_head=base,
            patch=patch,
        )
