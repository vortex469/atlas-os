from app.intelligence.findings import Severity
from app.intelligence.docker_rules import evaluate_docker


def test_expected_container_states_match() -> None:
    findings = evaluate_docker(
        status={
            "running": 1,
            "stopped": 1,
            "unhealthy": 0,
            "containers": [
                {
                    "name": "atlas-api",
                    "status": "running",
                    "health": "healthy",
                    "image": "atlas-api:latest",
                },
                {
                    "name": "temporary-job",
                    "status": "exited",
                    "health": "not-configured",
                    "image": "temporary-job:latest",
                },
            ],
        },
        expected_states_getter=lambda: {
            "atlas-api": "running",
            "temporary-job": "stopped",
        },
    )

    assert len(findings) == 1
    assert findings[0].id == "docker-running"
    assert findings[0].metric["unexpected_containers"] == 0


def test_running_container_expected_stopped() -> None:
    findings = evaluate_docker(
        status={
            "running": 1,
            "stopped": 0,
            "unhealthy": 0,
            "containers": [
                {
                    "name": "temporary-job",
                    "status": "running",
                    "health": "not-configured",
                    "image": "temporary-job:latest",
                },
            ],
        },
        expected_states_getter=lambda: {
            "temporary-job": "stopped",
        },
    )

    warning = next(
        finding
        for finding in findings
        if finding.id == "docker-unexpected-state"
    )

    assert warning.severity == Severity.WARNING
    assert warning.score_penalty == 5
    assert warning.details["containers"][0]["expected"] == "stopped"
    assert warning.details["containers"][0]["actual"] == "running"


def test_missing_expected_container() -> None:
    findings = evaluate_docker(
        status={
            "running": 0,
            "stopped": 0,
            "unhealthy": 0,
            "containers": [],
        },
        expected_states_getter=lambda: {
            "atlas-api": "running",
        },
    )

    warning = next(
        finding
        for finding in findings
        if finding.id == "docker-unexpected-state"
    )

    assert warning.details["containers"][0] == {
        "name": "atlas-api",
        "expected": "running",
        "actual": "missing",
        "status": None,
        "health": None,
    }


def test_unhealthy_container() -> None:
    findings = evaluate_docker(
        status={
            "running": 1,
            "stopped": 0,
            "unhealthy": 1,
            "containers": [
                {
                    "name": "atlas-api",
                    "status": "running",
                    "health": "unhealthy",
                    "image": "atlas-api:latest",
                },
            ],
        },
        expected_states_getter=lambda: {
            "atlas-api": "running",
        },
    )

    warning = next(
        finding
        for finding in findings
        if finding.id == "docker-unhealthy"
    )

    assert warning.severity == Severity.WARNING
    assert warning.score_penalty == 10
    assert warning.metric["unhealthy_containers"] == 1


def test_offline_docker_suppresses_expected_state_drift() -> None:
    findings = evaluate_docker(
        status={
            "status": "offline",
            "error": "Permission denied",
            "running": 0,
            "stopped": 0,
            "unhealthy": 0,
            "containers": [],
        },
        expected_states_getter=lambda: {
            "atlas-api": "running",
        },
    )

    assert len(findings) == 1
    assert findings[0].id == "docker-provider-failure"
    assert findings[0].severity == Severity.CRITICAL
    assert findings[0].details["error"] == "Permission denied"
