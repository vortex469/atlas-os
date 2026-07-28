"""Deterministic implementation review."""

from pathlib import Path

from app.review.exceptions import ReviewValidationError
from app.review.models import (
    ArchitectureAssessment,
    ReviewCategory,
    ReviewFinding,
    ReviewReport,
    ReviewRequest,
    ReviewSeverity,
    ReviewStatus,
    TestEvidence,
)
from app.verification.models import VerificationStatus


class ReviewEngine:
    """Review supplied implementation evidence without external inspection."""

    def review(self, request: ReviewRequest) -> ReviewReport:
        """Validate and review one immutable request."""

        normalized_request = self._normalize_request(request)

        findings = (
            self._architecture_findings(normalized_request.architecture_assessments)
            + self._scope_findings(normalized_request)
            + self._test_coverage_findings(normalized_request)
            + self._verification_findings(normalized_request)
        )

        return ReviewReport(
            request_id=normalized_request.identifier,
            checkpoint_id=normalized_request.plan.checkpoint_id,
            status=self._status(findings),
            findings=findings,
            recommendations=self._recommendations(findings),
        )

    def _normalize_request(self, request: ReviewRequest) -> ReviewRequest:
        identifier = request.identifier.strip()

        if not identifier:
            raise ReviewValidationError("Review request identifier must not be blank")

        repository_root = request.plan.repository_root.resolve(strict=False)
        verification_root = request.verification_report.repository_root.resolve(
            strict=False
        )

        if verification_root != repository_root:
            raise ReviewValidationError(
                "Verification report repository root must match the plan"
            )

        changed_files = self._normalize_changed_files(
            repository_root=repository_root,
            changed_files=request.changed_files,
        )
        assessments = self._normalize_architecture_assessments(
            request.architecture_assessments
        )
        test_evidence = self._normalize_test_evidence(request.test_evidence)

        return ReviewRequest(
            identifier=identifier,
            plan=request.plan,
            changed_files=changed_files,
            verification_report=request.verification_report,
            architecture_assessments=assessments,
            test_evidence=test_evidence,
        )

    @staticmethod
    def _normalize_changed_files(
        *,
        repository_root: Path,
        changed_files: tuple[Path, ...],
    ) -> tuple[Path, ...]:
        normalized: list[Path] = []
        seen: set[Path] = set()

        for changed_file in changed_files:
            if changed_file.is_absolute():
                absolute_path = changed_file.resolve(strict=False)
            else:
                absolute_path = (repository_root / changed_file).resolve(strict=False)

            if not absolute_path.is_relative_to(repository_root):
                raise ReviewValidationError(
                    "Changed files must be inside the repository"
                )

            relative_path = absolute_path.relative_to(repository_root)

            if relative_path == Path("."):
                raise ReviewValidationError(
                    "Changed file must identify a repository file"
                )

            if relative_path not in seen:
                seen.add(relative_path)
                normalized.append(relative_path)

        return tuple(normalized)

    @staticmethod
    def _normalize_architecture_assessments(
        assessments: tuple[ArchitectureAssessment, ...],
    ) -> tuple[ArchitectureAssessment, ...]:
        normalized: list[ArchitectureAssessment] = []
        identifiers: set[str] = set()

        for assessment in assessments:
            identifier = assessment.identifier.strip()
            summary = assessment.summary.strip()
            evidence = assessment.evidence.strip()
            recommendation = (
                assessment.recommendation.strip()
                if assessment.recommendation is not None
                else None
            )

            if not identifier:
                raise ReviewValidationError(
                    "Architecture assessment identifier must not be blank"
                )

            if identifier in identifiers:
                raise ReviewValidationError(
                    "Architecture assessment identifiers must be unique"
                )

            if not summary:
                raise ReviewValidationError(
                    f"Architecture assessment '{identifier}' summary must not be blank"
                )

            if not evidence:
                raise ReviewValidationError(
                    f"Architecture assessment '{identifier}' evidence must not be blank"
                )

            if recommendation == "":
                recommendation = None

            identifiers.add(identifier)
            normalized.append(
                ArchitectureAssessment(
                    identifier=identifier,
                    summary=summary,
                    passed=assessment.passed,
                    evidence=evidence,
                    recommendation=recommendation,
                )
            )

        return tuple(normalized)

    @staticmethod
    def _normalize_test_evidence(
        evidence_items: tuple[TestEvidence, ...],
    ) -> tuple[TestEvidence, ...]:
        normalized: list[TestEvidence] = []

        for evidence in evidence_items:
            requirement = evidence.requirement.strip()
            check_identifier = evidence.check_identifier.strip()

            if not requirement:
                raise ReviewValidationError(
                    "Test evidence requirement must not be blank"
                )

            if not check_identifier:
                raise ReviewValidationError(
                    "Test evidence check identifier must not be blank"
                )

            normalized.append(
                TestEvidence(
                    requirement=requirement,
                    check_identifier=check_identifier,
                )
            )

        return tuple(normalized)

    @staticmethod
    def _architecture_findings(
        assessments: tuple[ArchitectureAssessment, ...],
    ) -> tuple[ReviewFinding, ...]:
        findings: list[ReviewFinding] = []

        for assessment in assessments:
            if assessment.passed:
                continue

            recommendation = (
                assessment.recommendation
                or f"Resolve architecture assessment: {assessment.summary}"
            )

            findings.append(
                ReviewFinding(
                    code=f"architecture-{assessment.identifier}",
                    category=ReviewCategory.ARCHITECTURE,
                    severity=ReviewSeverity.ERROR,
                    summary=assessment.summary,
                    evidence=assessment.evidence,
                    recommendation=recommendation,
                )
            )

        return tuple(findings)

    @staticmethod
    def _scope_findings(
        request: ReviewRequest,
    ) -> tuple[ReviewFinding, ...]:
        planned_files = set(request.plan.affected_files)
        findings: list[ReviewFinding] = []

        for changed_file in request.changed_files:
            if changed_file in planned_files:
                continue

            findings.append(
                ReviewFinding(
                    code="out-of-scope-file",
                    category=ReviewCategory.SCOPE,
                    severity=ReviewSeverity.ERROR,
                    summary=f"Changed file is outside the approved plan: "
                    f"{changed_file}",
                    evidence=str(changed_file),
                    recommendation=(
                        "Add the file to the approved implementation plan "
                        "or remove the out-of-scope change"
                    ),
                )
            )

        return tuple(findings)

    @staticmethod
    def _test_coverage_findings(
        request: ReviewRequest,
    ) -> tuple[ReviewFinding, ...]:
        results = {
            result.identifier: result for result in request.verification_report.results
        }
        findings: list[ReviewFinding] = []

        for requirement in request.plan.required_tests:
            mappings = tuple(
                evidence
                for evidence in request.test_evidence
                if evidence.requirement == requirement
            )

            if not mappings:
                findings.append(
                    ReviewFinding(
                        code="missing-test-evidence",
                        category=ReviewCategory.TEST_COVERAGE,
                        severity=ReviewSeverity.ERROR,
                        summary=(
                            f"Required test has no verification evidence: {requirement}"
                        ),
                        evidence=requirement,
                        recommendation=(
                            "Map the required test to a passing verification check"
                        ),
                    )
                )
                continue

            if len(mappings) > 1:
                findings.append(
                    ReviewFinding(
                        code="duplicate-test-evidence",
                        category=ReviewCategory.TEST_COVERAGE,
                        severity=ReviewSeverity.ERROR,
                        summary=(
                            f"Required test has multiple evidence mappings: "
                            f"{requirement}"
                        ),
                        evidence=", ".join(
                            mapping.check_identifier for mapping in mappings
                        ),
                        recommendation=(
                            "Provide exactly one verification-check mapping "
                            "for the required test"
                        ),
                    )
                )
                continue

            check_identifier = mappings[0].check_identifier
            result = results.get(check_identifier)

            if result is None:
                findings.append(
                    ReviewFinding(
                        code="unknown-test-check",
                        category=ReviewCategory.TEST_COVERAGE,
                        severity=ReviewSeverity.ERROR,
                        summary=(
                            f"Required test references an unknown "
                            f"verification check: {requirement}"
                        ),
                        evidence=check_identifier,
                        recommendation=(
                            "Map the required test to a check present in the "
                            "verification report"
                        ),
                    )
                )
                continue

            if result.status is not VerificationStatus.PASSED:
                findings.append(
                    ReviewFinding(
                        code="required-test-not-passed",
                        category=ReviewCategory.TEST_COVERAGE,
                        severity=ReviewSeverity.ERROR,
                        summary=(f"Required test did not pass: {requirement}"),
                        evidence=(f"{check_identifier}: {result.status.value}"),
                        recommendation=(
                            "Resolve the failing verification check and run "
                            "the review again"
                        ),
                    )
                )

        return tuple(findings)

    @staticmethod
    def _verification_findings(
        request: ReviewRequest,
    ) -> tuple[ReviewFinding, ...]:
        findings: list[ReviewFinding] = []

        for result in request.verification_report.results:
            if result.status is VerificationStatus.PASSED:
                continue

            findings.append(
                ReviewFinding(
                    code=f"verification-{result.status.value}",
                    category=ReviewCategory.VERIFICATION,
                    severity=ReviewSeverity.ERROR,
                    summary=(f"Verification check did not pass: {result.identifier}"),
                    evidence=(f"{result.identifier}: {result.status.value}"),
                    recommendation=(
                        "Resolve the verification failure and rerun the "
                        "verification suite"
                    ),
                )
            )

        return tuple(findings)

    @staticmethod
    def _status(
        findings: tuple[ReviewFinding, ...],
    ) -> ReviewStatus:
        if any(finding.severity is ReviewSeverity.ERROR for finding in findings):
            return ReviewStatus.CHANGES_REQUIRED

        return ReviewStatus.APPROVED

    @staticmethod
    def _recommendations(
        findings: tuple[ReviewFinding, ...],
    ) -> tuple[str, ...]:
        recommendations: list[str] = []
        seen: set[str] = set()

        for finding in findings:
            recommendation = finding.recommendation.strip()

            if recommendation and recommendation not in seen:
                seen.add(recommendation)
                recommendations.append(recommendation)

        return tuple(recommendations)
