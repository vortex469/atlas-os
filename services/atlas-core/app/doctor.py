import sys
from collections.abc import Callable
from typing import Any

from app.config.validation import (
    ConfigurationValidationError,
    validate_configuration,
)
from app.intelligence.engine import IntelligenceEngine
from app.intelligence.findings import Severity
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


def run_check(
    name: str,
    check: Callable[[], Any],
) -> tuple[bool, Any, str | None]:
    try:
        result = check()
        print(f"{PASS} {name}")
        return True, result, None
    except Exception as error:
        message = str(error)
        print(f"{FAIL} {name}: {message}")
        return False, None, message


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


def main() -> int:
    print()
    print("Atlas Doctor")
    print("=" * 44)

    configuration_ok = True
    infrastructure_failures = 0
    critical_service_failures = 0
    warning_count = 0

    results: dict[str, Any] = {}
    failures: dict[str, str] = {}

    print()
    print("Configuration")
    print("-" * 44)

    try:
        validate_configuration()
        print(f"{PASS} Atlas configuration")
    except ConfigurationValidationError as error:
        configuration_ok = False
        print(f"{FAIL} Atlas configuration")
        print(error)

    print()
    print("Infrastructure")
    print("-" * 44)

    checks = (
        ("Docker", get_docker_status),
        ("Proxmox", get_proxmox_status),
        ("Proxmox guests", get_proxmox_guests),
        ("Home Assistant", get_homeassistant_status),
        ("Service inventory", get_health),
    )

    for name, check in checks:
        passed, result, error = run_check(name, check)

        if passed:
            results[name] = result
        else:
            infrastructure_failures += 1
            failures[name] = error or "Unknown error"

    warnings: list[str] = []
    information: list[str] = []
    critical: list[str] = []

    intelligence = IntelligenceEngine()

    home = results.get("Home Assistant")

    if isinstance(home, dict):
        intelligence.extend(
            evaluate_homeassistant(home)
        )

    for finding in intelligence.findings():
        if finding.severity == Severity.CRITICAL:
            critical.append(finding.message)

            if finding.affects_health:
                critical_service_failures += 1

        elif finding.severity == Severity.WARNING:
            warnings.append(finding.message)

            if finding.affects_health:
                warning_count += 1

        elif finding.severity == Severity.INFO:
            information.append(finding.message)

    docker = results.get("Docker", {})
    unhealthy_containers = docker.get("unhealthy", 0)

    if unhealthy_containers:
        warning_count += 1
        warnings.append(
            f"Docker has {unhealthy_containers} unhealthy containers"
        )

    services = results.get("Service inventory", {})

    if isinstance(services, dict):
        for service_name, service in services.items():
            if not isinstance(service, dict):
                continue

            status = service.get("status", "unknown")
            critical_service = service.get("critical") is True

            if status == "online":
                continue

            if critical_service:
                critical_service_failures += 1
                critical.append(
                    f"{service_name}: {status}"
                )
            else:
                warning_count += 1
                warnings.append(
                    f"{service_name}: {status}"
                )

    for name, error in failures.items():
        critical.append(f"{name}: {error}")

    print()
    print("Critical")
    print("-" * 44)

    if critical:
        for item in critical:
            print(f"{FAIL} {item}")
    else:
        print(f"{PASS} No critical issues detected")

    print()
    print("Warnings")
    print("-" * 44)

    if warnings:
        for item in warnings:
            print(f"{WARN} {item}")
    else:
        print(f"{PASS} No warnings detected")

    print()
    print("Information")
    print("-" * 44)

    if information:
        for item in information:
            print(f"{INFO} {item}")
    else:
        print(f"{PASS} No informational notices")

    score = calculate_score(
        configuration_ok=configuration_ok,
        infrastructure_failures=infrastructure_failures,
        critical_service_failures=critical_service_failures,
        warnings=warning_count,
    )

    print()
    print("Overall Health")
    print("-" * 44)
    print(f"Score: {score}/100")

    has_critical_failure = (
        not configuration_ok
        or infrastructure_failures > 0
        or critical_service_failures > 0
    )

    if has_critical_failure:
        print("Status: CRITICAL")
        return 2

    if warning_count:
        print("Status: DEGRADED")
        return 1

    print("Status: HEALTHY")
    return 0


if __name__ == "__main__":
    sys.exit(main())
