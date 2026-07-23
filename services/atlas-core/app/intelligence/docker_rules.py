from collections.abc import Callable

from app.config.policies import get_expected_container_states
from app.intelligence.findings import Finding, Severity


ExpectedStatesGetter = Callable[[], dict[str, str]]


def normalize_container_state(state: str | None) -> str:
    """Normalize Docker runtime states to Atlas policy states."""

    if state == "running":
        return "running"

    return "stopped"


def evaluate_docker(
    status: dict,
    expected_states_getter: ExpectedStatesGetter = (
        get_expected_container_states
    ),
) -> list[Finding]:
    findings: list[Finding] = []

    running = int(status.get("running", 0))
    containers = status.get("containers", [])
    expected_states = expected_states_getter()

    container_by_name = {
        container.get("name"): container
        for container in containers
        if container.get("name")
    }

    unhealthy_containers = [
        {
            "name": container.get("name"),
            "status": container.get("status"),
            "health": container.get("health"),
            "image": container.get("image"),
        }
        for container in containers
        if container.get("health") == "unhealthy"
    ]

    if unhealthy_containers:
        findings.append(
            Finding(
                id="docker-unhealthy",
                severity=Severity.WARNING,
                category="docker",
                source="docker",
                component="Docker",
                title="Docker containers unhealthy",
                message=(
                    f"{len(unhealthy_containers)} Docker container(s) "
                    "are unhealthy."
                ),
                recommendation=(
                    "Inspect unhealthy containers and review their logs "
                    "and health-check output."
                ),
                metric={
                    "unhealthy_containers": len(unhealthy_containers),
                },
                details={
                    "containers": unhealthy_containers,
                },
                score_penalty=10,
            )
        )

    unexpected_states: list[dict] = []

    for name, expected_state in expected_states.items():
        container = container_by_name.get(name)

        if container is None:
            actual_state = "missing"
        else:
            actual_state = normalize_container_state(
                container.get("status")
            )

        if actual_state == expected_state:
            continue

        unexpected_states.append(
            {
                "name": name,
                "expected": expected_state,
                "actual": actual_state,
                "status": (
                    container.get("status")
                    if container is not None
                    else None
                ),
                "health": (
                    container.get("health")
                    if container is not None
                    else None
                ),
            }
        )

    if unexpected_states:
        findings.append(
            Finding(
                id="docker-unexpected-state",
                severity=Severity.WARNING,
                category="docker",
                source="docker",
                component="Docker",
                title="Docker containers in unexpected states",
                message=(
                    f"{len(unexpected_states)} Docker container(s) "
                    "do not match expected policy."
                ),
                recommendation=(
                    "Review Docker containers whose actual state does "
                    "not match the configured expected state."
                ),
                metric={
                    "unexpected_containers": len(unexpected_states),
                    "configured_containers": len(expected_states),
                },
                details={
                    "containers": unexpected_states,
                },
                score_penalty=5,
            )
        )

    findings.append(
        Finding(
            id="docker-running",
            severity=Severity.INFO,
            category="docker",
            source="docker",
            component="Docker",
            title="Docker engine online",
            message=f"{running} Docker container(s) are running.",
            metric={
                "running": running,
                "configured_containers": len(expected_states),
                "unexpected_containers": len(unexpected_states),
            },
            details={
                "total_containers": len(containers),
            },
            affects_health=False,
            score_penalty=0,
        )
    )

    return findings
