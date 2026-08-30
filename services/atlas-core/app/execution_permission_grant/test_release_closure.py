"""P5 release isolation and authority closure for Atlas v0.35."""

from __future__ import annotations

import ast
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from fastapi import FastAPI

from app.api.v1.router import router as api_v1_router
from app.execution_permission_grant.contract import (
    ExecutionPermissionGrantResultV1,
    ExecutionPermissionGrantV1,
)
from app.execution_permission_grant.test_service_store import (
    _record,
    _service,
)

APP_ROOT = Path(__file__).parents[1]
REPOSITORY_ROOT = APP_ROOT.parents[2]
PACKAGE_ROOT = Path(__file__).parent
COLLECTION = (
    "/api/v1/installation/candidate-records/"
    "{candidate_record_id}/execution-permission-grants"
)
ITEM = COLLECTION + "/{grant_id}"


def _production_python(root: Path):
    return tuple(
        path
        for path in root.rglob("*.py")
        if not path.name.startswith("test_") and "__pycache__" not in path.parts
    )


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return {
        alias.name if isinstance(node, ast.Import) else node.module or ""
        for node in ast.walk(tree)
        if isinstance(node, (ast.Import, ast.ImportFrom))
        for alias in node.names
    }


def test_v035_openapi_is_exact_create_list_get_without_effect_siblings() -> None:
    application = FastAPI()
    application.include_router(api_v1_router)
    paths = {
        path: set(operations)
        for path, operations in application.openapi()["paths"].items()
        if "execution-permission-grants" in path
    }
    assert paths == {COLLECTION: {"get", "post"}, ITEM: {"get"}}
    all_paths = "\n".join(application.openapi()["paths"]).lower()
    for suffix in (
        "install", "execute", "dispatch", "retry", "resend", "send",
        "deploy", "rollback", "admit", "workflow", "worker", "mutation",
    ):
        assert f"execution-permission-grants/{suffix}" not in all_paths


def test_v035_models_are_evidence_only_and_fixed_non_authorizing() -> None:
    for model in (ExecutionPermissionGrantV1, ExecutionPermissionGrantResultV1):
        assert model.model_fields["evidence_only"].default is True
        for field in (
            "execution_admission_granted", "execution_authorized",
            "installation_allowed", "dispatch_allowed",
            "agent_invocation_allowed", "worker_allowed", "workflow_allowed",
            "provider_mutation_allowed", "repository_mutation_allowed",
            "in_guest_mutation_allowed", "deployment_allowed",
            "rollback_allowed", "retry_allowed", "resend_allowed",
            "docker_allowed", "podman_allowed", "shell_allowed",
            "process_allowed", "replay_allowed",
        ):
            assert model.model_fields[field].default is False


def test_v035_service_store_have_no_effect_or_replay_bypass_dependency() -> None:
    forbidden_imports = (
        "agent", "dispatch", "docker", "http", "network", "provider",
        "repository", "requests", "socket", "subprocess", "transport",
        "workflow", "worker",
    )
    violations = [
        f"{path.name} -> {imported}"
        for path in (PACKAGE_ROOT / "service.py", PACKAGE_ROOT / "store.py")
        for imported in _imports(path)
        if any(marker in imported.lower() for marker in forbidden_imports)
    ]
    assert violations == []

    source = "\n".join(
        path.read_text(encoding="utf-8").lower()
        for path in (PACKAGE_ROOT / "service.py", PACKAGE_ROOT / "store.py")
    )
    for call in (
        "subprocess", "os.system", "create_subprocess", "docker", "podman",
        ".execute_grant(", ".install(", ".dispatch(", ".retry(",
        ".resend(", ".invoke_agent(", ".start_worker(",
        ".start_workflow(", ".deploy(", ".rollback(", ".replay(",
        ".release_reservation(", ".delete_reservation(",
    ):
        assert call not in source


def test_permanent_reservations_survive_concurrency_restart_and_expiry(
    tmp_path: Path,
) -> None:
    grant_service, grant_store, _, _, response = _service(tmp_path)
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = tuple(pool.map(lambda _: _record(grant_service, response), range(16)))
    assert sum(result.disposition == "recorded" for result in results) == 1
    assert all(
        result.disposition in {"recorded", "exact_duplicate"} for result in results
    )
    with sqlite3.connect(grant_store.database_path) as connection:
        assert connection.execute(
            "SELECT COUNT(*) FROM execution_permission_grants"
        ).fetchone()[0] == 1

    restarted, _, reader, factory, _ = _service(
        tmp_path, response=response, second=59
    )
    duplicate = _record(restarted, response)
    assert duplicate.disposition == "exact_duplicate"
    assert duplicate.status.lifecycle == "expired"
    assert reader.calls == 0 and factory.calls == 0
    conflict = _record(
        restarted, response, idempotency_key="cannot-bypass-subject-reservation"
    )
    assert conflict.error.error_code == "conflict"


def test_persisted_and_presented_evidence_excludes_sensitive_raw_values(
    tmp_path: Path,
) -> None:
    raw_key = "raw-idempotency-key-must-never-persist"
    grant_service, grant_store, _, _, response = _service(tmp_path)
    result = _record(grant_service, response, idempotency_key=raw_key)
    assert result.disposition == "recorded"
    with sqlite3.connect(grant_store.database_path) as connection:
        schema = connection.execute(
            "SELECT sql FROM sqlite_master WHERE name = 'execution_permission_grants'"
        ).fetchone()[0]
        row = connection.execute(
            "SELECT * FROM execution_permission_grants"
        ).fetchone()
    persisted = schema + "\n" + "\n".join(str(value) for value in row)
    assert raw_key not in persisted
    for marker in (
        "credential_value", "authorization_header", "provider_payload",
        "request_body", "response_body", "command_argv", "stdout", "stderr",
        "internal_path", "endpoint_url", "host_address",
    ):
        assert marker not in persisted
        assert marker not in result.model_dump_json()


def test_v034_evidence_has_only_readiness_and_permission_evidence_consumers() -> None:
    markers = (
        "installation_readiness_review", "InstallationReadinessReviewV1",
        "installation-readiness-review-v1",
    )
    permitted = {
        APP_ROOT / "api" / "v1" / "router.py",
        APP_ROOT / "routes" / "installation_readiness_review.py",
        APP_ROOT / "installation_readiness_review" / "contract.py",
        APP_ROOT / "installation_readiness_review" / "service.py",
        APP_ROOT / "execution_permission_grant" / "contract.py",
        APP_ROOT / "execution_permission_grant" / "service.py",
    }
    consumers = {
        path
        for path in _production_python(APP_ROOT)
        if any(marker in path.read_text(encoding="utf-8") for marker in markers)
    }
    assert consumers == permitted

    effect_roots = (
        APP_ROOT / "operational_dispatch", APP_ROOT / "execution_candidates",
        APP_ROOT / "provider_intents", APP_ROOT / "actions",
        REPOSITORY_ROOT / "services" / "atlas-agent" / "app",
        REPOSITORY_ROOT / "services" / "atlas-execution-worker",
    )
    assert [
        path
        for root in effect_roots
        if root.exists()
        for path in _production_python(root)
        if any(marker in path.read_text(encoding="utf-8") for marker in markers)
    ] == []


def test_home_assistant_stays_blocked_without_deployment_artifact() -> None:
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
    mission_control = (
        REPOSITORY_ROOT / "services" / "mission-control" / "src" / "pages"
        / "InstallationReadinessReviewPage.tsx"
    ).read_text(encoding="utf-8")
    assert "Home Assistant remains non-installable and non-executable" in mission_control
