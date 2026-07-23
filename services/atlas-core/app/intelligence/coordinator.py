from collections.abc import Callable

from app.intelligence.assessment import build_situation_report
from app.intelligence.findings import Finding
from app.intelligence.providers.docker import collect_docker_findings
from app.intelligence.providers.homeassistant import (
    collect_homeassistant_findings,
)
from app.intelligence.providers.proxmox import (
    collect_proxmox_findings,
)
from app.intelligence.report import SituationReport


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


def build_report() -> SituationReport:
    """Collect all provider findings and build the ACE Situation Report."""
    return build_situation_report(collect_findings())
