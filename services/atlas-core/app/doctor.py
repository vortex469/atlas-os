import sys
from collections.abc import Callable
from typing import Any

from app.config.validation import (
    ConfigurationValidationError,
    validate_configuration,
)
from app.services.docker_service import get_docker_status
from app.services.health_service import get_health
from app.services.homeassistant_service import get_homeassistant_status
from app.services.proxmox_service import (
    get_proxmox_guests,
    get_proxmox_status,
)


PASS = "✓"
WARN = "!"
FAIL = "✗"


def run_check(
    name: str,
    check: Callable[[], Any],
) -> tuple[bool, Any]:
    try:
        result = check()
        print(f"{PASS} {name}")
        return True, result
    except Exception as error:
        print(f"{FAIL} {name}: {error}")
        return False, None


def calculate_score(
    successful_checks: int,
    total_checks: int,
    warnings: int,
) -> int:
    if total_checks == 0:
        return 0

    base_score = int(
        successful_checks / total_checks * 100
    )

    warning_penalty = min(warnings * 2, 20)

    return max(base_score - warning_penalty, 0)


def main() -> int:
    print()
    print("Atlas Doctor")
    print("=" * 44)
    print()

    successful_checks = 0
    total_checks = 0
    warning_count = 0
    critical_failure = False

    print("Configuration")
    print("-" * 44)

    total_checks += 1

    try:
        validate_configuration()
        successful_checks += 1
        print(f"{PASS} Atlas configuration")
    except ConfigurationValidationError as error:
        print(f"{FAIL} Atlas configuration")
        print(error)
        critical_failure = True

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

    results: dict[str, Any] = {}

    for name, check in checks:
        total_checks += 1
        passed, result = run_check(name, check)

        if passed:
            successful_checks += 1
            results[name] = result
        else:
            critical_failure = True

    print()
    print("Warnings")
    print("-" * 44)

    home = results.get("Home Assistant", {})

    unavailable_entities = (
        home
        .get("entities", {})
        .get("unavailable_count", 0)
    )

    pending_updates = (
        home
        .get("updates", {})
        .get("pending_count", 0)
    )

    if unavailable_entities:
        warning_count += unavailable_entities
        print(
            f"{WARN} Home Assistant has "
            f"{unavailable_entities} unavailable or unknown entities"
        )

    if pending_updates:
        warning_count += pending_updates
        print(
            f"{WARN} Home Assistant has "
            f"{pending_updates} pending updates"
        )

    docker = results.get("Docker", {})
    unhealthy_containers = docker.get("unhealthy", 0)

    if unhealthy_containers:
        warning_count += unhealthy_containers
        print(
            f"{WARN} Docker has "
            f"{unhealthy_containers} unhealthy containers"
        )

    services = results.get("Service inventory", {})

    unavailable_services = [
        service_name
        for service_name, service in services.items()
        if service.get("status") != "online"
    ]

    if unavailable_services:
        warning_count += len(unavailable_services)

        for service_name in unavailable_services:
            status = services[service_name].get(
                "status",
                "unknown",
            )
            print(
                f"{WARN} {service_name}: {status}"
            )

    if warning_count == 0:
        print(f"{PASS} No warnings detected")

    score = calculate_score(
        successful_checks,
        total_checks,
        warning_count,
    )

    print()
    print("Overall Health")
    print("-" * 44)
    print(f"Score: {score}/100")

    if critical_failure:
        print("Status: CRITICAL")
        return 2

    if warning_count:
        print("Status: DEGRADED")
        return 1

    print("Status: HEALTHY")
    return 0


if __name__ == "__main__":
    sys.exit(main())
