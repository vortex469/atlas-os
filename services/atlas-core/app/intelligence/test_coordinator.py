import asyncio

from app.config.policy_models import (
    IntelligencePolicy,
    ProviderPerformancePolicy,
)
from app.intelligence import coordinator
from app.intelligence.findings import Finding, Severity
from app.intelligence.report import (
    IntelligenceTelemetry,
    ProviderCollectionTiming,
)
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


def test_build_report(monkeypatch, isolated_intelligence_history):
    finding = make_test_finding()

    monkeypatch.setattr(
        coordinator,
        "PROVIDERS",
        (lambda: [finding],),
    )
    monkeypatch.setattr(
        coordinator,
        "collect_discovery_compatibility_findings",
        list,
    )

    report = asyncio.run(coordinator.build_report())

    assert report.score == 100
    assert report.status == "healthy"
    assert report.findings == [finding]
    assert len(report.assessments) == 1
    assert report.telemetry.provider_timeout_seconds == 10
    snapshots = isolated_intelligence_history.list()
    assert len(snapshots) == 1
    assert snapshots[0].telemetry == report.telemetry


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


def test_provider_performance_findings_follow_policy(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        coordinator,
        "get_intelligence_policy",
        lambda: IntelligencePolicy(
            providers={
                "qdrant": ProviderPerformancePolicy(
                    maximum_collection_duration_ms=100,
                    severity="critical",
                ),
                "n8n": ProviderPerformancePolicy(
                    maximum_collection_duration_ms=100,
                ),
            },
        ),
    )
    telemetry = IntelligenceTelemetry(
        provider_collection_duration_ms=200,
        provider_timeout_seconds=10,
        providers=[
            ProviderCollectionTiming(
                provider_id="qdrant",
                provider_name="Qdrant",
                status="completed",
                duration_ms=150,
                finding_count=0,
            ),
            ProviderCollectionTiming(
                provider_id="n8n",
                provider_name="n8n",
                status="timed_out",
                duration_ms=10000,
                finding_count=1,
            ),
        ],
    )

    findings = coordinator._performance_findings(telemetry)

    assert len(findings) == 1
    assert findings[0].id == (
        "qdrant-intelligence-collection-slow"
    )
    assert findings[0].severity == "critical"
    assert findings[0].score_penalty == 15
    assert findings[0].metric == {
        "duration_ms": 150,
        "maximum_duration_ms": 100,
    }


def test_build_report_includes_discovery_recommendations(
    monkeypatch,
    isolated_intelligence_history,
) -> None:
    discovery_finding = Finding(
        id="discovery-frigate-atlas-investigate-compatibility",
        severity=Severity.INFO,
        category="discovery-compatibility",
        source="discovery",
        title="Discovery needs compatibility information for Frigate",
        message="Discovery could not determine compatibility.",
        recommendation="Review missing Discovery compatibility information for Frigate.",
        component="Frigate",
        affects_health=False,
        score_penalty=0,
    )
    telemetry = IntelligenceTelemetry(
        provider_collection_duration_ms=0,
        provider_timeout_seconds=10,
        providers=[],
    )

    async def no_provider_findings():
        return [], telemetry

    monkeypatch.setattr(coordinator, "PROVIDERS", ())
    monkeypatch.setattr(
        coordinator,
        "collect_provider_findings_with_telemetry",
        no_provider_findings,
    )
    monkeypatch.setattr(
        coordinator,
        "collect_discovery_compatibility_findings",
        lambda: [discovery_finding, discovery_finding],
    )

    report = asyncio.run(coordinator.build_report())

    assert report.findings == [discovery_finding, discovery_finding]
    assert len(report.recommendations) == 1
    assert report.recommendations[0].title == (
        "Review missing Discovery compatibility information for Frigate."
    )
    assert report.recommendations[0].priority == "low"
    assert report.recommendations[0].component == "Frigate"


def test_discovery_collection_failure_is_log_only_in_report(
    monkeypatch,
    isolated_intelligence_history,
) -> None:
    legacy_finding = make_test_finding()
    telemetry = IntelligenceTelemetry(
        provider_collection_duration_ms=0,
        provider_timeout_seconds=10,
        providers=[],
    )

    async def no_provider_findings():
        return [], telemetry

    def failing_discovery_collection():
        raise AssertionError("Discovery collector should isolate its own failures")

    monkeypatch.setattr(coordinator, "PROVIDERS", (lambda: [legacy_finding],))
    monkeypatch.setattr(
        coordinator,
        "collect_provider_findings_with_telemetry",
        no_provider_findings,
    )
    monkeypatch.setattr(
        coordinator,
        "collect_discovery_compatibility_findings",
        failing_discovery_collection,
    )

    try:
        report = asyncio.run(coordinator.build_report())
    except AssertionError as error:  # pragma: no cover - documents expected boundary
        raise AssertionError(
            "Discovery failures must be isolated inside the Discovery collector."
        ) from error

    assert report.findings == [legacy_finding]
    assert report.recommendations == []
