from app.intelligence.docker_rules import evaluate_docker
from app.intelligence.findings import Severity


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
        finding for finding in findings if finding.id == "docker-unexpected-state"
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
        finding for finding in findings if finding.id == "docker-unexpected-state"
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

    warning = next(finding for finding in findings if finding.id == "docker-unhealthy")

    assert warning.severity == Severity.WARNING
    assert warning.score_penalty == 10
    assert warning.metric["unhealthy_containers"] == 1


def test_running_healthy_container_has_no_unhealthy_warning() -> None:
    findings = evaluate_docker(
        status={
            "running": 1,
            "stopped": 0,
            "unhealthy": 0,
            "containers": [
                {
                    "name": "atlas-api",
                    "status": "running",
                    "health": "healthy",
                    "image": "atlas-api:latest",
                },
            ],
        },
        expected_states_getter=dict,
    )

    assert all(finding.id != "docker-unhealthy" for finding in findings)


def test_stopped_unhealthy_container_has_no_unhealthy_warning() -> None:
    findings = evaluate_docker(
        status={
            "running": 0,
            "stopped": 1,
            "unhealthy": 1,
            "containers": [
                {
                    "name": "credential-stager",
                    "status": "exited",
                    "health": "unhealthy",
                    "image": "credential-stager:latest",
                },
            ],
        },
        expected_states_getter=dict,
    )

    assert all(finding.id != "docker-unhealthy" for finding in findings)


def test_stopped_container_without_healthcheck_has_no_unhealthy_warning() -> None:
    findings = evaluate_docker(
        status={
            "running": 0,
            "stopped": 1,
            "unhealthy": 0,
            "containers": [
                {
                    "name": "credential-stager",
                    "status": "exited",
                    "health": "not-configured",
                    "image": "credential-stager:latest",
                },
            ],
        },
        expected_states_getter=dict,
    )

    assert all(finding.id != "docker-unhealthy" for finding in findings)


def test_multiple_stopped_unhealthy_containers_have_no_warning() -> None:
    containers = [
        {
            "name": f"credential-stager-{index}",
            "status": "exited",
            "health": "unhealthy",
            "image": "credential-stager:latest",
        }
        for index in range(3)
    ]

    findings = evaluate_docker(
        status={
            "running": 0,
            "stopped": 3,
            "unhealthy": 3,
            "containers": containers,
        },
        expected_states_getter=dict,
    )

    assert all(finding.id != "docker-unhealthy" for finding in findings)


def test_only_running_unhealthy_containers_are_counted() -> None:
    findings = evaluate_docker(
        status={
            "running": 1,
            "stopped": 1,
            "unhealthy": 2,
            "containers": [
                {
                    "name": "atlas-api",
                    "status": "running",
                    "health": "unhealthy",
                    "image": "atlas-api:latest",
                },
                {
                    "name": "credential-stager",
                    "status": "exited",
                    "health": "unhealthy",
                    "image": "credential-stager:latest",
                },
            ],
        },
        expected_states_getter=dict,
    )

    warning = next(finding for finding in findings if finding.id == "docker-unhealthy")

    assert warning.metric["unhealthy_containers"] == 1
    assert warning.details["containers"] == [
        {
            "name": "atlas-api",
            "status": "running",
            "health": "unhealthy",
            "image": "atlas-api:latest",
        }
    ]


def test_stopped_unhealthy_expected_running_still_reports_state_drift() -> None:
    findings = evaluate_docker(
        status={
            "running": 0,
            "stopped": 1,
            "unhealthy": 1,
            "containers": [
                {
                    "name": "atlas-api",
                    "status": "exited",
                    "health": "unhealthy",
                    "image": "atlas-api:latest",
                },
            ],
        },
        expected_states_getter=lambda: {"atlas-api": "running"},
    )

    assert all(finding.id != "docker-unhealthy" for finding in findings)
    warning = next(
        finding for finding in findings if finding.id == "docker-unexpected-state"
    )
    assert warning.metric["unexpected_containers"] == 1
    assert warning.details["containers"][0]["actual"] == "stopped"


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
