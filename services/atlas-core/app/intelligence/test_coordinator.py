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
    assert report.telemetry.provider_timeout_seconds == 10


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


def test_provider_collection_exposes_timing_telemetry() -> None:
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

    findings, telemetry = asyncio.run(
        coordinator.collect_provider_findings_with_telemetry(
            registry,
            timeout_seconds=2,
        ),
    )

    assert findings == [make_test_finding()]
    assert telemetry.provider_timeout_seconds == 2
    assert telemetry.provider_collection_duration_ms >= 0
    assert len(telemetry.providers) == 1
    timing = telemetry.providers[0]
    assert timing.provider_id == "opnsense"
    assert timing.provider_name == "OPNsense"
    assert timing.status == "completed"
    assert timing.duration_ms >= 0
    assert timing.finding_count == 1


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


def test_provider_finding_collection_has_time_budget() -> None:
    class SlowProvider(OPNsenseProvider):
        async def get_findings(self) -> list[Finding]:
            await asyncio.Event().wait()
            return []

    registry = ProviderRegistry()
    registry.register(
        SlowProvider(
            {
                "host": "firewall.example.test",
                "protocol": "https",
            },
            api_key="key",
            api_secret="secret",
        ),
    )

    findings = asyncio.run(
        coordinator.collect_provider_findings(
            registry,
            timeout_seconds=0.001,
        ),
    )

    assert len(findings) == 1
    assert findings[0].id.endswith("timed-out")
    assert findings[0].severity == Severity.CRITICAL
    assert findings[0].details["timeout_seconds"] == 0.001

    _, telemetry = asyncio.run(
        coordinator.collect_provider_findings_with_telemetry(
            registry,
            timeout_seconds=0.001,
        ),
    )
    assert telemetry.providers[0].status == "timed_out"
    assert telemetry.providers[0].finding_count == 1


def test_optional_provider_failure_is_warning() -> None:
    class FailingProvider(OPNsenseProvider):
        async def get_findings(self) -> list[Finding]:
            raise RuntimeError("Provider failed")

    registry = ProviderRegistry()
    registry.register(
        FailingProvider(
            {
                "host": "firewall.example.test",
                "protocol": "https",
                "critical": False,
            },
            api_key="key",
            api_secret="secret",
        ),
    )

    findings = asyncio.run(
        coordinator.collect_provider_findings(registry),
    )

    assert findings[0].severity == Severity.WARNING
    assert findings[0].score_penalty == 10
