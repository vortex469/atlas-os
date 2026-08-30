"""P5 release isolation and authority closure for Atlas v0.38."""

from __future__ import annotations

import ast
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from fastapi import FastAPI

from app.api.v1.router import router as api_v1_router
from app.worker_admission_stub.contract import (
    STUB_BLOCKERS,
    WorkerAdmissionStubResultV1,
    WorkerAdmissionStubV1,
)
from app.worker_admission_stub.test_service_store import _record, _service

APP_ROOT = Path(__file__).parents[1]
REPOSITORY_ROOT = APP_ROOT.parents[2]
PACKAGE_ROOT = Path(__file__).parent
COLLECTION = (
    "/api/v1/installation/candidate-records/"
    "{candidate_record_id}/worker-admission-stubs"
)
ITEM = COLLECTION + "/{stub_id}"


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


def test_v038_openapi_is_exact_create_list_get_without_effect_siblings() -> None:
    application = FastAPI()
    application.include_router(api_v1_router)
    paths = {
        path: set(operations)
        for path, operations in application.openapi()["paths"].items()
        if "worker-admission-stubs" in path
    }
    assert paths == {COLLECTION: {"get", "post"}, ITEM: {"get"}}
    all_paths = "\n".join(application.openapi()["paths"]).lower()
    for suffix in (
        "worker", "start", "enqueue", "queue", "run", "execute", "bind",
        "dispatch", "retry", "resend", "send", "agent", "workflow",
        "install", "deploy", "rollback", "replay", "mutation",
    ):
        assert f"worker-admission-stubs/{suffix}" not in all_paths


def test_v038_models_are_stubbed_evidence_only_and_fixed_false() -> None:
    assert WorkerAdmissionStubV1.model_fields["record_state"].default == "recorded"
    assert WorkerAdmissionStubV1.model_fields["lifecycle"].default == "active"
    assert (
        WorkerAdmissionStubV1.model_fields["eligibility"].default
        == "worker_admission_stubbed"
    )
    assert WorkerAdmissionStubV1.model_fields["blockers"].default == STUB_BLOCKERS
    assert WorkerAdmissionStubV1.model_fields["evidence_only"].default is True
    assert WorkerAdmissionStubResultV1.model_fields["evidence_only"].default is True
    for field in (
        "runner_binding_allowed", "worker_registered", "worker_contacted",
        "worker_reserved", "worker_bound", "worker_started", "queue_created",
        "queue_allowed", "work_enqueued", "enqueue_allowed", "dispatch_allowed",
        "execution_start_allowed", "execution_authorized", "installation_allowed",
        "retry_allowed", "resend_allowed", "agent_invocation_allowed",
        "workflow_allowed", "docker_allowed", "podman_allowed", "shell_allowed",
        "process_allowed", "provider_mutation_allowed",
        "repository_mutation_allowed", "in_guest_mutation_allowed",
        "deployment_allowed", "rollback_allowed", "replay_allowed",
    ):
        assert WorkerAdmissionStubV1.model_fields[field].default is False


def test_v038_service_store_have_no_effect_or_replay_bypass_dependency() -> None:
    forbidden_imports = (
        "agent", "dispatch", "docker", "http", "network", "provider",
        "repository", "requests", "socket", "subprocess", "transport",
        "workflow", "execution_worker",
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
        ".bind_runner(", ".start_worker(", ".enqueue(", ".create_queue(",
        ".execute_worker(", ".start_execution(", ".dispatch(", ".retry(",
        ".resend(", ".invoke_agent(",
        ".start_workflow(", ".deploy(", ".rollback(", ".replay(",
        ".release_reservation(", ".delete_reservation(",
    ):
        assert call not in source


def test_permanent_worker_admission_reservation_survives_concurrency_and_restart(
    tmp_path: Path,
) -> None:
    stub_service, stub_store, _, _, _, _, plan, _, worker = _service(tmp_path)
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = tuple(
            pool.map(lambda _: _record(stub_service, plan, worker), range(16))
        )
    assert sum(result.disposition == "recorded" for result in results) == 1
    assert all(
        result.disposition in {"recorded", "exact_duplicate"}
        for result in results
    )
    with sqlite3.connect(stub_store.database_path) as connection:
        assert connection.execute(
            "SELECT COUNT(*) FROM worker_admission_stubs"
        ).fetchone()[0] == 1

    fresh, _, _, _, _, _, plan2, _, worker2 = _service(tmp_path)
    conflict = _record(
        fresh,
        plan2,
        worker2,
        idempotency_key="cannot-bypass-worker-admission-subject",
    )
    assert conflict.error.error_code == "conflict"

    restarted, _, evidence, worker_reader, _, _, plan3, _, worker3 = _service(
        tmp_path, second=59
    )
    duplicate = _record(restarted, plan3, worker3)
    assert duplicate.disposition == "exact_duplicate"
    assert duplicate.status.lifecycle == "expired"
    assert evidence.calls == worker_reader.calls == 0
    with sqlite3.connect(stub_store.database_path) as connection:
        assert connection.execute(
            "SELECT COUNT(*) FROM worker_admission_stubs"
        ).fetchone()[0] == 1


def test_v038_persistence_is_secret_free_and_has_no_effect_consumer(
    tmp_path: Path,
) -> None:
    stub_service, stub_store, _, _, _, _, plan, _, worker = _service(tmp_path)
    result = _record(stub_service, plan, worker)
    persisted = stub_store.database_path.read_bytes()
    for marker in (
        b"worker-admission-stub-key-1", b"credential", b"Authorization",
        b"Bearer ", b"command_argv", b"mount_source", b"endpoint_url",
        b"worker_address", b"provider_payload", b"stdout", b"stderr",
    ):
        assert marker not in persisted
        assert marker not in result.model_dump_json().encode()

    markers = (
        "app.worker_admission_stub", "WorkerAdmissionStubV1",
        "worker-admission-stub-v1", "worker-admission-stubs",
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


def test_v038_home_assistant_stays_blocked_without_deployment_artifact() -> None:
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
        / "installation" / "WorkerAdmissionStubs.tsx"
    ).read_text(encoding="utf-8")
    assert "worker admission remains blocked" in component
    assert "non-installable and non-executable" in component
