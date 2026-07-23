from app.intelligence.docker_rules import evaluate_docker
from app.intelligence.findings import Finding, Severity
from app.services.docker_service import get_docker_status


def collect_docker_findings() -> list[Finding]:
    try:
        status = get_docker_status()
        return evaluate_docker(status)
    except Exception as error:
        return [
            Finding(
                id="docker-provider-failure",
                severity=Severity.CRITICAL,
                category="docker",
                source="docker",
                title="Docker monitoring failed",
                message=f"ACE could not collect Docker status: {error}",
                recommendation=(
                    "Verify that the Docker daemon is running and that "
                    "Atlas can access the Docker socket."
                ),
                score_penalty=20,
                details={
                    "error": str(error),
                },
            )
        ]
