from app.context import AtlasContext
from app.intelligence.docker_rules import (
    docker_failure_finding,
    evaluate_docker,
)
from app.intelligence.findings import Finding
from app.services.docker_service import get_docker_status


def collect_docker_findings(
    atlas_context: AtlasContext | None = None,
) -> list[Finding]:
    try:
        status = get_docker_status(atlas_context)
        return evaluate_docker(status)
    except Exception as error:  # noqa: BLE001
        return [docker_failure_finding(str(error))]
