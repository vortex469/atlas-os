"""Explicit local Git commit orchestration."""

from __future__ import annotations

import subprocess
from hashlib import sha256
from pathlib import Path

from app.repository.exceptions import (
    RepositoryCommitError,
    RepositoryCommitValidationError,
)
from app.repository.inspector import GitInspector
from app.repository.models import CommitRequest, CommitResult, ReviewedChangeEvidence

_DENIED_COMMIT_PATH_PARTS = frozenset({".git", "jcode", "logs"})


class GitCommitter:
    """Create one local commit from an exact reviewed path allowlist."""

    def __init__(self, repository_root: Path) -> None:
        self.repository_root = repository_root.resolve(strict=False)
        self._inspector = GitInspector(self.repository_root)

    def commit(
        self,
        request: CommitRequest,
        *,
        reviewed_evidence: ReviewedChangeEvidence | None = None,
    ) -> CommitResult:
        """Validate, stage, commit, and verify one explicit path set."""

        paths = self._normalize_paths(request)
        message = self._normalize_message(request.message)
        if reviewed_evidence is not None and not (
            reviewed_evidence.repository_root.resolve(strict=False) == self.repository_root
            and reviewed_evidence.expected_branch == request.expected_branch
            and reviewed_evidence.expected_head == request.expected_head
            and reviewed_evidence.reviewed_files == paths
            and reviewed_evidence.commit_message == message
            and tuple(change.path for change in reviewed_evidence.changes) == paths
        ):
            raise RepositoryCommitValidationError(
                "Reviewed evidence does not match the commit request"
            )
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
        if (
            staged.branch != request.expected_branch
            or staged.head_commit != request.expected_head
        ):
            raise RepositoryCommitValidationError(
                "Repository identity changed while staging the reviewed paths"
            )
        staged_tree = self._run_git("write-tree").stdout.strip()
        if reviewed_evidence is not None:
            self._validate_reviewed_tree(staged_tree, reviewed_evidence)

        self._run_git(
            "commit",
            "-m",
            message,
        )

        commit_sha = self._run_git("rev-parse", "HEAD").stdout.strip()
        parents = self._run_git(
            "show", "-s", "--format=%P", commit_sha
        ).stdout.strip().split()
        expected_parents = [request.expected_head] if request.expected_head else []
        committed_tree = self._run_git(
            "show", "-s", "--format=%T", commit_sha
        ).stdout.strip()
        committed_message = self._run_git(
            "log",
            "-1",
            "--format=%s",
            commit_sha,
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
                    commit_sha,
                ).stdout.split("\0")
                if path
            )
        )

        after = self._inspector.inspect()
        if (
            parents != expected_parents
            or committed_tree != staged_tree
            or after.branch != request.expected_branch
            or after.head_commit != commit_sha
            or committed_message != message
            or committed_files != paths
        ):
            raise RepositoryCommitError(
                "Created commit metadata or content does not match the reviewed request"
            )

        return CommitResult(
            repository_root=self.repository_root,
            branch=after.branch,
            parent_head=parents[0] if parents else None,
            commit_sha=commit_sha,
            message=committed_message,
            committed_files=committed_files,
        )

    def _validate_reviewed_tree(
        self, tree: str, evidence: ReviewedChangeEvidence
    ) -> None:
        """Compare staged blob bytes with evidence already bound to approval."""

        for change in evidence.changes:
            entry = self._run_git(
                "ls-tree", "-z", tree, "--", str(change.path)
            ).stdout
            if change.deletion_marker == "deleted" and change.content_sha256 is None:
                matches = not entry
            elif change.deletion_marker is None and change.content_sha256 is not None:
                metadata, separator, path = entry.partition("\t")
                fields = metadata.split()
                matches = (
                    bool(separator)
                    and path == f"{change.path}\0"
                    and len(fields) == 3
                    and fields[0] in {"100644", "100755"}
                    and fields[1] == "blob"
                )
                if matches:
                    matches = self._blob_digest(fields[2]) == change.content_sha256
            else:
                matches = False
            if not matches:
                raise RepositoryCommitValidationError(
                    "Staged content differs from the approved review evidence"
                )

    def _blob_digest(self, object_id: str) -> str:
        # Binary output preserves CRLF, non-UTF-8 bytes and terminal newlines.
        try:
            result = subprocess.run(
                ["git", "cat-file", "blob", object_id],
                cwd=self.repository_root,
                check=False,
                capture_output=True,
            )
        except OSError as exc:
            raise RepositoryCommitError("Unable to read staged Git blob") from exc
        if result.returncode != 0:
            raise RepositoryCommitError("Unable to read staged Git blob")
        return sha256(result.stdout).hexdigest()

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
