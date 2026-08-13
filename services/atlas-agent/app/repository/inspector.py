"""Git repository inspector implementation."""

import json
import subprocess
from hashlib import sha256
from pathlib import Path

from app.repository.exceptions import (
    InvalidRepositoryError,
    RepositoryInspectionError,
)
from app.repository.models import (
    RepositorySnapshot,
    ReviewedChange,
    ReviewedChangeEvidence,
)


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

    def reviewed_change_evidence(
        self,
        *,
        reviewed_files: tuple[Path, ...],
        expected_branch: str | None,
        expected_head: str | None,
        commit_message: str,
        excluded_roots: tuple[str, ...] = ("logs",),
    ) -> ReviewedChangeEvidence:
        """Return canonical evidence for the exact reviewed changed path set."""

        root = Path(
            self._run_git("rev-parse", "--show-toplevel").stdout.strip()
        ).resolve()
        branch = self._get_branch()
        head = self._get_head_commit()
        if branch != expected_branch:
            raise RepositoryInspectionError(
                "Repository branch differs from the reviewed commit evidence"
            )
        if head != expected_head:
            raise RepositoryInspectionError(
                "Repository HEAD differs from the reviewed commit evidence"
            )

        records = self._status_records()
        non_excluded = {
            record["path"]: record
            for record in records
            if not self._is_excluded(record["path"], excluded_roots)
        }
        expected_paths = tuple(sorted(self._normalize_relative_paths(reviewed_files)))
        actual_paths = tuple(sorted(non_excluded))
        if actual_paths != expected_paths:
            raise RepositoryInspectionError(
                "Repository changed paths differ from the reviewed commit evidence"
            )

        return self._build_reviewed_change_evidence(
            root=root,
            expected_branch=expected_branch,
            expected_head=expected_head,
            commit_message=commit_message,
            expected_paths=expected_paths,
            records=non_excluded,
        )

    def reviewed_candidate_change_evidence(
        self,
        *,
        reviewed_files: tuple[Path, ...],
        baseline_status: tuple[tuple[str, str], ...],
        post_execution_status: tuple[tuple[str, str], ...],
        expected_branch: str | None,
        expected_head: str | None,
        commit_message: str,
    ) -> ReviewedChangeEvidence:
        """Return evidence for a candidate-owned delta over a dirty baseline."""

        root = Path(
            self._run_git("rev-parse", "--show-toplevel").stdout.strip()
        ).resolve()
        branch = self._get_branch()
        head = self._get_head_commit()
        if branch != expected_branch:
            raise RepositoryInspectionError(
                "Repository branch differs from the reviewed commit evidence"
            )
        if head != expected_head:
            raise RepositoryInspectionError(
                "Repository HEAD differs from the reviewed commit evidence"
            )

        from app.execution.patches import WorkerPatchApplier

        baseline = {Path(path): status for path, status in baseline_status}
        expected_post = {Path(path): status for path, status in post_execution_status}
        current = {
            Path(path): status
            for path, status in WorkerPatchApplier.capture_baseline(
                self.repository_root
            )
        }
        if current != expected_post:
            raise RepositoryInspectionError(
                "Repository status differs from the validated candidate evidence"
            )
        if any(current.get(path) != status for path, status in baseline.items()):
            raise RepositoryInspectionError(
                "Candidate baseline paths differ from the validated evidence"
            )

        expected_paths = tuple(sorted(self._normalize_relative_paths(reviewed_files)))
        owned_paths = tuple(sorted(set(current) - set(baseline)))
        if owned_paths != expected_paths:
            raise RepositoryInspectionError(
                "Candidate-owned paths differ from the validated review evidence"
            )

        records = self._status_records()
        current_records = {
            record["path"]: record
            for record in records
            if record["path"] in set(expected_paths)
        }
        return self._build_reviewed_change_evidence(
            root=root,
            expected_branch=expected_branch,
            expected_head=expected_head,
            commit_message=commit_message,
            expected_paths=expected_paths,
            records=current_records,
        )

    def _build_reviewed_change_evidence(
        self,
        *,
        root: Path,
        expected_branch: str | None,
        expected_head: str | None,
        commit_message: str,
        expected_paths: tuple[Path, ...],
        records: dict[Path, dict[str, object]],
    ) -> ReviewedChangeEvidence:
        changes = tuple(
            self._reviewed_change(records[path], root)
            for path in expected_paths
        )
        manifest = {
            "version": 1,
            "repository_root": str(root),
            "expected_branch": expected_branch,
            "expected_head": expected_head,
            "reviewed_files": [str(path) for path in expected_paths],
            "commit_message": commit_message,
            "changes": [
                {
                    "path": str(change.path),
                    "status": change.status,
                    "content_sha256": change.content_sha256,
                    "deletion_marker": change.deletion_marker,
                    "rename_source": (
                        str(change.rename_source)
                        if change.rename_source is not None
                        else None
                    ),
                }
                for change in changes
            ],
        }
        payload = json.dumps(
            manifest,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return ReviewedChangeEvidence(
            repository_root=root,
            expected_branch=expected_branch,
            expected_head=expected_head,
            reviewed_files=expected_paths,
            commit_message=commit_message,
            changes=changes,
            fingerprint=sha256(payload).hexdigest(),
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

    def _status_records(self) -> tuple[dict[str, object], ...]:
        output = self._run_git("status", "--porcelain=v1", "-z").stdout
        records: list[dict[str, object]] = []
        fields = output.split("\0")
        index = 0
        while index < len(fields):
            record = fields[index]
            if not record:
                index += 1
                continue
            if len(record) < 4 or record[2] != " ":
                raise RepositoryInspectionError(
                    f"Malformed Git status record: {record!r}"
                )
            index_status = record[0]
            worktree_status = record[1]
            path = Path(record[3:])
            rename_source = None
            if index_status in {"R", "C"} or worktree_status in {"R", "C"}:
                index += 1
                if index >= len(fields) or not fields[index]:
                    raise RepositoryInspectionError(
                        "Malformed Git rename or copy status record"
                    )
                rename_source = Path(fields[index])
            records.append(
                {
                    "index_status": index_status,
                    "worktree_status": worktree_status,
                    "path": path,
                    "rename_source": rename_source,
                }
            )
            index += 1
        return tuple(records)

    @staticmethod
    def _normalize_relative_paths(paths: tuple[Path, ...]) -> tuple[Path, ...]:
        normalized: list[Path] = []
        for path in paths:
            candidate = Path(path)
            if candidate.is_absolute() or candidate == Path(".") or ".." in candidate.parts:
                raise RepositoryInspectionError(
                    f"Reviewed path must be repository-relative: {path}"
                )
            if candidate in normalized:
                raise RepositoryInspectionError(
                    f"Reviewed paths must be unique: {path}"
                )
            normalized.append(candidate)
        if not normalized:
            raise RepositoryInspectionError("Reviewed paths must not be empty")
        return tuple(normalized)

    @staticmethod
    def _is_excluded(path: Path, excluded_roots: tuple[str, ...]) -> bool:
        return bool(path.parts) and path.parts[0] in excluded_roots

    @staticmethod
    def _reviewed_change(record: dict[str, object], root: Path) -> ReviewedChange:
        path = record["path"]
        if not isinstance(path, Path):
            raise RepositoryInspectionError("Malformed Git status path")
        index_status = str(record["index_status"])
        worktree_status = str(record["worktree_status"])
        status = f"{index_status}{worktree_status}"
        rename_source = record["rename_source"]
        if rename_source is not None and not isinstance(rename_source, Path):
            raise RepositoryInspectionError("Malformed Git rename source")
        absolute_path = root / path
        if index_status == "D" or worktree_status == "D" or not absolute_path.exists():
            return ReviewedChange(
                path=path,
                status=status,
                deletion_marker="deleted",
                rename_source=rename_source,
            )
        if not absolute_path.is_file():
            raise RepositoryInspectionError(
                f"Reviewed path is not a regular file: {path}"
            )
        return ReviewedChange(
            path=path,
            status=status,
            content_sha256=sha256(absolute_path.read_bytes()).hexdigest(),
            rename_source=rename_source,
        )
