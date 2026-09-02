"""P5 release isolation and authority closure for Atlas v0.40."""

from __future__ import annotations

import ast
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from fastapi import FastAPI

from app.api.v1.router import router as api_v1_router
from app.worker_intake_admission.contract import (
    ADMISSION_BLOCKERS,
    NoAuthorityV1,
    WorkerIntakeAdmissionEvaluationV1,
    WorkerIntakeAdmissionResultV1,
    WorkerIntakeAdmissionV1,
    evaluate_worker_intake_admission,
)
from app.worker_intake_admission.store import WorkerIntakeAdmissionStore
from app.worker_intake_admission.test_contract import ADMISSION_ID, _input
from app.worker_intake_admission.test_service_store import (
    Factory,
    Reader,
    _record,
    _service,
)

APP_ROOT = Path(__file__).parents[1]
REPOSITORY_ROOT = APP_ROOT.parents[2]
PACKAGE_ROOT = Path(__file__).parent
COLLECTION = (
    "/api/v1/installation/candidate-records/"
    "{candidate_record_id}/worker-intake-admissions"
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


def test_v040_integrated_openapi_is_exact_create_list_get_without_effect_siblings() -> None:
    application = FastAPI()
    application.include_router(api_v1_router)
    paths = {
        path: set(operations)
        for path, operations in application.openapi()["paths"].items()
        if "worker-intake-admissions" in path
    }
    assert paths == {COLLECTION: {"get", "post"}, ITEM: {"get"}}
    joined_paths = "\n".join(application.openapi()["paths"]).lower()
    for suffix in (
        "enqueue",
        "dequeue",
        "poll",
        "claim",
        "lease",
        "worker",
        "start",
        "run",
        "execute",
        "dispatch",
        "retry",
        "resend",
        "send",
        "agent",
        "workflow",
        "install",
        "deploy",
        "rollback",
        "release",
        "replay",
        "mutation",
    ):
        assert f"worker-intake-admissions/{suffix}" not in joined_paths


def test_v040_models_are_fixed_false_evidence_only() -> None:
    for model in (
        NoAuthorityV1,
        WorkerIntakeAdmissionV1,
        WorkerIntakeAdmissionResultV1,
        WorkerIntakeAdmissionEvaluationV1,
    ):
        assert model.model_fields["evidence_only"].default is True
    for field in (
        "live_enqueue_allowed",
        "dequeue_allowed",
        "queue_polling_allowed",
        "worker_contact_allowed",
        "worker_start_allowed",
        "execution_start_allowed",
        "runner_binding_allowed",
        "dispatch_allowed",
        "retry_allowed",
        "resend_allowed",
        "agent_invocation_allowed",
        "workflow_start_allowed",
        "docker_execution_allowed",
        "podman_execution_allowed",
        "shell_execution_allowed",
        "process_execution_allowed",
        "provider_mutation_allowed",
        "repository_mutation_allowed",
        "in_guest_mutation_allowed",
        "installation_allowed",
        "deployment_allowed",
        "rollback_allowed",
        "replay_bypass_allowed",
    ):
        assert WorkerIntakeAdmissionV1.model_fields[field].default is False
    assert WorkerIntakeAdmissionV1.model_fields["blockers"].default == ADMISSION_BLOCKERS


def test_v040_service_store_have_no_effect_or_forbidden_authority_dependency() -> None:
    forbidden_imports = (
        "agent",
        "dispatch",
        "docker",
        "http",
        "network",
        "podman",
        "provider",
        "repository",
        "requests",
        "socket",
        "subprocess",
        "transport",
        "workflow",
    )
    violations = [
        f"{path.name} -> {imported}"
        for path in (
            PACKAGE_ROOT / "contract.py",
            PACKAGE_ROOT / "service.py",
            PACKAGE_ROOT / "store.py",
        )
        for imported in _imports(path)
        if any(marker in imported.lower() for marker in forbidden_imports)
    ]
    assert violations == []
    source = "\n".join(
        path.read_text(encoding="utf-8").lower()
        for path in (
            PACKAGE_ROOT / "contract.py",
            PACKAGE_ROOT / "service.py",
            PACKAGE_ROOT / "store.py",
        )
    )
    for call in (
        "subprocess",
        "os.system",
        "create_subprocess",
        "docker.",
        "podman.",
        ".enqueue(",
        ".dequeue(",
        ".poll(",
        ".claim(",
        ".lease(",
        ".bind_runner(",
        ".execute_admission(",
        ".start_execution(",
        ".dispatch(",
        ".retry(",
        ".resend(",
        ".invoke_agent(",
        ".start_worker(",
        ".start_workflow(",
        ".deploy(",
        ".rollback(",
        ".release_reservation(",
        ".delete_reservation(",
    ):
        assert call not in source


def test_permanent_intake_subject_survives_concurrency_restart_and_expiry(
    tmp_path: Path,
) -> None:
    admission_service, admission_store, *tail = _service(tmp_path)
    reservation = tail[5]
    create = tail[9]
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = tuple(
            pool.map(
                lambda _: _record(admission_service, reservation, create),
                range(16),
            )
        )
    assert sum(result.ok for result in results) == 16
    assert {result.admission.admission_id for result in results if result.admission} == {
        ADMISSION_ID
    }
    with sqlite3.connect(admission_store.database_path) as connection:
        assert connection.execute(
            "SELECT COUNT(*) FROM worker_intake_admissions"
        ).fetchone()[0] == 1

    restarted = _service(tmp_path, second=40)[0]
    duplicate = _record(restarted, reservation, create)
    assert duplicate.ok
    assert duplicate.admission == results[0].admission
    conflict = _record(
        restarted,
        reservation,
        create,
        idempotency_key="cannot-bypass-worker-intake-subject",
    )
    assert conflict.error.error_code == "conflict"

    read_only = WorkerIntakeAdmissionStore(admission_store.database_path)
    assert read_only.get(
        operator_id=reservation.operator_id,
        admission_id=ADMISSION_ID,
    ) == results[0].admission
    expired_replay = _record(_service(tmp_path, second=59)[0], reservation, create)
    assert expired_replay.ok
    expired_subject_replay = _record(
        _service(tmp_path, second=59)[0],
        reservation,
        create,
        idempotency_key="cannot-bypass-expired-worker-intake",
    )
    assert expired_subject_replay.error.error_code in {
        "conflict",
        "evidence_expired",
        "evidence_stale",
    }


def test_exact_duplicate_after_restart_does_not_re_read_or_reissue_ids(
    tmp_path: Path,
) -> None:
    created_service, admission_store, *tail = _service(tmp_path)
    reservation = tail[5]
    create = tail[9]
    assert _record(created_service, reservation, create).ok

    evidence_reader = Reader(None)
    identity_reader = Reader(None)
    intake_reader = Reader(None)
    admission_factory = Factory("6f80fe47-d0dc-4449-b65d-bdb0e0a365e3")
    decision_factory = Factory("f87d1208-4b38-5a6d-8a79-fc9887367c0f")
    restarted = _service(tmp_path / "unused")[0]
    restarted._store = WorkerIntakeAdmissionStore(admission_store.database_path)
    restarted._evidence_reader = evidence_reader
    restarted._worker_identity_reader = identity_reader
    restarted._worker_intake_reference_reader = intake_reader
    restarted._admission_id_factory = admission_factory
    restarted._decision_id_factory = decision_factory

    duplicate = _record(restarted, reservation, create)
    assert duplicate.ok
    assert duplicate.admission.admission_id == ADMISSION_ID
    assert evidence_reader.calls == identity_reader.calls == intake_reader.calls == 0
    assert admission_factory.calls == decision_factory.calls == 0


def test_v040_evidence_has_no_agent_execution_worker_or_effect_consumer() -> None:
    markers = (
        "worker_intake_admission",
        "WorkerIntakeAdmissionV1",
        "worker-intake-admission-v1",
        "worker-intake-admissions",
    )
    effect_roots = (
        APP_ROOT / "operational_dispatch",
        APP_ROOT / "execution_candidates",
        APP_ROOT / "provider_intents",
        APP_ROOT / "actions",
        APP_ROOT / "deploy",
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


def test_home_assistant_blocked_golden_has_no_record_or_deployment_artifact(
    tmp_path: Path,
) -> None:
    blocked = evaluate_worker_intake_admission(
        {**_input(tmp_path).model_dump(mode="python"), "home_assistant": True}
    )
    assert blocked.eligibility == "blocked"
    assert blocked.blockers == ("installation_capability_unsupported",)
    assert blocked.queue_reservation_evidence is None
    assert blocked.recognized_v039_queue_reservation_count == 0
    assert not blocked.admission_record_build_allowed
    assert not blocked.live_enqueue_allowed
    assert not blocked.worker_start_allowed
    assert not blocked.execution_start_allowed

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
        REPOSITORY_ROOT
        / "services"
        / "mission-control"
        / "src"
        / "features"
        / "installation"
        / "WorkerIntakeAdmissions.tsx"
    ).read_text(encoding="utf-8")
    assert "For Home Assistant, worker intake admission remains blocked" in component
    assert "non-installable and non-executable" in component
