"""Immutable planning models."""

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class RoadmapCheckpoint:
    """Explicit roadmap checkpoint supplied to the planning engine."""

    identifier: str
    title: str
    goal: str
    scope_items: tuple[str, ...] = ()
    affected_files: tuple[Path, ...] = ()
    required_tests: tuple[str, ...] = ()
    risks: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class PlanRisk:
    """One traceable implementation risk."""

    code: str
    summary: str
    source: str


@dataclass(frozen=True, slots=True)
class ImplementationPlan:
    """Validated implementation plan tied to repository state."""

    checkpoint_id: str
    title: str
    goal: str
    repository_root: Path
    branch: str | None
    head_commit: str | None
    scope_items: tuple[str, ...]
    affected_files: tuple[Path, ...]
    required_tests: tuple[str, ...]
    risks: tuple[PlanRisk, ...]
