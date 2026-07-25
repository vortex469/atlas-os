import asyncio
from collections.abc import Callable

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
) -> list[Finding]:
    async def collect_from_provider(
        provider: Provider,
    ) -> list[Finding]:
        try:
            provider_findings = await provider.get_findings()
            return [
                finding
                for finding in provider_findings
                if isinstance(finding, Finding)
            ]
        except Exception as error:
            return [
                Finding(
                    id=(
                        f"{provider.metadata.id}-finding-collection-"
                        "failed"
                    ),
                    severity=Severity.CRITICAL,
                    category="provider",
                    source=provider.metadata.id,
                    component=provider.metadata.name,
                    title="Provider intelligence collection failed",
                    message=(
                        f"ACE could not collect findings from "
                        f"{provider.metadata.name}: {error}"
                    ),
                    recommendation=(
                        "Review provider connectivity and Atlas Core "
                        "logs."
                    ),
                    score_penalty=20,
                    details={"error": str(error)},
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
