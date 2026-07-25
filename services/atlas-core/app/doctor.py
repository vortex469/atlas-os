import sys
from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.config.validation import validate_configuration
from app.intelligence.docker_rules import evaluate_docker
from app.intelligence.findings import Finding, Severity
from app.intelligence.homeassistant_rules import evaluate_homeassistant
from app.services.docker_service import get_docker_status
from app.services.health_service import get_health
from app.services.homeassistant_service import get_homeassistant_status
from app.services.proxmox_service import (
    get_proxmox_guests,
    get_proxmox_status,
)


PASS = "✓"
INFO = "i"
WARN = "!"
FAIL = "✗"


class DoctorCheck(BaseModel):
    name: str
    passed: bool
    error: str | None = None


class DoctorReport(BaseModel):
    status: Literal["healthy", "degraded", "critical"]
    score: int = Field(ge=0, le=100)
    checked_at: datetime
    configuration_ok: bool
    checks: list[DoctorCheck] = Field(default_factory=list)
    critical: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    information: list[str] = Field(default_factory=list)


def calculate_score(
    configuration_ok: bool,
    infrastructure_failures: int,
    critical_service_failures: int,
    warnings: int,
) -> int:
    score = 100

    if not configuration_ok:
        score -= 40

    score -= infrastructure_failures * 20
    score -= critical_service_failures * 15
    score -= warnings * 5

    return max(score, 0)


def _classify_findings(
    findings: list[Finding],
    critical: list[str],
    warnings: list[str],
    information: list[str],
) -> tuple[int, int]:
    critical_failures = 0
    warning_count = 0

    for finding in findings:
        if finding.severity == Severity.CRITICAL:
            critical.append(finding.message)
            if finding.affects_health:
                critical_failures += 1
        elif finding.severity == Severity.WARNING:
            warnings.append(finding.message)
            if finding.affects_health:
                warning_count += 1
        elif finding.severity == Severity.INFO:
            information.append(finding.message)

    return critical_failures, warning_count


def run_diagnostics(
    *,
    configuration_check: Callable[[], None] = validate_configuration,
    infrastructure_checks: tuple[
        tuple[str, Callable[[], Any]], ...
    ] | None = None,
) -> DoctorReport:
    checks_to_run = (
        infrastructure_checks
        if infrastructure_checks is not None
        else (
            ("Docker", get_docker_status),
            ("Proxmox", get_proxmox_status),
            ("Proxmox guests", get_proxmox_guests),
            ("Home Assistant", get_homeassistant_status),
            ("Service inventory", get_health),
        )
    )
    configuration_ok = True
    critical: list[str] = []
    warnings: list[str] = []
    information: list[str] = []
    checks: list[DoctorCheck] = []
    results: dict[str, Any] = {}

    try:
        configuration_check()
    except Exception as error:
        configuration_ok = False
        critical.append(str(error))

    for name, check in checks_to_run:
        try:
            results[name] = check()
            checks.append(DoctorCheck(name=name, passed=True))
        except Exception as error:
            message = str(error)
            checks.append(
                DoctorCheck(
                    name=name,
                    passed=False,
                    error=message,
                ),
            )
            critical.append(f"{name}: {message}")

    findings: list[Finding] = []
    docker = results.get("Docker")
    if isinstance(docker, dict):
        findings.extend(evaluate_docker(docker))
    home = results.get("Home Assistant")
    if isinstance(home, dict):
        findings.extend(evaluate_homeassistant(home))

    critical_service_failures, warning_count = (
        _classify_findings(
            findings,
            critical,
            warnings,
            information,
        )
    )

    services = results.get("Service inventory")
    if isinstance(services, dict):
        for service_name, service in services.items():
            if not isinstance(service, dict):
                continue
            status = service.get("status", "unknown")
            if status == "online":
                continue
            if service.get("critical") is True:
                critical_service_failures += 1
                critical.append(f"{service_name}: {status}")
            else:
                warning_count += 1
                warnings.append(f"{service_name}: {status}")

    infrastructure_failures = sum(
        not check.passed for check in checks
    )
    score = calculate_score(
        configuration_ok=configuration_ok,
        infrastructure_failures=infrastructure_failures,
        critical_service_failures=critical_service_failures,
        warnings=warning_count,
    )
    status: Literal["healthy", "degraded", "critical"]
    if (
        not configuration_ok
        or infrastructure_failures
        or critical_service_failures
    ):
        status = "critical"
    elif warning_count:
        status = "degraded"
    else:
        status = "healthy"

    return DoctorReport(
        status=status,
        score=score,
        checked_at=datetime.now(timezone.utc),
        configuration_ok=configuration_ok,
        checks=checks,
        critical=critical,
        warnings=warnings,
        information=information,
    )


def _print_items(
    title: str,
    items: list[str],
    marker: str,
    empty_message: str,
) -> None:
    print()
    print(title)
    print("-" * 44)
    if items:
        for item in items:
            print(f"{marker} {item}")
    else:
        print(f"{PASS} {empty_message}")


def main() -> int:
    print()
    print("Atlas Doctor")
    print("=" * 44)

    report = run_diagnostics()

    print()
    print("Configuration")
    print("-" * 44)
    if report.configuration_ok:
        print(f"{PASS} Atlas configuration")
    else:
        print(f"{FAIL} Atlas configuration")

    print()
    print("Infrastructure")
    print("-" * 44)
    for check in report.checks:
        if check.passed:
            print(f"{PASS} {check.name}")
        else:
            print(f"{FAIL} {check.name}: {check.error}")

    _print_items(
        "Critical",
        report.critical,
        FAIL,
        "No critical issues detected",
    )
    _print_items(
        "Warnings",
        report.warnings,
        WARN,
        "No warnings detected",
    )
    _print_items(
        "Information",
        report.information,
        INFO,
        "No informational notices",
    )

    print()
    print("Overall Health")
    print("-" * 44)
    print(f"Score: {report.score}/100")
    print(f"Status: {report.status.upper()}")

    return {
        "healthy": 0,
        "degraded": 1,
        "critical": 2,
    }[report.status]


if __name__ == "__main__":
    sys.exit(main())
