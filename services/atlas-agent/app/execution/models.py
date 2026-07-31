"""Immutable execution models."""

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from app.planning.models import ImplementationPlan


class ExecutionStatus(StrEnum):
    """Final status of one execution attempt."""

    SUCCEEDED = "succeeded"
    FAILED = "failed"
    TIMED_OUT = "timed_out"
    LAUNCH_FAILED = "launch_failed"


@dataclass(frozen=True, slots=True)
class EnvironmentVariable:
    """One immutable environment override."""

    name: str
    value: str
    value_digest: str | None = None
    redacted: bool = False


@dataclass(frozen=True, slots=True)
class ExecutionRequest:
    """Approved command execution tied to an implementation plan."""

    identifier: str
    plan: ImplementationPlan
    argv: tuple[str, ...]
    working_directory: Path
    timeout_seconds: float | None = None
    environment: tuple[EnvironmentVariable, ...] = ()


@dataclass(frozen=True, slots=True)
class AllowedCommand:
    """Normalized command approved by an execution policy."""

    identifier: str
    plan: ImplementationPlan
    argv: tuple[str, ...]
    working_directory: Path
    timeout_seconds: float | None
    environment: tuple[EnvironmentVariable, ...]


@dataclass(frozen=True, slots=True)
class PolicyViolation:
    """Reason an execution policy rejected a command."""

    message: str


@dataclass(frozen=True, slots=True)
class RunnerOutcome:
    """Raw outcome returned by a command runner."""

    return_code: int | None
    stdout: str
    stderr: str
    timed_out: bool = False
    launch_error: str | None = None


@dataclass(frozen=True, slots=True)
class ExecutionResult:
    """Immutable result of an execution attempt."""

    request_id: str
    checkpoint_id: str
    argv: tuple[str, ...]
    working_directory: Path
    status: ExecutionStatus
    return_code: int | None
    stdout: str
    stderr: str
    duration_seconds: float
    error: str | None = None
