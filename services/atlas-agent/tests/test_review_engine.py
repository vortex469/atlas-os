"""Tests for deterministic implementation review."""

import subprocess
from pathlib import Path

import pytest

from app.context.models import AgentContext
from app.planning.models import ImplementationPlan, PlanRisk
from app.review import (
    ArchitectureAssessment,
    ReviewCategory,
    ReviewEngine,
    ReviewRequest,
    ReviewStatus,
    ReviewValidationError,
)
from app.review import (
    TestEvidence as ReviewTestEvidence,
)
from app.verification.models import (
    VerificationCheckResult,
    VerificationReport,
    VerificationStatus,
)


def make_plan(
    *,
    repository_root: Path = Path("/opt/atlas"),
    affected_files: tuple[Path, ...] = (
        Path("services/atlas-agent/app/review/models.py"),
        Path("services/atlas-agent/app/review/engine.py"),
    ),
    required_tests: tuple[str, ...] = (
        "Run Ruff",
        "Run pytest",
    ),
    risks: tuple[PlanRisk, ...] = (),
) -> ImplementationPlan:
    return ImplementationPlan(
        checkpoint_id="A6",
        title="Review Engine",
        goal="Review implementation against Atlas architecture.",
        repository_root=repository_root,
        branch="feature/atlas-agent",
        head_commit="abc123",
        scope_items=("Add deterministic implementation review",),
        affected_files=affected_files,
        required_tests=required_tests,
        risks=risks,
    )


def make_result(
    *,
    identifier: str,
    status: VerificationStatus = VerificationStatus.PASSED,
) -> VerificationCheckResult:
    return VerificationCheckResult(
        identifier=identifier,
        argv=("python", "-m", identifier),
        working_directory=Path("/opt/atlas"),
        status=status,
        return_code=0 if status is VerificationStatus.PASSED else 1,
        stdout="",
        stderr="",
        duration_seconds=1.0,
    )


def make_report(
    *,
    repository_root: Path = Path("/opt/atlas"),
    results: tuple[VerificationCheckResult, ...] = (
        make_result(identifier="ruff"),
        make_result(identifier="pytest"),
    ),
) -> VerificationReport:
    return VerificationReport(
        repository_root=repository_root,
        results=results,
        status=(
            VerificationStatus.PASSED
            if all(result.status is VerificationStatus.PASSED for result in results)
            else VerificationStatus.FAILED
        ),
        duration_seconds=2.0,
    )


def make_request(**overrides: object) -> ReviewRequest:
    values: dict[str, object] = {
        "identifier": "review-a6",
        "plan": make_plan(),
        "changed_files": (
            Path("services/atlas-agent/app/review/models.py"),
            Path("services/atlas-agent/app/review/engine.py"),
        ),
        "verification_report": make_report(),
        "architecture_assessments": (
            ArchitectureAssessment(
                identifier="boundaries",
                summary="Review remains deterministic",
                passed=True,
                evidence="No subprocess or repository inspection",
            ),
        ),
        "test_evidence": (
            ReviewTestEvidence("Run Ruff", "ruff"),
            ReviewTestEvidence("Run pytest", "pytest"),
        ),
    }
    values.update(overrides)
    return ReviewRequest(**values)  # type: ignore[arg-type]


def test_approves_complete_passing_review() -> None:
    report = ReviewEngine().review(make_request())

    assert report.request_id == "review-a6"
    assert report.checkpoint_id == "A6"
    assert report.status is ReviewStatus.APPROVED
    assert report.findings == ()
    assert report.recommendations == ()


def test_rejects_context_different_from_verification_snapshot() -> None:
    context = AgentContext(
        atlas="online",
        assistant="Atlas",
        engine="Hermes",
        release="test",
        services={},
    )

    with pytest.raises(
        ReviewValidationError,
        match="Review context must match the verification snapshot",
    ):
        ReviewEngine().review(make_request(context=context))


def test_plan_risk_findings_preserve_order() -> None:
    request = make_request(
        plan=make_plan(
            risks=(
                PlanRisk(
                    code="first-risk",
                    summary="First risk.",
                    source="atlas-core",
                ),
                PlanRisk(
                    code="second-risk",
                    summary="Second risk.",
                    source="planning-engine",
                ),
            ),
        ),
    )

    report = ReviewEngine().review(request)

    assert tuple(finding.code for finding in report.findings) == (
        "plan-risk-first-risk",
        "plan-risk-second-risk",
    )


def test_plan_risk_warning_coexists_with_error() -> None:
    request = make_request(
        plan=make_plan(
            risks=(
                PlanRisk(
                    code="atlas-core-unavailable",
                    summary="Atlas Core context could not be loaded.",
                    source="atlas-core",
                ),
            ),
        ),
        changed_files=(Path("services/atlas-core/app/main.py"),),
    )

    report = ReviewEngine().review(request)

    assert report.status is ReviewStatus.CHANGES_REQUIRED
    assert tuple(finding.code for finding in report.findings) == (
        "out-of-scope-file",
        "plan-risk-atlas-core-unavailable",
    )


def test_plan_risk_creates_warning_finding() -> None:
    request = make_request(
        plan=make_plan(
            risks=(
                PlanRisk(
                    code="atlas-core-unavailable",
                    summary="Atlas Core context could not be loaded.",
                    source="atlas-core",
                ),
            ),
        ),
    )

    report = ReviewEngine().review(request)

    assert report.status is ReviewStatus.APPROVED
    assert len(report.findings) == 1

    finding = report.findings[0]

    assert finding.code == "plan-risk-atlas-core-unavailable"
    assert finding.category is ReviewCategory.SCOPE
    assert finding.severity.value == "warning"
    assert finding.summary == "Atlas Core context could not be loaded."
    assert finding.evidence == "Plan risk source: atlas-core"
    assert finding.recommendation == (
        "Address or explicitly accept this plan risk before implementation."
    )


def test_failed_architecture_assessment_requires_changes() -> None:
    request = make_request(
        architecture_assessments=(
            ArchitectureAssessment(
                identifier="boundary",
                summary="Review engine executes Git",
                passed=False,
                evidence="subprocess.run invokes git status",
                recommendation="Remove repository inspection",
            ),
        ),
    )

    report = ReviewEngine().review(request)

    assert report.status is ReviewStatus.CHANGES_REQUIRED
    assert report.findings[0].category is ReviewCategory.ARCHITECTURE
    assert report.findings[0].code == "architecture-boundary"
    assert report.recommendations == ("Remove repository inspection",)


def test_failed_architecture_assessment_gets_default_recommendation() -> None:
    request = make_request(
        architecture_assessments=(
            ArchitectureAssessment(
                identifier="immutability",
                summary="Review output is mutable",
                passed=False,
                evidence="Mutable list field",
            ),
        ),
    )

    report = ReviewEngine().review(request)

    assert report.recommendations == (
        "Resolve architecture assessment: Review output is mutable",
    )


def test_out_of_scope_changed_file_requires_changes() -> None:
    request = make_request(
        changed_files=(
            Path("services/atlas-agent/app/review/models.py"),
            Path("services/atlas-core/app/main.py"),
        ),
    )

    report = ReviewEngine().review(request)

    assert report.status is ReviewStatus.CHANGES_REQUIRED
    assert any(finding.code == "out-of-scope-file" for finding in report.findings)


def test_absolute_changed_file_inside_repository_is_normalized() -> None:
    request = make_request(
        changed_files=(
            Path("/opt/atlas/services/atlas-agent/app/review/models.py"),
            Path("/opt/atlas/services/atlas-agent/app/review/engine.py"),
        ),
    )

    report = ReviewEngine().review(request)

    assert report.status is ReviewStatus.APPROVED


def test_duplicate_changed_files_are_deduplicated() -> None:
    request = make_request(
        changed_files=(
            Path("services/atlas-agent/app/review/models.py"),
            Path("services/atlas-agent/app/review/models.py"),
            Path("services/atlas-agent/app/review/engine.py"),
        ),
    )

    report = ReviewEngine().review(request)

    assert report.status is ReviewStatus.APPROVED


def test_changed_file_outside_repository_is_rejected() -> None:
    with pytest.raises(
        ReviewValidationError,
        match="inside the repository",
    ):
        ReviewEngine().review(make_request(changed_files=(Path("../outside.py"),)))


def test_missing_required_test_evidence_requires_changes() -> None:
    request = make_request(
        test_evidence=(ReviewTestEvidence("Run Ruff", "ruff"),),
    )

    report = ReviewEngine().review(request)

    assert any(finding.code == "missing-test-evidence" for finding in report.findings)


def test_duplicate_required_test_evidence_requires_changes() -> None:
    request = make_request(
        test_evidence=(
            ReviewTestEvidence("Run Ruff", "ruff"),
            ReviewTestEvidence("Run Ruff", "ruff-second"),
            ReviewTestEvidence("Run pytest", "pytest"),
        ),
    )

    report = ReviewEngine().review(request)

    assert any(finding.code == "duplicate-test-evidence" for finding in report.findings)


def test_unknown_verification_check_requires_changes() -> None:
    request = make_request(
        test_evidence=(
            ReviewTestEvidence("Run Ruff", "unknown"),
            ReviewTestEvidence("Run pytest", "pytest"),
        ),
    )

    report = ReviewEngine().review(request)

    assert any(finding.code == "unknown-test-check" for finding in report.findings)


@pytest.mark.parametrize(
    "status",
    (
        VerificationStatus.FAILED,
        VerificationStatus.TIMED_OUT,
        VerificationStatus.LAUNCH_FAILED,
    ),
)
def test_required_test_must_map_to_passing_check(
    status: VerificationStatus,
) -> None:
    request = make_request(
        verification_report=make_report(
            results=(
                make_result(identifier="ruff", status=status),
                make_result(identifier="pytest"),
            )
        ),
    )

    report = ReviewEngine().review(request)

    assert any(
        finding.code == "required-test-not-passed" for finding in report.findings
    )
    assert report.status is ReviewStatus.CHANGES_REQUIRED


def test_unmapped_failed_verification_check_is_not_ignored() -> None:
    request = make_request(
        verification_report=make_report(
            results=(
                make_result(identifier="ruff"),
                make_result(identifier="pytest"),
                make_result(
                    identifier="build",
                    status=VerificationStatus.FAILED,
                ),
            )
        ),
    )

    report = ReviewEngine().review(request)

    assert any(finding.code == "verification-failed" for finding in report.findings)


def test_nonpassing_required_check_creates_traceable_findings() -> None:
    request = make_request(
        verification_report=make_report(
            results=(
                make_result(
                    identifier="ruff",
                    status=VerificationStatus.TIMED_OUT,
                ),
                make_result(identifier="pytest"),
            )
        ),
    )

    report = ReviewEngine().review(request)

    assert tuple(finding.code for finding in report.findings) == (
        "required-test-not-passed",
        "verification-timed_out",
    )


def test_recommendations_are_ordered_and_deduplicated() -> None:
    request = make_request(
        architecture_assessments=(
            ArchitectureAssessment(
                identifier="one",
                summary="First issue",
                passed=False,
                evidence="Evidence one",
                recommendation="Apply the shared fix",
            ),
            ArchitectureAssessment(
                identifier="two",
                summary="Second issue",
                passed=False,
                evidence="Evidence two",
                recommendation="Apply the shared fix",
            ),
        ),
    )

    report = ReviewEngine().review(request)

    assert report.recommendations == ("Apply the shared fix",)


@pytest.mark.parametrize("identifier", ("", " ", "\t"))
def test_blank_request_identifier_is_rejected(
    identifier: str,
) -> None:
    with pytest.raises(ReviewValidationError):
        ReviewEngine().review(make_request(identifier=identifier))


def test_verification_repository_must_match_plan() -> None:
    with pytest.raises(
        ReviewValidationError,
        match="repository root",
    ):
        ReviewEngine().review(
            make_request(
                verification_report=make_report(
                    repository_root=Path("/different/repository")
                )
            )
        )


@pytest.mark.parametrize(
    "assessment",
    (
        ArchitectureAssessment(
            identifier="",
            summary="Summary",
            passed=True,
            evidence="Evidence",
        ),
        ArchitectureAssessment(
            identifier="architecture",
            summary="",
            passed=True,
            evidence="Evidence",
        ),
        ArchitectureAssessment(
            identifier="architecture",
            summary="Summary",
            passed=True,
            evidence="",
        ),
    ),
)
def test_invalid_architecture_assessment_is_rejected(
    assessment: ArchitectureAssessment,
) -> None:
    with pytest.raises(ReviewValidationError):
        ReviewEngine().review(make_request(architecture_assessments=(assessment,)))


def test_duplicate_architecture_identifier_is_rejected() -> None:
    assessment = ArchitectureAssessment(
        identifier="boundary",
        summary="Summary",
        passed=True,
        evidence="Evidence",
    )

    with pytest.raises(ReviewValidationError, match="unique"):
        ReviewEngine().review(
            make_request(architecture_assessments=(assessment, assessment))
        )


@pytest.mark.parametrize(
    "evidence",
    (
        ReviewTestEvidence("", "ruff"),
        ReviewTestEvidence("Run Ruff", ""),
    ),
)
def test_invalid_test_evidence_is_rejected(
    evidence: ReviewTestEvidence,
) -> None:
    with pytest.raises(ReviewValidationError):
        ReviewEngine().review(make_request(test_evidence=(evidence,)))


def test_identical_inputs_produce_equal_reports() -> None:
    request = make_request()
    engine = ReviewEngine()

    assert engine.review(request) == engine.review(request)


def test_review_does_not_execute_or_inspect_filesystem(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_subprocess(
        *args: object,
        **kwargs: object,
    ) -> subprocess.CompletedProcess[str]:
        raise AssertionError("Review must not execute subprocesses")

    def fail_exists(self: Path) -> bool:
        raise AssertionError("Review must not inspect the filesystem")

    monkeypatch.setattr(subprocess, "run", fail_subprocess)
    monkeypatch.setattr(Path, "exists", fail_exists)

    report = ReviewEngine().review(make_request())

    assert report.status is ReviewStatus.APPROVED
