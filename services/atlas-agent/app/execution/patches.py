"""Agent-owned validation and application of worker-generated patches."""

from __future__ import annotations

import hashlib
import subprocess
from dataclasses import dataclass
from pathlib import Path

from app.execution.worker_contracts import WorkerExecutionRequest, WorkerExecutionResult


class PatchApplicationError(ValueError):
    """A worker patch failed an Agent-owned safety check."""


@dataclass(frozen=True, slots=True)
class PatchApplicationOutcome:
    changed_files: tuple[str, ...]
    patch_digest: str


class WorkerPatchApplier:
    """Validate and apply only an approved worker patch to a trusted checkout."""

    def apply(
        self,
        repository_root: Path,
        request: WorkerExecutionRequest,
        result: WorkerExecutionResult,
    ) -> PatchApplicationOutcome:
        if result.execution_request_id != request.execution_request_id:
            raise PatchApplicationError("patch_request_id_mismatch")
        result.validate(request)
        if result.patch is None or result.patch_truncated:
            raise PatchApplicationError("patch_truncated")
        patch = result.patch.text
        digest = "sha256:" + hashlib.sha256(patch.encode("utf-8")).hexdigest()
        if result.patch_digest != digest:
            raise PatchApplicationError("patch_digest_mismatch")
        if result.base_repository_head is None:
            raise PatchApplicationError("patch_stale")
        current_head = self._git(repository_root, "rev-parse", "HEAD")
        if current_head != result.base_repository_head:
            raise PatchApplicationError("patch_stale")
        if "GIT binary patch" in patch:
            raise PatchApplicationError("patch_invalid")
        approved = set(request.allowed_affected_files)
        self._validate_paths(result.changed_files, approved)
        baseline = self._status(repository_root)
        if self._run_git(
            repository_root,
            ("apply", "--reverse", "--check", "--whitespace=error", "-"),
            patch,
            check=False,
        ):
            return PatchApplicationOutcome(tuple(sorted(result.changed_files)), digest)
        self._run_git(repository_root, ("apply", "--check", "--whitespace=error", "-"), patch)
        self._run_git(repository_root, ("apply", "--whitespace=error", "-"), patch)
        after = self._status(repository_root)
        delta = {
            path
            for path in set(baseline) | set(after)
            if baseline.get(path) != after.get(path)
        }
        actual = tuple(sorted(delta))
        baseline_preserved = all(after.get(path) == status for path, status in baseline.items())
        if (
            not baseline_preserved
            or set(actual) != set(result.changed_files)
            or not delta.issubset(approved)
        ):
            self._run_git(repository_root, ("apply", "-R", "-"), patch, check=False)
            raise PatchApplicationError("post_apply_scope_mismatch")
        check = subprocess.run(
            ["git", "diff", "--check"],
            cwd=repository_root,
            capture_output=True,
            text=True,
            check=False,
        )
        if check.returncode != 0:
            self._run_git(repository_root, ("apply", "-R", "-"), patch, check=False)
            raise PatchApplicationError("patch_apply_failed")
        return PatchApplicationOutcome(actual, digest)

    @staticmethod
    def _validate_paths(paths: tuple[str, ...], approved: set[str]) -> None:
        for path in paths:
            candidate = Path(path)
            if candidate.is_absolute() or ".." in candidate.parts or path not in approved:
                raise PatchApplicationError("patch_out_of_scope")

    @staticmethod
    def _status(repository_root: Path) -> dict[str, str]:
        result = subprocess.run(
            ["git", "status", "--porcelain=v1", "-z"],
            cwd=repository_root,
            capture_output=True,
            text=False,
            check=True,
        )
        records = result.stdout.decode("utf-8").split("\0")
        status: dict[str, str] = {}
        for record in records:
            if not record:
                continue
            path = record[3:]
            file_digest = "missing"
            candidate = repository_root / path
            if candidate.is_file():
                file_digest = hashlib.sha256(candidate.read_bytes()).hexdigest()
            staged = subprocess.run(
                ["git", "diff", "--cached", "--binary", "--", path],
                cwd=repository_root,
                capture_output=True,
                text=False,
                check=True,
            ).stdout
            status[path] = record[:3] + ":" + hashlib.sha256(
                file_digest.encode() + staged
            ).hexdigest()
        return status

    @staticmethod
    def _git(repository_root: Path, *arguments: str) -> str:
        result = subprocess.run(
            ["git", *arguments],
            cwd=repository_root,
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()

    @staticmethod
    def _run_git(
        repository_root: Path,
        arguments: tuple[str, ...],
        patch: str,
        *,
        check: bool = True,
    ) -> bool:
        result = subprocess.run(
            ["git", *arguments],
            cwd=repository_root,
            input=patch,
            capture_output=True,
            text=True,
            check=False,
        )
        if check and result.returncode != 0:
            raise PatchApplicationError("patch_invalid")
        return result.returncode == 0
