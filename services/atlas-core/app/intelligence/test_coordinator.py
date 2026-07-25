import asyncio

from app.intelligence import coordinator
from app.intelligence.findings import Finding, Severity
from app.providers.opnsense import OPNsenseProvider
from app.providers.registry import ProviderRegistry


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

    report = asyncio.run(coordinator.build_report())

    assert report.score == 100
    assert report.status == "healthy"
    assert report.findings == [finding]
    assert len(report.assessments) == 1


def test_collects_registered_provider_findings() -> None:
    class FindingProvider(OPNsenseProvider):
        async def get_findings(self) -> list[Finding]:
            return [make_test_finding()]

    registry = ProviderRegistry()
    registry.register(
        FindingProvider(
            {
                "host": "firewall.example.test",
                "protocol": "https",
            },
            api_key="key",
            api_secret="secret",
        ),
    )

    findings = asyncio.run(
        coordinator.collect_provider_findings(registry),
    )

    assert findings == [make_test_finding()]


def test_provider_finding_failure_is_isolated() -> None:
    class FailingProvider(OPNsenseProvider):
        async def get_findings(self) -> list[Finding]:
            raise RuntimeError("Provider failed")

    registry = ProviderRegistry()
    registry.register(
        FailingProvider(
            {
                "host": "firewall.example.test",
                "protocol": "https",
            },
            api_key="key",
            api_secret="secret",
        ),
    )

    findings = asyncio.run(
        coordinator.collect_provider_findings(registry),
    )

    assert len(findings) == 1
    assert findings[0].severity == Severity.CRITICAL
    assert findings[0].source == "opnsense"
