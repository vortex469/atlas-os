"""P5 release isolation and authority closure for Atlas v0.34."""

from __future__ import annotations

import ast
from pathlib import Path

from fastapi import FastAPI

from app.api.v1.router import router as api_v1_router
from app.installation_readiness_review.contract import (
    InstallationReadinessReviewResultV1,
    InstallationReadinessReviewV1,
)

APP_ROOT = Path(__file__).parents[1]
REPOSITORY_ROOT = APP_ROOT.parents[2]
PACKAGE_ROOT = Path(__file__).parent
ROUTE_PATH = (
    "/api/v1/installation/candidate-records/"
    "{candidate_record_id}/readiness-review"
)


def _production_python(root: Path):
    return tuple(
        path
        for path in root.rglob("*.py")
        if not path.name.startswith("test_") and "__pycache__" not in path.parts
    )


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.Import, ast.ImportFrom))
        for alias in node.names
    }


def test_v034_openapi_is_exactly_one_get_without_effect_siblings() -> None:
    application = FastAPI()
    application.include_router(api_v1_router)
    paths = {
        path: set(operations)
        for path, operations in application.openapi()["paths"].items()
        if "readiness-review" in path
    }
    assert paths == {ROUTE_PATH: {"get"}}
    operation = application.openapi()["paths"][ROUTE_PATH]["get"]
    assert "requestBody" not in operation
    assert [parameter["in"] for parameter in operation["parameters"]] == ["path"]
    all_paths = "\n".join(application.openapi()["paths"])
    for suffix in (
        "install", "execute", "dispatch", "retry", "resend", "send",
        "deploy", "rollback", "admit", "workflow", "mutation",
    ):
        assert f"readiness-review/{suffix}" not in all_paths.lower()


def test_v034_service_has_no_store_reservation_or_effect_dependency() -> None:
    service = PACKAGE_ROOT / "service.py"
    imports = _imports(service)
    forbidden_imports = (
        "store", "sqlite", "route", "transport", "http", "request",
        "subprocess", "docker", "agent", "dispatch", "workflow", "worker",
        "provider", "repository", "credential",
    )
    assert not any(
        marker in imported.lower()
        for imported in imports
        for marker in forbidden_imports
    )
    source = service.read_text(encoding="utf-8").lower()
    for call in (
        ".reserve(", ".append(", ".insert(", ".save(", ".update(",
        ".delete(", ".consume(", ".retry(", ".replay(", "uuid4(",
        "subprocess", "os.system", "docker", "podman", "create_subprocess",
        "install(", "execute(", "dispatch(", "deploy(", "start_workflow(",
    ):
        assert call not in source


def test_v034_models_remain_fixed_read_only_and_non_authorizing() -> None:
    for model in (InstallationReadinessReviewV1, InstallationReadinessReviewResultV1):
        assert model.model_fields["evidence_only"].default is True
        assert model.model_fields["read_only"].default is True
        for field in (
            "execution_admission_granted", "execution_authorized",
            "installation_allowed", "dispatch_allowed", "worker_allowed",
            "workflow_allowed", "deployment_allowed", "mutation_allowed",
            "retry_allowed", "replay_allowed",
        ):
            assert model.model_fields[field].default is False


def test_v020_v033_evidence_has_only_the_named_v034_read_consumer() -> None:
    execution_roots = (
        APP_ROOT / "operational_dispatch",
        APP_ROOT / "execution_candidates",
        APP_ROOT / "provider_intents",
        APP_ROOT / "actions",
        REPOSITORY_ROOT / "services" / "atlas-agent" / "app",
        REPOSITORY_ROOT / "services" / "atlas-execution-worker",
    )
    markers = (
        "installation_readiness_review",
        "InstallationReadinessReviewV1",
        "installation-readiness-review-v1",
    )
    violations = [
        f"{path.relative_to(REPOSITORY_ROOT)} -> {marker}"
        for root in execution_roots
        if root.exists()
        for path in _production_python(root)
        for marker in markers
        if marker in path.read_text(encoding="utf-8")
    ]
    assert violations == []

    permitted = {
        APP_ROOT / "api" / "v1" / "router.py",
        APP_ROOT / "routes" / "installation_readiness_review.py",
        APP_ROOT / "execution_permission_grant" / "contract.py",
    }
    consumers = [
        path
        for path in _production_python(APP_ROOT)
        if PACKAGE_ROOT not in path.parents
        and any(marker in path.read_text(encoding="utf-8") for marker in markers)
    ]
    assert set(consumers) == permitted


def test_v034_home_assistant_stays_blocked_without_deployment_artifact() -> None:
    agent_models = (
        REPOSITORY_ROOT
        / "services"
        / "atlas-agent"
        / "app"
        / "candidate_planning"
        / "models.py"
    ).read_text(encoding="utf-8")
    assert "install-container" not in agent_models
    artifacts = [
        path.relative_to(REPOSITORY_ROOT)
        for root in (REPOSITORY_ROOT / "compose", REPOSITORY_ROOT / "deploy")
        if root.exists()
        for path in root.rglob("*")
        if path.is_file()
        and "home-assistant" in path.name.lower()
        and path.suffix.lower() in {".yaml", ".yml", ".json", ".toml"}
    ]
    assert artifacts == []
