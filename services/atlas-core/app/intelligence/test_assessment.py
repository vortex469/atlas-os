from app.intelligence.assessment import build_situation_report
from app.intelligence.findings import Finding, Severity


def make_finding(
    *,
    finding_id: str,
    severity: Severity,
    recommendation: str | None = None,
    score_penalty: int = 0,
) -> Finding:
    return Finding(
        id=finding_id,
        severity=severity,
        category="test",
        source="test-provider",
        title="Test finding",
        message="Test finding message.",
        recommendation=recommendation,
        component="Test Component",
        score_penalty=score_penalty,
    )


def test_empty_findings_generate_healthy_report():
    report = build_situation_report([])

    assert report.score == 100
    assert report.status == "healthy"
    assert report.findings == []
    assert len(report.assessments) == 1
    assert report.recommendations == []


def test_warning_generates_degraded_report():
    finding = make_finding(
        finding_id="warning-test",
        severity=Severity.WARNING,
        score_penalty=10,
    )

    report = build_situation_report([finding])

    assert report.score == 90
    assert report.status == "degraded"
    assert len(report.assessments) == 1
    assert report.assessments[0].priority == "warning"


def test_critical_generates_critical_report():
    finding = make_finding(
        finding_id="critical-test",
        severity=Severity.CRITICAL,
        score_penalty=25,
    )

    report = build_situation_report([finding])

    assert report.score == 75
    assert report.status == "critical"
    assert "Immediate attention" in report.summary


def test_finding_recommendation_becomes_structured_recommendation():
    finding = make_finding(
        finding_id="recommendation-test",
        severity=Severity.WARNING,
        recommendation="Inspect the affected service.",
    )

    report = build_situation_report([finding])

    assert len(report.recommendations) == 1
    assert (
        report.recommendations[0].title
        == "Inspect the affected service."
    )
    assert report.recommendations[0].priority == "medium"
    assert report.recommendations[0].component == "Test Component"


def test_duplicate_recommendations_are_removed():
    findings = [
        make_finding(
            finding_id="duplicate-one",
            severity=Severity.WARNING,
            recommendation="Review the service.",
        ),
        make_finding(
            finding_id="duplicate-two",
            severity=Severity.WARNING,
            recommendation="Review the service.",
        ),
    ]

    report = build_situation_report(findings)

    assert len(report.recommendations) == 1
