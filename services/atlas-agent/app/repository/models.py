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
