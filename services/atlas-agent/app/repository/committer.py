"""Explicit local Git commit orchestration."""

from __future__ import annotations

import subprocess
from pathlib import Path

from app.repository.exceptions import (
    RepositoryCommitError,
    RepositoryCommitValidationError,
)
from app.repository.inspector import GitInspector
from app.repository.models import CommitRequest, CommitResult

_DENIED_COMMIT_PATH_PARTS = frozenset({".git", "jcode", "logs"})


class GitCommitter:
    """Create one local commit from an exact reviewed path allowlist."""

    def __init__(self, repository_root: Path) -> None:
        self.repository_root = repository_root.resolve(strict=False)
        self._inspector = GitInspector(self.repository_root)

    def commit(self, request: CommitRequest) -> CommitResult:
        """Validate, stage, commit, and verify one explicit path set."""

        paths = self._normalize_paths(request)
        message = self._normalize_message(request.message)
        before = self._inspector.inspect()

        if before.root != self.repository_root:
            raise RepositoryCommitValidationError(
                "Commit repository root does not match the Git work tree"
            )
        if before.branch != request.expected_branch:
            raise RepositoryCommitValidationError(
                "Repository branch differs from the approved plan"
            )
        if before.head_commit != request.expected_head:
            raise RepositoryCommitValidationError(
                "Repository HEAD differs from the approved plan"
            )

        self._run_git("add", "-A", "--", *(str(path) for path in paths))

        staged = self._inspector.inspect()
        staged_paths = tuple(sorted(Path(path) for path in staged.staged_files))
        if staged_paths != paths:
            raise RepositoryCommitValidationError(
                "Staged files do not match the reviewed commit paths"
            )

        self._run_git(
            "commit",
            "--only",
            "-m",
            message,
            "--",
            *(str(path) for path in paths),
        )

        commit_sha = self._run_git("rev-parse", "HEAD").stdout.strip()
        committed_message = self._run_git(
            "log",
            "-1",
            "--format=%s",
            "HEAD",
        ).stdout.rstrip("\n")
        committed_files = tuple(
            sorted(
                Path(path)
                for path in self._run_git(
                    "diff-tree",
                    "--root",
                    "--no-commit-id",
                    "--name-only",
                    "-r",
                    "-M",
                    "-z",
                    "HEAD",
                ).stdout.split("\0")
                if path
            )
        )

        if committed_message != message or committed_files != paths:
            raise RepositoryCommitError(
                "Created commit metadata does not match the reviewed request"
            )

        return CommitResult(
            repository_root=self.repository_root,
            branch=request.expected_branch,
            parent_head=request.expected_head,
            commit_sha=commit_sha,
            message=committed_message,
            committed_files=committed_files,
        )

    def _normalize_paths(self, request: CommitRequest) -> tuple[Path, ...]:
        request_root = request.repository_root.resolve(strict=False)
        if request_root != self.repository_root:
            raise RepositoryCommitValidationError(
                "Commit request repository root does not match the committer"
            )
        if not request.paths:
            raise RepositoryCommitValidationError(
                "Commit paths must not be empty"
            )

        normalized: list[Path] = []
        repository_parts = self.repository_root.parts
        for path in request.paths:
            if path.is_absolute() or path == Path(".") or ".." in path.parts:
                raise RepositoryCommitValidationError(
                    f"Commit path must be repository-relative: {path}"
                )
            normalized_path = Path(*path.parts) if path.parts else Path("")
            if not normalized_path.parts:
                raise RepositoryCommitValidationError("Commit path must not be empty")
            if normalized_path.parts[0] in _DENIED_COMMIT_PATH_PARTS:
                raise RepositoryCommitValidationError(
                    f"Commit paths must not include {normalized_path.parts[0]}/"
                )
            resolved_path = (self.repository_root / normalized_path).resolve(strict=False)
            if not resolved_path.is_relative_to(self.repository_root):
                raise RepositoryCommitValidationError(
                    "Commit path must not escape the repository"
                )
            if (
                "agent-state" in normalized_path.parts
                or (
                    "agent-state" in repository_parts
                    and normalized_path.parts[0] in {"agent-state", "state"}
                )
            ):
                raise RepositoryCommitValidationError(
                    "Commit paths must not include Atlas Agent state directories"
                )
            if normalized_path in normalized:
                raise RepositoryCommitValidationError(
                    f"Commit paths must be unique: {normalized_path}"
                )
            normalized.append(normalized_path)

        return tuple(sorted(normalized))

    @staticmethod
    def _normalize_message(message: str) -> str:
        if any(ord(character) < 32 or ord(character) == 127 for character in message):
            raise RepositoryCommitValidationError(
                "Commit message must not contain control characters"
            )
        normalized = " ".join(message.split())
        if not normalized:
            raise RepositoryCommitValidationError(
                "Commit message must not be blank"
            )
        if normalized != message:
            raise RepositoryCommitValidationError(
                "Commit message must already be normalized"
            )
        return normalized

    def _run_git(self, *arguments: str) -> subprocess.CompletedProcess[str]:
        try:
            result = subprocess.run(
                ["git", *arguments],
                cwd=self.repository_root,
                check=False,
                capture_output=True,
                text=True,
            )
        except OSError as exc:
            raise RepositoryCommitError(
                f"Unable to execute Git in {self.repository_root}: {exc}"
            ) from exc

        if result.returncode != 0:
            detail = result.stderr.strip() or result.stdout.strip()
            message = (
                f"Git command failed with exit code {result.returncode}: "
                f"git {' '.join(arguments)}"
            )
            if detail:
                message = f"{message}: {detail}"
            raise RepositoryCommitError(message)

        return result
