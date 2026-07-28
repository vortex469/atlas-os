"""Immutable review models."""

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from app.planning.models import ImplementationPlan
from app.verification.models import VerificationReport


class ReviewStatus(StrEnum):
    """Overall status of an implementation review."""

    APPROVED = "approved"
    CHANGES_REQUIRED = "changes_required"


class ReviewCategory(StrEnum):
    """Category of one review finding."""

    ARCHITECTURE = "architecture"
    SCOPE = "scope"
    TEST_COVERAGE = "test_coverage"
    VERIFICATION = "verification"


class ReviewSeverity(StrEnum):
    """Severity of one review finding."""

    WARNING = "warning"
    ERROR = "error"


@dataclass(frozen=True, slots=True)
class ArchitectureAssessment:
    """One caller-supplied architecture assessment."""

    identifier: str
    summary: str
    passed: bool
    evidence: str
    recommendation: str | None = None


@dataclass(frozen=True, slots=True)
class TestEvidence:
    """Mapping from one required test to one verification check."""

    requirement: str
    check_identifier: str


@dataclass(frozen=True, slots=True)
class ReviewRequest:
    """Structured evidence submitted for deterministic review."""

    identifier: str
    plan: ImplementationPlan
    changed_files: tuple[Path, ...]
    verification_report: VerificationReport
    architecture_assessments: tuple[ArchitectureAssessment, ...] = ()
    test_evidence: tuple[TestEvidence, ...] = ()


@dataclass(frozen=True, slots=True)
class ReviewFinding:
    """One traceable review finding."""

    code: str
    category: ReviewCategory
    severity: ReviewSeverity
    summary: str
    evidence: str
    recommendation: str


@dataclass(frozen=True, slots=True)
class ReviewReport:
    """Immutable structured implementation review."""

    request_id: str
    checkpoint_id: str
    status: ReviewStatus
    findings: tuple[ReviewFinding, ...]
    recommendations: tuple[str, ...]
