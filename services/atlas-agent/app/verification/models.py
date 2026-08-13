"""Immutable verification models."""

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from app.context.models import AgentContext
from app.execution.models import EnvironmentVariable


class VerificationStatus(StrEnum):
    """Status of a verification check or report."""

    PASSED = "passed"
    FAILED = "failed"
    TIMED_OUT = "timed_out"
    LAUNCH_FAILED = "launch_failed"


@dataclass(frozen=True, slots=True)
class VerificationCheck:
    """Definition of one verification command."""

    identifier: str
    argv: tuple[str, ...]
    working_directory: Path
    timeout_seconds: float | None = None
    environment: tuple[EnvironmentVariable, ...] = ()


@dataclass(frozen=True, slots=True)
class VerificationCheckResult:
    """Immutable result from one verification check."""

    identifier: str
    argv: tuple[str, ...]
    working_directory: Path
    status: VerificationStatus
    return_code: int | None
    stdout: str
    stderr: str
    duration_seconds: float
    error: str | None = None


@dataclass(frozen=True, slots=True)
class VerificationReport:
    """Structured report for an ordered verification suite."""

    repository_root: Path
    results: tuple[VerificationCheckResult, ...]
    status: VerificationStatus
    duration_seconds: float
    context: AgentContext | None = None
