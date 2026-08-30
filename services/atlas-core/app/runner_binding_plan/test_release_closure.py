"""P5 release isolation and authority closure for Atlas v0.37."""

from __future__ import annotations

import ast
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from fastapi import FastAPI

from app.api.v1.router import router as api_v1_router
from app.runner_binding_plan.contract import (
    RunnerBindingPlanResultV1,
    RunnerBindingPlanV1,
)
from app.runner_binding_plan.test_service_store import _record, _service

APP_ROOT = Path(__file__).parents[1]
REPOSITORY_ROOT = APP_ROOT.parents[2]
PACKAGE_ROOT = Path(__file__).parent
COLLECTION = (
    "/api/v1/installation/candidate-records/"
    "{candidate_record_id}/runner-binding-plans"
)
ITEM = COLLECTION + "/{plan_id}"


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


def test_v037_openapi_is_exact_create_list_get_without_effect_siblings() -> None:
    application = FastAPI()
    application.include_router(api_v1_router)
    paths = {
        path: set(operations)
        for path, operations in application.openapi()["paths"].items()
        if "runner-binding-plans" in path
    }
    assert paths == {COLLECTION: {"get", "post"}, ITEM: {"get"}}
    all_paths = "\n".join(application.openapi()["paths"]).lower()
    for suffix in (
        "bind", "run", "execute", "start", "dispatch", "retry", "resend",
        "send", "agent", "worker", "workflow", "install", "deploy",
        "rollback", "replay", "mutation",
    ):
        assert f"runner-binding-plans/{suffix}" not in all_paths


def test_v037_models_are_binding_planned_evidence_only() -> None:
    assert RunnerBindingPlanV1.model_fields["record_state"].default == "recorded"
    assert RunnerBindingPlanV1.model_fields["lifecycle"].default == "active"
    assert RunnerBindingPlanV1.model_fields["eligibility"].default == "binding_planned"
    assert RunnerBindingPlanV1.model_fields["blockers"].default == (
        "runner_not_bound",
        "execution_start_boundary_not_defined",
    )
    assert RunnerBindingPlanV1.model_fields["evidence_only"].default is True
    assert RunnerBindingPlanResultV1.model_fields["evidence_only"].default is True
    for field in (
        "runner_registered", "runner_contacted", "runner_reserved",
        "runner_bound", "runner_binding_allowed", "execution_start_allowed",
        "execution_authorized", "installation_allowed", "dispatch_allowed",
        "retry_allowed", "resend_allowed", "agent_invocation_allowed",
        "worker_allowed", "workflow_allowed", "docker_allowed",
        "podman_allowed", "shell_allowed", "process_allowed",
        "provider_mutation_allowed", "repository_mutation_allowed",
        "in_guest_mutation_allowed", "deployment_allowed", "rollback_allowed",
        "replay_allowed",
    ):
        assert RunnerBindingPlanV1.model_fields[field].default is False


def test_v037_service_store_have_no_effect_or_replay_bypass_dependency() -> None:
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
        ".bind_runner(", ".execute_plan(", ".start_execution(", ".dispatch(",
        ".retry(", ".resend(", ".invoke_agent(", ".start_worker(",
        ".start_workflow(", ".deploy(", ".rollback(", ".replay(",
        ".release_reservation(", ".delete_reservation(",
    ):
        assert call not in source


def test_permanent_binding_plan_reservation_survives_concurrency_and_restart(
    tmp_path: Path,
) -> None:
    plan_service, plan_store, _, _, _, admission, _, runner = _service(tmp_path)
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = tuple(
            pool.map(lambda _: _record(plan_service, admission, runner), range(16))
        )
    assert sum(result.disposition == "recorded" for result in results) == 1
    assert all(
        result.disposition in {"recorded", "exact_duplicate"}
        for result in results
    )
    with sqlite3.connect(plan_store.database_path) as connection:
        assert connection.execute(
            "SELECT COUNT(*) FROM runner_binding_plans"
        ).fetchone()[0] == 1

    restarted, _, evidence, runner_reader, _, admission2, _, runner2 = _service(
        tmp_path, second=59
    )
    duplicate = _record(restarted, admission2, runner2)
    assert duplicate.disposition == "exact_duplicate"
    assert duplicate.status.lifecycle == "expired"
    assert evidence.calls == runner_reader.calls == 0
    conflict = _record(
        restarted,
        admission2,
        runner2,
        idempotency_key="cannot-bypass-binding-subject-reservation",
    )
    assert conflict.error.error_code == "expired"
    with sqlite3.connect(plan_store.database_path) as connection:
        assert connection.execute(
            "SELECT COUNT(*) FROM runner_binding_plans"
        ).fetchone()[0] == 1


def test_v037_persistence_is_secret_free_and_has_no_effect_consumer(
    tmp_path: Path,
) -> None:
    plan_service, plan_store, _, _, _, admission, _, runner = _service(tmp_path)
    result = _record(plan_service, admission, runner)
    persisted = plan_store.database_path.read_bytes()
    for marker in (
        b"runner-binding-plan-key-1", b"credential", b"Authorization",
        b"Bearer ", b"command_argv", b"mount_source", b"endpoint_url",
    ):
        assert marker not in persisted
        assert marker not in result.model_dump_json().encode()

    markers = (
        "app.runner_binding_plan", "RunnerBindingPlanV1",
        "runner-binding-plan-v1", "runner-binding-plans",
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


def test_v037_home_assistant_stays_blocked_without_deployment_artifact() -> None:
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
        / "installation" / "RunnerBindingPlans.tsx"
    ).read_text(encoding="utf-8")
    assert (
        "Home Assistant remains blocked, non-installable, non-executable" in component
    )
