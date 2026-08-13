"""Repository inspection models."""

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class RepositorySnapshot:
    """Immutable repository state snapshot."""

    root: Path
    branch: str | None
    head_commit: str | None
    is_clean: bool
    modified_files: tuple[str, ...]
    staged_files: tuple[str, ...]
    untracked_files: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class CommitRequest:
    """One explicit, repository-scoped Git commit request."""

    repository_root: Path
    expected_branch: str | None
    expected_head: str | None
    paths: tuple[Path, ...]
    message: str


@dataclass(frozen=True, slots=True)
class CommitResult:
    """Immutable metadata for one completed local Git commit."""

    repository_root: Path
    branch: str | None
    parent_head: str | None
    commit_sha: str
    message: str
    committed_files: tuple[Path, ...]


@dataclass(frozen=True, slots=True)
class ReviewedChange:
    """Canonical metadata for one reviewed repository change."""

    path: Path
    status: str
    content_sha256: str | None = None
    deletion_marker: str | None = None
    rename_source: Path | None = None


@dataclass(frozen=True, slots=True)
class ReviewedChangeEvidence:
    """Canonical non-secret evidence for a reviewed commit boundary."""

    repository_root: Path
    expected_branch: str | None
    expected_head: str | None
    reviewed_files: tuple[Path, ...]
    commit_message: str
    changes: tuple[ReviewedChange, ...]
    fingerprint: str
