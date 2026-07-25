import asyncio
from collections.abc import Callable

from app.config.settings import settings
from app.intelligence.assessment import build_situation_report
from app.intelligence.findings import Finding, Severity
from app.intelligence.providers.docker import collect_docker_findings
from app.intelligence.providers.homeassistant import (
    collect_homeassistant_findings,
)
from app.intelligence.providers.proxmox import (
    collect_proxmox_findings,
)
from app.intelligence.report import SituationReport
from app.providers.base import Provider
from app.providers.capabilities import ProviderPriority
from app.providers.registry import ProviderRegistry, provider_registry


FindingProvider = Callable[[], list[Finding]]


PROVIDERS: tuple[FindingProvider, ...] = (
    collect_homeassistant_findings,
    collect_docker_findings,
    collect_proxmox_findings,
)


def collect_findings() -> list[Finding]:
    findings: list[Finding] = []

    for provider in PROVIDERS:
        findings.extend(provider())

    return findings


async def collect_provider_findings(
    registry: ProviderRegistry = provider_registry,
    *,
    timeout_seconds: float = (
        settings.intelligence.provider_timeout_seconds
    ),
) -> list[Finding]:
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
    ) -> list[Finding]:
        try:
            provider_findings = await asyncio.wait_for(
                provider.get_findings(),
                timeout=timeout_seconds,
            )
            return [
                finding
                for finding in provider_findings
                if isinstance(finding, Finding)
            ]
        except TimeoutError:
            return [
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
        except Exception as error:
            return [
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

    provider_results = await asyncio.gather(
        *(
            collect_from_provider(provider)
            for provider in registry.all()
        ),
    )

    return [
        finding
        for provider_findings in provider_results
        for finding in provider_findings
    ]


async def build_report() -> SituationReport:
    """Collect all provider findings and build the ACE Situation Report."""
    findings = collect_findings()
    findings.extend(await collect_provider_findings())
    return build_situation_report(findings)
