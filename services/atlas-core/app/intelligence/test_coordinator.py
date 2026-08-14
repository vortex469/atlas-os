import asyncio
import time

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

    async def no_provider_findings(**_kwargs):
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

    async def no_provider_findings(**_kwargs):
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


def test_legacy_collectors_are_concurrent_ordered_and_attributed(
    monkeypatch,
) -> None:
    def collector(source: str, delay: float):
        def collect() -> list[Finding]:
            time.sleep(delay)
            finding = make_test_finding().model_copy(
                update={"id": source, "source": source},
            )
            return [finding]

        return collect

    home = collector("home", 0.06)
    docker = collector("docker", 0.02)
    proxmox = collector("proxmox", 0.04)
    monkeypatch.setattr(coordinator, "PROVIDERS", (home, docker, proxmox))
    monkeypatch.setattr(
        coordinator,
        "LEGACY_PROVIDER_IDENTITIES",
        {
            home: ("home-assistant", "Home Assistant"),
            docker: ("docker", "Docker"),
            proxmox: ("proxmox", "Proxmox"),
        },
    )

    started_at = time.perf_counter()
    findings, timings = asyncio.run(
        coordinator.collect_legacy_findings_with_telemetry(
            timeout_seconds=0.5,
        )
    )
    duration = time.perf_counter() - started_at

    assert duration < 0.11
    assert [finding.id for finding in findings] == ["home", "docker", "proxmox"]
    assert [timing.provider_id for timing in timings] == [
        "home-assistant",
        "docker",
        "proxmox",
    ]
    assert all(timing.status == "completed" for timing in timings)
    assert all(timing.duration_ms > 0 for timing in timings)


def test_legacy_blocking_collector_does_not_block_loop_and_times_out(
    monkeypatch,
) -> None:
    def slow() -> list[Finding]:
        time.sleep(0.1)
        return []

    def successful() -> list[Finding]:
        return [make_test_finding()]

    monkeypatch.setattr(coordinator, "PROVIDERS", (slow, successful))

    async def exercise():
        started_at = time.perf_counter()
        task = asyncio.create_task(
            coordinator.collect_legacy_findings_with_telemetry(
                timeout_seconds=0.02,
            )
        )
        await asyncio.sleep(0.005)
        loop_remained_responsive_at = time.perf_counter() - started_at
        findings, timings = await task
        returned_at = time.perf_counter() - started_at
        return loop_remained_responsive_at, returned_at, findings, timings

    responsive_at, returned_at, findings, timings = asyncio.run(exercise())

    assert responsive_at < 0.02
    assert returned_at < 0.06
    assert timings[0].status == "timed_out"
    assert timings[1].status == "completed"
    assert findings[0].id.endswith("timed-out")
    assert findings[1] == make_test_finding()


def test_legacy_failure_does_not_suppress_success(monkeypatch) -> None:
    def failing() -> list[Finding]:
        raise RuntimeError("sensitive internal failure")

    def successful() -> list[Finding]:
        return [make_test_finding()]

    monkeypatch.setattr(coordinator, "PROVIDERS", (failing, successful))

    findings, timings = asyncio.run(
        coordinator.collect_legacy_findings_with_telemetry(
            timeout_seconds=1,
        )
    )

    assert timings[0].status == "failed"
    assert timings[1].status == "completed"
    assert findings[0].message == (
        "ACE could not collect findings from Legacy Provider 1."
    )
    assert "sensitive" not in findings[0].model_dump_json()
    assert findings[1] == make_test_finding()


def test_build_report_does_not_double_count_registered_findings(
    monkeypatch,
    isolated_intelligence_history,
) -> None:
    telemetry = IntelligenceTelemetry(
        provider_collection_duration_ms=1,
        provider_timeout_seconds=10,
        providers=[
            ProviderCollectionTiming(
                provider_id="registered-provider",
                provider_name="Registered Provider",
                status="completed",
                duration_ms=1,
                finding_count=1,
            )
        ],
    )

    async def registered_findings(**_kwargs):
        return [make_test_finding()], telemetry

    monkeypatch.setattr(coordinator, "PROVIDERS", ())
    monkeypatch.setattr(
        coordinator,
        "collect_provider_findings_with_telemetry",
        registered_findings,
    )
    monkeypatch.setattr(
        coordinator,
        "collect_discovery_compatibility_findings",
        list,
    )

    report = asyncio.run(coordinator.build_report())

    assert report.findings == [make_test_finding()]
    assert [timing.provider_id for timing in report.telemetry.providers] == [
        "registered-provider"
    ]
