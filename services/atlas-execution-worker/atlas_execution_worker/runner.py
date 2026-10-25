"""Disabled-gated workspace runner and deterministic patch collection."""

from __future__ import annotations

import hashlib
import os
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

from .process import CapturedCommand, CommandTimeout, run_command
from .workspace import WorkerWorkspaceManager, WorkspaceError, WorkspaceTimeout

MAX_CAPTURE_BYTES = 1_048_576
MAX_PATCH_BYTES = 4_194_304
MAX_PATCH_CAPTURE_BYTES = min(MAX_PATCH_BYTES, MAX_CAPTURE_BYTES)


class PatchTooLarge(WorkspaceError):
    """The complete patch cannot fit the existing bounded text contract."""


class RepositoryControlChanged(WorkspaceError):
    """Model work changed repository revision or execution-control metadata."""


def _git_argv(root: Path, *args: str) -> list[str]:
    return ["git", "-C", str(root), "-c", "core.hooksPath=/dev/null", "-c", "core.fsmonitor=false", *args]


def _git_environment() -> dict[str, str]:
    return {**os.environ, "GIT_NO_REPLACE_OBJECTS":"1", "GIT_CONFIG_NOSYSTEM":"1"}


def _read_control_digest(root: Path) -> str:
    git = root / ".git"
    if not git.is_dir() or git.is_symlink():
        raise RepositoryControlChanged("unsupported repository metadata")
    replace = git / "refs/replace"
    if replace.is_symlink() or (replace.exists() and (not replace.is_dir() or next(replace.iterdir(), None) is not None)):
        raise RepositoryControlChanged("replacement refs are unsupported")
    names = ["HEAD","config","packed-refs","commondir","gitdir","shallow","info/attributes","info/grafts","objects/info/alternates"]
    head = git / "HEAD"
    if head.is_symlink():
        raise RepositoryControlChanged("unsupported HEAD")
    with head.open("rb") as stream:
        text = stream.read(65537)
    if text.startswith(b"ref: "):
        reference = text[5:].strip().decode("utf-8")
        if not reference.startswith("refs/") or ".." in Path(reference).parts:
            raise RepositoryControlChanged("unsupported HEAD ref")
        names.append(reference)
    digest = hashlib.sha256()
    for name in names:
        path = git / name
        if path.is_symlink() or not path.resolve().is_relative_to(git.resolve()):
            raise RepositoryControlChanged("repository metadata escapes clone")
        if not path.exists():
            digest.update(name.encode() + b":missing\0")
            continue
        if not path.is_file():
            raise RepositoryControlChanged("unsupported repository metadata")
        with path.open("rb") as stream:
            data = stream.read(65537)
        if len(data) > 65536:
            raise RepositoryControlChanged("repository metadata exceeds bound")
        digest.update(name.encode() + b":" + data + b"\0")
    return digest.hexdigest()


def _control_digest(root: Path) -> str:
    try:
        return _read_control_digest(root)
    except (OSError, UnicodeError) as exc:
        raise RepositoryControlChanged("unreadable repository metadata") from exc


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
                WorkerFailureCode.TIMEOUT
                if isinstance(exc, WorkspaceTimeout) else WorkerFailureCode.STALE_REPOSITORY
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
            controls = _control_digest(workspace.path)
            process = run_command(
                list(request.argv), cwd=cwd, timeout=request.timeout_seconds,
            )
            if _control_digest(workspace.path) != controls or self._git(workspace.path, "rev-parse", "HEAD") != workspace.base_head:
                raise RepositoryControlChanged("repository revision or metadata changed")
            result = self._collect(request, workspace.path, workspace.base_head, process, started)
            return result
        except RepositoryControlChanged:
            return self._result(request, WorkerFailureCode.STALE_REPOSITORY, started, base=workspace.base_head)
        except PatchTooLarge:
            return self._result(request, WorkerFailureCode.PATCH_TOO_LARGE, started, base=workspace.base_head)
        except WorkspaceError:
            return self._result(request, WorkerFailureCode.INVALID_REQUEST, started, base=workspace.base_head)
        except subprocess.TimeoutExpired as exc:
            return self._result(
                request,
                WorkerFailureCode.TIMEOUT,
                started,
                return_code=None,
                stdout=exc.stdout_capture if isinstance(exc, CommandTimeout) else self._bounded(exc.stdout),
                stderr=exc.stderr_capture if isinstance(exc, CommandTimeout) else self._bounded(exc.stderr),
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

    def _collect(self, request: WorkerExecutionRequest, root: Path, base_head: str, process: CapturedCommand, started: float) -> WorkerExecutionResult:
        staged = run_command(_git_argv(root, "add", "--all", "--"), cwd=root, timeout=30, environment=_git_environment())
        if staged.returncode != 0:
            raise WorkspaceError("workspace staging failed")
        changed = self._changed_files(root)
        allowed = set(request.allowed_affected_files)
        failure = None
        status = WorkerExecutionStatus.SUCCEEDED if process.returncode == 0 else WorkerExecutionStatus.BLOCKED
        if not set(changed).issubset(allowed) or len(changed) > 64:
            return self._result(
                request, WorkerFailureCode.OUT_OF_SCOPE_CHANGES, started,
                base=base_head, workspace_head=self._git(root, "rev-parse", "HEAD"),
                changed_files=changed if len(changed) <= 64 else (),
                stdout=process.stdout, stderr=process.stderr,
            )
        if process.returncode != 0:
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
            stdout=process.stdout,
            stderr=process.stderr,
            changed_files=changed,
            patch=patch,
            patch_digest="sha256:" + hashlib.sha256(patch_text.encode()).hexdigest() if patch_text else None,
            patch_size=len(patch_text.encode()) if patch_text else None,
            base=base_head,
            workspace_head=self._git(root, "rev-parse", "HEAD"),
        )

    @staticmethod
    def _changed_files(root: Path) -> tuple[str, ...]:
        result = run_command(_git_argv(root, "status", "--porcelain=v1", "-z", "--untracked-files=all"), cwd=root, timeout=30, environment=_git_environment())
        if result.returncode != 0 or result.stdout.truncated:
            raise WorkspaceError("unsupported repository status")
        records = result.stdout.text.encode("utf-8").split(b"\x00")
        if records[-1] != b"":
            raise WorkspaceError("unterminated repository status")
        files = set()
        index = 0
        try:
            while index < len(records) - 1:
                record = records[index]
                if len(record) < 4 or record[2:3] != b" ":
                    raise WorkspaceError("invalid repository status")
                names = [record[3:]]
                index += 1
                if b"R" in record[:2] or b"C" in record[:2]:
                    if index >= len(records) - 1:
                        raise WorkspaceError("incomplete rename status")
                    names.append(records[index])
                    index += 1
                for raw in names:
                    name = raw.decode("utf-8")
                    path = Path(name)
                    if not name or path.is_absolute() or ".." in path.parts or "\\" in name:
                        raise WorkspaceError("changed path escapes supported scope")
                    files.add(path.as_posix())
        except UnicodeDecodeError as exc:
            raise WorkspaceError("changed path is not UTF-8") from exc
        return tuple(sorted(files))

    @staticmethod
    def _patch(root: Path) -> str:
        result = run_command(
            _git_argv(root, "diff", "--binary", "--no-ext-diff", "--no-textconv", "--no-color", "HEAD"),
            cwd=root, timeout=30.0, output_limit=MAX_PATCH_CAPTURE_BYTES, environment=_git_environment(),
        )
        if result.returncode != 0:
            raise WorkspaceError("patch generation failed")
        if result.stdout.truncated:
            raise PatchTooLarge("patch exceeds bounded transport text")
        return result.stdout.text

    @staticmethod
    def _git(root: Path, *args: str) -> str:
        result = run_command(_git_argv(root, *args), cwd=root, timeout=30, environment=_git_environment())
        if result.returncode != 0 or result.stdout.truncated:
            raise WorkspaceError("workspace metadata unavailable")
        return result.stdout.text.strip()

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
            worker_attestation=WorkerAttestation(
                10001,
                True,
                True,
                "0000000000000000",
                "runsc-squid+atlas-workspace",
            ),
            base_repository_head=base,
            patch=patch,
        )
