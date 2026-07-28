"""Immutable Atlas Agent workflow-state models."""

from dataclasses import dataclass
from enum import StrEnum


class SprintPhase(StrEnum):
    """Lifecycle phase of one Atlas Agent sprint."""

    PLANNED = "planned"
    IN_PROGRESS = "in_progress"
    VERIFYING = "verifying"
    REVIEWING = "reviewing"
    COMPLETED = "completed"
    BLOCKED = "blocked"


@dataclass(frozen=True, slots=True)
class SprintStatus:
    """Current Atlas Agent sprint status."""

    checkpoint_id: str
    title: str
    goal: str
    phase: SprintPhase
