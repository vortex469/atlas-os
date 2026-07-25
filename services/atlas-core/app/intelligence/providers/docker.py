from app.intelligence.docker_rules import (
    docker_failure_finding,
    evaluate_docker,
)
from app.intelligence.findings import Finding
from app.services.docker_service import get_docker_status


def collect_docker_findings() -> list[Finding]:
    try:
        status = get_docker_status()
        return evaluate_docker(status)
    except Exception as error:
        return [docker_failure_finding(str(error))]
