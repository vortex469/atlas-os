"""P5 release isolation and authority closure for Atlas v0.36."""

from __future__ import annotations

import ast
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from fastapi import FastAPI

from app.api.v1.router import router as api_v1_router
from app.installation_execution_admission.contract import (
    InstallationExecutionAdmissionResultV1,
    InstallationExecutionAdmissionV1,
    InstallationRunnerEligibilityV1,
)
from app.installation_execution_admission.test_service_store import (
    _record,
    _service,
)

APP_ROOT = Path(__file__).parents[1]
REPOSITORY_ROOT = APP_ROOT.parents[2]
PACKAGE_ROOT = Path(__file__).parent
COLLECTION = (
    "/api/v1/installation/candidate-records/"
    "{candidate_record_id}/execution-admissions"
)
ITEM = COLLECTION + "/{admission_id}"


def _production_python(root: Path) -> tuple[Path, ...]:
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


def test_v036_openapi_is_exact_create_list_get_without_effect_siblings() -> None:
    application = FastAPI()
    application.include_router(api_v1_router)
    paths = {
        path: set(operations)
        for path, operations in application.openapi()["paths"].items()
        if "execution-admissions" in path
    }
    assert paths == {COLLECTION: {"get", "post"}, ITEM: {"get"}}
    all_paths = "\n".join(application.openapi()["paths"]).lower()
    for suffix in (
        "runner", "execute", "execution", "start", "dispatch", "retry",
        "resend", "send", "agent", "worker", "workflow", "install",
        "deploy", "rollback", "replay", "mutation",
    ):
        assert f"execution-admissions/{suffix}" not in all_paths


def test_v036_models_are_admission_gated_evidence_only() -> None:
    assert InstallationRunnerEligibilityV1.model_fields["admission_gated"].default
    for model in (InstallationExecutionAdmissionV1, InstallationExecutionAdmissionResultV1):
        assert model.model_fields["evidence_only"].default is True
    assert InstallationExecutionAdmissionV1.model_fields["readiness"].default == "admission_gated"
    for field in (
        "execution_start_allowed", "runner_binding_allowed",
        "execution_authorized", "installation_allowed", "dispatch_allowed",
        "retry_allowed", "resend_allowed", "agent_invocation_allowed",
        "worker_allowed", "workflow_allowed", "docker_allowed",
        "podman_allowed", "shell_allowed", "process_allowed",
        "provider_mutation_allowed", "repository_mutation_allowed",
        "in_guest_mutation_allowed", "deployment_allowed", "rollback_allowed",
        "replay_allowed",
    ):
        assert InstallationExecutionAdmissionV1.model_fields[field].default is False


def test_v036_service_store_have_no_effect_or_replay_bypass_dependency() -> None:
    forbidden_imports = (
        "agent", "dispatch", "docker", "http", "network", "provider",
        "repository", "requests", "runner", "socket", "subprocess",
        "transport", "workflow", "worker",
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
        ".bind_runner(", ".execute_admission(", ".start_execution(", ".dispatch(",
        ".retry(", ".resend(", ".invoke_agent(", ".start_worker(",
        ".start_workflow(", ".deploy(", ".rollback(", ".replay(",
        ".release_reservation(", ".delete_reservation(",
    ):
        assert call not in source


def test_permanent_admission_reservation_survives_concurrency_and_restart(
    tmp_path: Path,
) -> None:
    admission_service, admission_store, _, _, grant, _ = _service(tmp_path)
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = tuple(pool.map(lambda _: _record(admission_service, grant), range(16)))
    assert sum(result.disposition == "recorded" for result in results) == 1
    assert all(result.disposition in {"recorded", "exact_duplicate"} for result in results)
    with sqlite3.connect(admission_store.database_path) as connection:
        assert connection.execute(
            "SELECT COUNT(*) FROM installation_execution_admissions"
        ).fetchone()[0] == 1

    restarted, _, reader, factory, restarted_grant, _ = _service(tmp_path, second=59)
    duplicate = _record(restarted, restarted_grant)
    assert duplicate.disposition == "exact_duplicate"
    assert duplicate.status.lifecycle == "expired"
    assert reader.calls == 0 and factory.calls == 0
    conflict = _record(
        restarted,
        restarted_grant,
        idempotency_key="cannot-bypass-admission-subject-reservation",
    )
    assert conflict.error.error_code == "conflict"


def test_v036_evidence_has_no_effect_or_agent_consumer() -> None:
    markers = (
        "installation_execution_admission",
        "InstallationExecutionAdmissionV1",
        "installation-execution-admission-v1",
    )
    effect_roots = (
        APP_ROOT / "operational_dispatch",
        APP_ROOT / "execution_candidates",
        APP_ROOT / "provider_intents",
        APP_ROOT / "actions",
        REPOSITORY_ROOT / "services" / "atlas-agent" / "app",
        REPOSITORY_ROOT / "services" / "atlas-execution-worker",
    )
    violations = [
        f"{path.relative_to(REPOSITORY_ROOT)} -> {marker}"
        for root in effect_roots
        if root.exists()
        for path in _production_python(root)
        for marker in markers
        if marker in path.read_text(encoding="utf-8")
    ]
    assert violations == []


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
    component = (
        REPOSITORY_ROOT / "services" / "mission-control" / "src" / "features"
        / "installation" / "InstallationExecutionAdmissions.tsx"
    ).read_text(encoding="utf-8")
    assert "Home Assistant remains blocked, non-installable, and non-executable" in component
