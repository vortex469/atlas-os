from unittest.mock import patch

from app.intelligence.coordinator import collect_findings
from app.intelligence.findings import Finding, Severity


def test_collect_findings() -> None:
    sample = Finding(
        id="test-finding",
        severity=Severity.INFO,
        category="test",
        source="test_provider",
        title="Test finding",
        message="Coordinator test finding.",
        affects_health=False,
    )

    with patch(
        "app.intelligence.coordinator.PROVIDERS",
        (lambda: [sample],),
    ):
        findings = collect_findings()

    assert len(findings) == 1
    assert findings[0].id == "test-finding"


if __name__ == "__main__":
    test_collect_findings()
    print("ACE coordinator test passed")
