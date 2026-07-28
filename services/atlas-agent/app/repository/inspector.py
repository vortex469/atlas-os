"""Git repository inspector implementation."""

import subprocess
from pathlib import Path

from app.repository.exceptions import (
    InvalidRepositoryError,
    RepositoryInspectionError,
)
from app.repository.models import RepositorySnapshot


class GitInspector:
    """Inspect a Git repository without modifying it."""

    def __init__(self, repository_root: Path) -> None:
        """Initialize and validate a repository path."""

        candidate = repository_root.expanduser()

        if not candidate.exists():
            raise InvalidRepositoryError(
                f"Repository path does not exist: {candidate}"
            )

        if not candidate.is_dir():
            raise InvalidRepositoryError(
                f"Repository path is not a directory: {candidate}"
            )

        self.repository_root = candidate.resolve()

        result = self._run_git(
            "rev-parse",
            "--is-inside-work-tree",
            check=False,
        )
        if result.returncode != 0 or result.stdout.strip() != "true":
            raise InvalidRepositoryError(
                f"Path is not inside a Git work tree: {self.repository_root}"
            )

    def inspect(self) -> RepositorySnapshot:
        """Return an immutable snapshot of the repository state."""

        root = Path(
            self._run_git("rev-parse", "--show-toplevel").stdout.strip()
        ).resolve()
        branch = self._get_branch()
        head_commit = self._get_head_commit()

        modified_files, staged_files, untracked_files = self._parse_status(
            self._run_git("status", "--porcelain=v1", "-z").stdout
        )

        return RepositorySnapshot(
            root=root,
            branch=branch,
            head_commit=head_commit,
            is_clean=not (
                modified_files
                or staged_files
                or untracked_files
            ),
            modified_files=modified_files,
            staged_files=staged_files,
            untracked_files=untracked_files,
        )

    def _run_git(
        self,
        *arguments: str,
        check: bool = True,
    ) -> subprocess.CompletedProcess[str]:
        """Run one Git command inside the configured repository."""

        try:
            result = subprocess.run(
                ["git", *arguments],
                cwd=self.repository_root,
                check=False,
                capture_output=True,
                text=True,
            )
        except OSError as exc:
            raise RepositoryInspectionError(
                f"Unable to execute Git in {self.repository_root}: {exc}"
            ) from exc

        if check and result.returncode != 0:
            detail = result.stderr.strip() or result.stdout.strip()
            message = (
                f"Git command failed with exit code {result.returncode}: "
                f"git {' '.join(arguments)}"
            )
            if detail:
                message = f"{message}: {detail}"

            raise RepositoryInspectionError(message)

        return result

    def _get_branch(self) -> str | None:
        """Return the current branch or None for detached HEAD."""

        result = self._run_git(
            "symbolic-ref",
            "--quiet",
            "--short",
            "HEAD",
            check=False,
        )

        if result.returncode == 0:
            return result.stdout.strip()

        if result.returncode == 1:
            return None

        raise RepositoryInspectionError(
            "Unable to determine the current Git branch"
        )

    def _get_head_commit(self) -> str | None:
        """Return the HEAD commit or None for a repository without commits."""

        result = self._run_git(
            "rev-parse",
            "--verify",
            "HEAD",
            check=False,
        )

        if result.returncode == 0:
            return result.stdout.strip()

        if result.returncode == 128:
            return None

        raise RepositoryInspectionError(
            "Unable to determine the current HEAD commit"
        )

    def _parse_status(
        self,
        output: str,
    ) -> tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...]]:
        """Parse NUL-delimited porcelain-v1 status output."""

        modified_files: list[str] = []
        staged_files: list[str] = []
        untracked_files: list[str] = []

        records = output.split("\0")
        index = 0

        while index < len(records):
            record = records[index]
            if not record:
                index += 1
                continue

            if len(record) < 4 or record[2] != " ":
                raise RepositoryInspectionError(
                    f"Malformed Git status record: {record!r}"
                )

            index_status = record[0]
            worktree_status = record[1]
            path = record[3:]

            if index_status == "?" and worktree_status == "?":
                untracked_files.append(path)
            else:
                if index_status not in {" ", "?"}:
                    staged_files.append(path)

                if worktree_status not in {" ", "?"}:
                    modified_files.append(path)

            if index_status in {"R", "C"} or worktree_status in {"R", "C"}:
                index += 1
                if index >= len(records) or not records[index]:
                    raise RepositoryInspectionError(
                        "Malformed Git rename or copy status record"
                    )

            index += 1

        return (
            tuple(modified_files),
            tuple(staged_files),
            tuple(untracked_files),
        )
