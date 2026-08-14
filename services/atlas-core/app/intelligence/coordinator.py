import asyncio
from collections.abc import Callable
from time import perf_counter

from app.config.policies import get_intelligence_policy
from app.config.policy_models import PolicySeverity
from app.config.settings import settings
from app.core.logging import get_logger
from app.intelligence import history as history_module
from app.intelligence.assessment import build_situation_report
from app.intelligence.discovery import collect_discovery_compatibility_findings
from app.intelligence.findings import Finding, Severity
from app.intelligence.providers.docker import collect_docker_findings
from app.intelligence.providers.homeassistant import (
    collect_homeassistant_findings,
)
from app.intelligence.providers.proxmox import (
    collect_proxmox_findings,
)
from app.intelligence.report import (
    IntelligenceTelemetry,
    ProviderCollectionTiming,
    SituationReport,
)
from app.providers.base import Provider
from app.providers.capabilities import ProviderPriority
from app.providers.registry import ProviderRegistry, provider_registry

FindingProvider = Callable[[], list[Finding]]
logger = get_logger("atlas.intelligence.coordinator")


PROVIDERS: tuple[FindingProvider, ...] = (
    collect_homeassistant_findings,
    collect_docker_findings,
    collect_proxmox_findings,
)

LEGACY_PROVIDER_IDENTITIES = {
    collect_homeassistant_findings: ("home-assistant", "Home Assistant"),
    collect_docker_findings: ("docker", "Docker"),
    collect_proxmox_findings: ("proxmox", "Proxmox"),
}


def collect_findings() -> list[Finding]:
    findings: list[Finding] = []

    for provider in PROVIDERS:
        findings.extend(provider())

    return findings


def _legacy_provider_identity(
    provider: FindingProvider,
    index: int,
) -> tuple[str, str]:
    return LEGACY_PROVIDER_IDENTITIES.get(
        provider,
        (f"legacy-provider-{index + 1}", f"Legacy Provider {index + 1}"),
    )


async def collect_legacy_findings_with_telemetry(
    *,
    timeout_seconds: float,
) -> tuple[list[Finding], list[ProviderCollectionTiming]]:
    """Run synchronous legacy collectors concurrently within one deadline."""

    async def collect_one(
        provider: FindingProvider,
        index: int,
    ) -> tuple[list[Finding], ProviderCollectionTiming]:
        provider_id, provider_name = _legacy_provider_identity(provider, index)
        started_at = perf_counter()
        status = "completed"
        try:
            findings = await asyncio.wait_for(
                asyncio.to_thread(provider),
                timeout=timeout_seconds,
            )
        except TimeoutError:
            status = "timed_out"
            findings = [
                Finding(
                    id=f"{provider_id}-finding-collection-timed-out",
                    severity=Severity.CRITICAL,
                    category="provider",
                    source=provider_id,
                    component=provider_name,
                    title="Provider intelligence collection timed out",
                    message=(
                        f"ACE stopped waiting for findings from {provider_name} "
                        f"after {timeout_seconds:g} seconds."
                    ),
                    recommendation=(
                        "Review provider connectivity, response time, and "
                        "Atlas Core logs."
                    ),
                    score_penalty=20,
                    details={"timeout_seconds": timeout_seconds},
                )
            ]
        except Exception as error:  # noqa: BLE001
            status = "failed"
            findings = [
                Finding(
                    id=f"{provider_id}-finding-collection-failed",
                    severity=Severity.CRITICAL,
                    category="provider",
                    source=provider_id,
                    component=provider_name,
                    title="Provider intelligence collection failed",
                    message=f"ACE could not collect findings from {provider_name}.",
                    recommendation=(
                        "Review provider connectivity, response time, and "
                        "Atlas Core logs."
                    ),
                    score_penalty=20,
                    details={"error_type": type(error).__name__},
                )
            ]
        return findings, ProviderCollectionTiming(
            provider_id=provider_id,
            provider_name=provider_name,
            status=status,
            duration_ms=round((perf_counter() - started_at) * 1000, 2),
            finding_count=len(findings),
        )

    results = await asyncio.gather(
        *(collect_one(provider, index) for index, provider in enumerate(PROVIDERS))
    )
    return (
        [finding for findings, _ in results for finding in findings],
        [timing for _, timing in results],
    )


async def collect_provider_findings(
    registry: ProviderRegistry = provider_registry,
    *,
    timeout_seconds: float = (
        settings.intelligence.provider_timeout_seconds
    ),
) -> list[Finding]:
    findings, _ = await collect_provider_findings_with_telemetry(
        registry,
        timeout_seconds=timeout_seconds,
    )
    return findings


async def collect_provider_findings_with_telemetry(
    registry: ProviderRegistry = provider_registry,
    *,
    timeout_seconds: float = (
        settings.intelligence.provider_timeout_seconds
    ),
    excluded_provider_ids: frozenset[str] = frozenset(),
) -> tuple[list[Finding], IntelligenceTelemetry]:
    collection_started_at = perf_counter()

    def failure_finding(
        provider: Provider,
        *,
        title: str,
        message: str,
        details: dict[str, object],
        finding_id_suffix: str,
    ) -> Finding:
        critical = (
            provider.metadata.priority
            == ProviderPriority.CRITICAL
        )

        return Finding(
            id=(
                f"{provider.metadata.id}-finding-collection-"
                f"{finding_id_suffix}"
            ),
            severity=(
                Severity.CRITICAL
                if critical
                else Severity.WARNING
            ),
            category="provider",
            source=provider.metadata.id,
            component=provider.metadata.name,
            title=title,
            message=message,
            recommendation=(
                "Review provider connectivity, response time, and "
                "Atlas Core logs."
            ),
            score_penalty=20 if critical else 10,
            details=details,
        )

    async def collect_from_provider(
        provider: Provider,
    ) -> tuple[list[Finding], ProviderCollectionTiming]:
        started_at = perf_counter()
        status = "completed"

        try:
            provider_findings = await asyncio.wait_for(
                provider.get_findings(),
                timeout=timeout_seconds,
            )
            findings = [
                finding
                for finding in provider_findings
                if isinstance(finding, Finding)
            ]
        except TimeoutError:
            status = "timed_out"
            findings = [
                failure_finding(
                    provider,
                    title="Provider intelligence collection timed out",
                    message=(
                        f"ACE stopped waiting for findings from "
                        f"{provider.metadata.name} after "
                        f"{timeout_seconds:g} seconds."
                    ),
                    details={
                        "timeout_seconds": timeout_seconds,
                    },
                    finding_id_suffix="timed-out",
                ),
            ]
        except Exception as error:  # noqa: BLE001
            status = "failed"
            findings = [
                failure_finding(
                    provider,
                    title="Provider intelligence collection failed",
                    message=(
                        f"ACE could not collect findings from "
                        f"{provider.metadata.name}: {error}"
                    ),
                    details={"error": str(error)},
                    finding_id_suffix="failed",
                ),
            ]

        return findings, ProviderCollectionTiming(
            provider_id=provider.metadata.id,
            provider_name=provider.metadata.name,
            status=status,
            duration_ms=round(
                (perf_counter() - started_at) * 1000,
                2,
            ),
            finding_count=len(findings),
        )

    provider_results = await asyncio.gather(
        *(
            collect_from_provider(provider)
            for provider in registry.all()
            if provider.metadata.id not in excluded_provider_ids
        ),
    )

    findings = [
        finding
        for provider_findings, _ in provider_results
        for finding in provider_findings
    ]
    telemetry = IntelligenceTelemetry(
        provider_collection_duration_ms=round(
            (perf_counter() - collection_started_at) * 1000,
            2,
        ),
        provider_timeout_seconds=timeout_seconds,
        providers=[
            timing
            for _, timing in provider_results
        ],
    )
    return findings, telemetry


async def build_report() -> SituationReport:
    """Collect all provider findings and build the ACE Situation Report."""
    collection_started_at = perf_counter()
    timeout_seconds = settings.intelligence.provider_timeout_seconds
    legacy_provider_ids = frozenset(
        _legacy_provider_identity(provider, index)[0]
        for index, provider in enumerate(PROVIDERS)
    )
    (
        (legacy_findings, legacy_timings),
        (provider_findings, provider_telemetry),
    ) = await asyncio.gather(
        collect_legacy_findings_with_telemetry(
            timeout_seconds=timeout_seconds,
        ),
        collect_provider_findings_with_telemetry(
            timeout_seconds=timeout_seconds,
            excluded_provider_ids=legacy_provider_ids,
        ),
    )
    findings = [*legacy_findings, *provider_findings]
    telemetry = IntelligenceTelemetry(
        provider_collection_duration_ms=round(
            (perf_counter() - collection_started_at) * 1000,
            2,
        ),
        provider_timeout_seconds=timeout_seconds,
        providers=[*legacy_timings, *provider_telemetry.providers],
    )
    try:
        findings.extend(collect_discovery_compatibility_findings())
    except Exception:
        logger.exception("Unable to collect Discovery compatibility findings")
    findings.extend(_performance_findings(telemetry))
    report = build_situation_report(findings)
    try:
        history_module.intelligence_telemetry_history.append(
            telemetry
        )
    except Exception:
        logger.exception(
            "Unable to persist provider intelligence telemetry"
        )
    return report.model_copy(
        update={"telemetry": telemetry},
    )


def _performance_findings(
    telemetry: IntelligenceTelemetry,
) -> list[Finding]:
    policy = get_intelligence_policy()
    findings: list[Finding] = []

    for timing in telemetry.providers:
        provider_policy = policy.providers.get(
            timing.provider_id
        )
        if (
            provider_policy is None
            or timing.status != "completed"
            or timing.duration_ms
            <= provider_policy.maximum_collection_duration_ms
        ):
            continue

        severity = _policy_severity(provider_policy.severity)
        findings.append(
            Finding(
                id=(
                    f"{timing.provider_id}-intelligence-"
                    "collection-slow"
                ),
                severity=severity,
                category="provider",
                source=timing.provider_id,
                component=timing.provider_name,
                title="Provider intelligence collection is slow",
                message=(
                    f"{timing.provider_name} finding collection took "
                    f"{timing.duration_ms:g} ms; policy allows "
                    f"{provider_policy.maximum_collection_duration_ms:g} "
                    "ms."
                ),
                recommendation=(
                    "Review provider response time, query scope, and "
                    "network latency before the hard timeout is reached."
                ),
                affects_health=severity != Severity.INFO,
                score_penalty={
                    Severity.INFO: 0,
                    Severity.WARNING: 5,
                    Severity.CRITICAL: 15,
                }[severity],
                metric={
                    "duration_ms": timing.duration_ms,
                    "maximum_duration_ms": (
                        provider_policy
                        .maximum_collection_duration_ms
                    ),
                },
            ),
        )

    return findings


def _policy_severity(value: PolicySeverity) -> Severity:
    return {
        "info": Severity.INFO,
        "warning": Severity.WARNING,
        "critical": Severity.CRITICAL,
    }[value]
