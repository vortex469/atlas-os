from app.intelligence import coordinator
from app.intelligence.findings import Finding, Severity


def make_test_finding() -> Finding:
    return Finding(
        id="coordinator-test",
        severity=Severity.INFO,
        category="test",
        source="test-provider",
        title="Coordinator test",
        message="Coordinator test finding.",
        component="Test Component",
        affects_health=False,
    )


def test_collect_findings(monkeypatch):
    finding = make_test_finding()

    monkeypatch.setattr(
        coordinator,
        "PROVIDERS",
        (lambda: [finding],),
    )

    findings = coordinator.collect_findings()

    assert findings == [finding]


def test_build_report(monkeypatch):
    finding = make_test_finding()

    monkeypatch.setattr(
        coordinator,
        "PROVIDERS",
        (lambda: [finding],),
    )

    report = coordinator.build_report()

    assert report.score == 100
    assert report.status == "healthy"
    assert report.findings == [finding]
    assert len(report.assessments) == 1
