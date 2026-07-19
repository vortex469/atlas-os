from collections.abc import Callable

from app.intelligence.findings import Finding
from app.intelligence.providers.homeassistant import (
    collect_homeassistant_findings,
)


FindingProvider = Callable[[], list[Finding]]


PROVIDERS: tuple[FindingProvider, ...] = (
    collect_homeassistant_findings,
)


def collect_findings() -> list[Finding]:
    findings: list[Finding] = []

    for provider in PROVIDERS:
        findings.extend(provider())

    return findings
