from collections import Counter

from app.intelligence.engine import IntelligenceEngine
from app.intelligence.findings import Finding, Severity
from app.intelligence.report import (
    Assessment,
    Recommendation,
    SituationReport,
)


def build_situation_report(findings: list[Finding]) -> SituationReport:
    """Convert provider findings into an ACE Situation Report."""
    engine = IntelligenceEngine()
    engine.extend(findings)

    score = engine.calculate_score()
    status = engine.status()

    assessments = _build_assessments(findings, status)
    recommendations = _build_recommendations(findings)
    summary = _build_summary(findings, status)

    return SituationReport(
        score=score,
        status=status,
        summary=summary,
        findings=findings,
        assessments=assessments,
        recommendations=recommendations,
    )


def _build_summary(findings: list[Finding], status: str) -> str:
    if not findings:
        return "No findings were reported. Atlas is operating normally."

    counts = Counter(finding.severity for finding in findings)

    if status == "critical":
        return (
            f"Atlas detected {counts[Severity.CRITICAL]} critical finding(s), "
            f"{counts[Severity.WARNING]} warning(s), and "
            f"{counts[Severity.INFO]} informational finding(s). "
            "Immediate attention is recommended."
        )

    if status == "degraded":
        return (
            f"Atlas detected {counts[Severity.WARNING]} warning(s) and "
            f"{counts[Severity.INFO]} informational finding(s). "
            "The environment is operational, but maintenance is recommended."
        )

    return (
        f"Atlas reviewed {len(findings)} finding(s). "
        "No health-affecting warnings or critical conditions were detected."
    )


def _build_assessments(
    findings: list[Finding],
    status: str,
) -> list[Assessment]:
    if not findings:
        return [
            Assessment(
                title="Environment healthy",
                priority="info",
                details={
                    "status": status,
                    "finding_count": 0,
                },
            )
        ]

    assessments: list[Assessment] = []

    for severity in (
        Severity.CRITICAL,
        Severity.WARNING,
        Severity.INFO,
    ):
        matching = [
            finding
            for finding in findings
            if finding.severity == severity
        ]

        if not matching:
            continue

        components = sorted(
            {
                finding.component or finding.source
                for finding in matching
            }
        )

        assessments.append(
            Assessment(
                title=f"{len(matching)} {severity.value} finding(s) detected",
                priority=severity.value,
                details={
                    "count": len(matching),
                    "components": components,
                },
            )
        )

    return assessments


def _build_recommendations(
    findings: list[Finding],
) -> list[Recommendation]:
    recommendations: list[Recommendation] = []
    seen: set[tuple[str, str | None]] = set()

    for finding in findings:
        if not finding.recommendation:
            continue

        key = (finding.recommendation, finding.component)

        if key in seen:
            continue

        seen.add(key)

        recommendations.append(
            Recommendation(
                title=finding.recommendation,
                reason=finding.message,
                priority=_recommendation_priority(finding.severity),
                confidence=1.0,
                estimated_effort="Unknown",
                component=finding.component or finding.source,
            )
        )

    return recommendations


def _recommendation_priority(severity: Severity) -> str:
    if severity == Severity.CRITICAL:
        return "high"

    if severity == Severity.WARNING:
        return "medium"

    return "low"
