from __future__ import annotations

import ast
import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path

from app.worker_admission_stub import service, store
from app.worker_admission_stub.contract import WorkerAdmissionStubCreateV1
from app.worker_admission_stub.service import create_worker_admission_stub_service
from app.worker_admission_stub.store import WorkerAdmissionStubStore
from app.worker_admission_stub.test_contract import (
    INTENT_ID,
    STUB_ID,
    _input,
)


class Reader:
    def __init__(self, value) -> None:
        self.value = value
        self.calls = 0

    def read_owned(self, **_kwargs):
        self.calls += 1
        return self.value


class Factory:
    def __init__(self, value: str) -> None:
        self.value = value
        self.calls = 0

    def __call__(self) -> str:
        self.calls += 1
        return self.value


def _clock(second: int = 33):
    instant = datetime(2026, 8, 27, 12, 0, tzinfo=UTC) + timedelta(seconds=second)
    return lambda: instant


def _fixtures(tmp_path: Path):
    validation = _input(tmp_path)
    return (
        validation.runner_binding_plan,
        validation.runner_binding_plan_status,
        validation.worker_reference,
    )


def _service(
    tmp_path: Path,
    *,
    evidence=None,
    worker=None,
    second: int = 33,
    quota: int = 16,
):
    plan, status, reference = _fixtures(tmp_path)
    evidence_reader = Reader(evidence if evidence is not None else (plan, status, False))
    worker_reader = Reader(reference if worker is None else worker)
    stub_factory = Factory(STUB_ID)
    intent_factory = Factory(INTENT_ID)
    stub_store = WorkerAdmissionStubStore(
        tmp_path / "worker-admission-stubs.sqlite3",
        max_records_per_operator=quota,
    )
    stub_service = create_worker_admission_stub_service(
        evidence_reader=evidence_reader,
        worker_reference_reader=worker_reader,
        store=stub_store,
        clock=_clock(second),
        stub_id_factory=stub_factory,
        intent_id_factory=intent_factory,
    )
    return (
        stub_service,
        stub_store,
        evidence_reader,
        worker_reader,
        stub_factory,
        intent_factory,
        plan,
        status,
        reference,
    )


def _create(plan, worker) -> WorkerAdmissionStubCreateV1:
    return WorkerAdmissionStubCreateV1(
        runner_binding_plan_id=plan.plan_id,
        runner_binding_plan_fingerprint=plan.plan_fingerprint,
        runner_binding_plan_valid_until=plan.valid_until,
        worker_reference_id=worker.worker_reference_id,
        worker_reference_fingerprint=worker.reference_fingerprint,
        inherited_limits_fingerprint=plan.limits.limits_fingerprint,
    )


def _record(stub_service, plan, worker, **changes):
    values = {
        "authenticated_operator_id": plan.operator_id,
        "permission_verified": True,
        "candidate_record_id": plan.candidate_record_id,
        "idempotency_key": "worker-admission-stub-key-1",
        "correlation_id": "worker-admission-stub-correlation-1",
    }
    values.update(changes)
    return stub_service.create(_create(plan, worker), **values)


def test_create_get_list_and_restart_safe_readback(tmp_path: Path) -> None:
    stub_service, stub_store, evidence_reader, worker_reader, *_rest, plan, _, worker = _service(tmp_path)
    created = _record(stub_service, plan, worker)
    assert created.disposition == "recorded"
    assert created.status.lifecycle == "active"
    assert created.status.eligibility == "worker_admission_stubbed"
    assert created.stub.eligibility == "worker_admission_stubbed"
    assert evidence_reader.calls == worker_reader.calls == 1
    assert not created.stub.worker_started
    assert not created.stub.work_enqueued
    assert not created.stub.execution_authorized

    restarted = create_worker_admission_stub_service(
        evidence_reader=Reader(None),
        worker_reference_reader=Reader(None),
        store=WorkerAdmissionStubStore(stub_store.database_path),
        clock=_clock(50),
        stub_id_factory=Factory("bcb26247-12a3-4818-9053-59a83eb4312a"),
        intent_id_factory=Factory("0dfc9761-fbc6-54c6-8a5a-4e2446e2c4df"),
    )
    readback = restarted.get(
        authenticated_operator_id=plan.operator_id,
        permission_verified=True,
        stub_id=STUB_ID,
        correlation_id="readback",
    )
    assert readback.stub == created.stub
    assert readback.status.lifecycle == "expired"
    listed = restarted.list(
        authenticated_operator_id=plan.operator_id,
        permission_verified=True,
        correlation_id="list",
    )
    assert tuple(item.stub.stub_id for item in listed) == (STUB_ID,)
    assert restarted.get(
        authenticated_operator_id="operator-b",
        permission_verified=True,
        stub_id=STUB_ID,
        correlation_id="foreign",
    ).error.error_code == "not_found"
    assert restarted.list(
        authenticated_operator_id="operator-b",
        permission_verified=True,
        correlation_id="foreign-list",
    ) == ()


def test_exact_duplicate_is_zero_reader_and_raw_key_is_not_persisted(tmp_path: Path) -> None:
    stub_service, stub_store, evidence_reader, worker_reader, stub_factory, intent_factory, plan, _, worker = _service(tmp_path)
    created = _record(stub_service, plan, worker)
    duplicate = _record(stub_service, plan, worker)
    assert duplicate.disposition == "exact_duplicate"
    assert duplicate.stub == created.stub
    assert evidence_reader.calls == worker_reader.calls == 1
    assert stub_factory.calls == intent_factory.calls == 1
    with sqlite3.connect(stub_store.database_path) as connection:
        schema = connection.execute(
            "SELECT sql FROM sqlite_master WHERE name = 'worker_admission_stubs'"
        ).fetchone()[0]
        row = connection.execute("SELECT * FROM worker_admission_stubs").fetchone()
    assert "worker-admission-stub-key-1" not in schema
    assert all("worker-admission-stub-key-1" not in str(value) for value in row)


def test_idempotency_conflict_and_permanent_subject_reservation(tmp_path: Path) -> None:
    stub_service, _, _, _, _, _, plan, _, worker = _service(tmp_path)
    assert _record(stub_service, plan, worker).disposition == "recorded"
    subject_retry = _record(
        stub_service,
        plan,
        worker,
        idempotency_key="another-permanent-key",
    )
    assert subject_retry.error.error_code == "conflict"
    changed = _create(plan, worker).model_copy(
        update={"runner_binding_plan_valid_until": "2026-08-27T12:00:44Z"}
    )
    conflict = stub_service.create(
        changed,
        authenticated_operator_id=plan.operator_id,
        permission_verified=True,
        candidate_record_id=plan.candidate_record_id,
        idempotency_key="worker-admission-stub-key-1",
        correlation_id="conflict",
    )
    assert conflict.error.error_code == "conflict"


def test_auth_permission_owner_missing_and_redaction_fail_closed(tmp_path: Path) -> None:
    stub_service, _, evidence_reader, _, _, _, plan, _, worker = _service(tmp_path)
    assert _record(stub_service, plan, worker, permission_verified=False).error.error_code == "unauthorized"
    assert _record(stub_service, plan, worker, authenticated_operator_id=None).error.error_code == "unauthenticated"
    assert evidence_reader.calls == 0
    assert _record(stub_service, plan, worker, authenticated_operator_id="operator-b").error.error_code == "not_found"
    missing, *_tail = _service(tmp_path / "missing")
    missing._evidence_reader = Reader(None)  # explicitly injected test dependency
    missing_result = _record(missing, plan, worker, correlation_id="secret/internal/path")
    assert missing_result.error.error_code == "not_found"
    assert "secret/internal/path" not in missing_result.model_dump_json()


def test_stale_home_assistant_worker_and_limit_mismatch_are_blocked(tmp_path: Path) -> None:
    stale, _, _, _, _, _, plan, _, worker = _service(tmp_path / "stale", second=50)
    assert _record(stale, plan, worker).error.error_code == "expired"

    plan2, status2, worker2 = _fixtures(tmp_path / "home-fixture")
    home, *_ = _service(
        tmp_path / "home", evidence=(plan2, status2, True), worker=worker2
    )
    assert _record(home, plan2, worker2).error.error_code == "not_eligible"

    mismatch, _, _, _, _, _, plan3, _, worker3 = _service(tmp_path / "mismatch")
    bad = _create(plan3, worker3).model_copy(
        update={
            "worker_reference_fingerprint": worker3.reference_fingerprint.model_copy(
                update={"value": "f" * 64}
            )
        }
    )
    result = mismatch.create(
        bad,
        authenticated_operator_id=plan3.operator_id,
        permission_verified=True,
        candidate_record_id=plan3.candidate_record_id,
        idempotency_key="mismatch-key-1234",
        correlation_id="mismatch",
    )
    assert result.error.error_code == "not_eligible"
    limits = _create(plan3, worker3).model_copy(
        update={
            "inherited_limits_fingerprint": plan3.limits.limits_fingerprint.model_copy(
                update={"value": "e" * 64}
            )
        }
    )
    assert mismatch.create(
        limits,
        authenticated_operator_id=plan3.operator_id,
        permission_verified=True,
        candidate_record_id=plan3.candidate_record_id,
        idempotency_key="limits-mismatch-key",
        correlation_id="limits",
    ).error.error_code == "not_eligible"


def test_quota_record_bounds_and_corruption_fail_closed(tmp_path: Path, monkeypatch) -> None:
    quota_service, _, _, _, _, _, plan, _, worker = _service(tmp_path / "quota", quota=0)
    assert _record(quota_service, plan, worker).error.error_code == "quota_exceeded"

    bounded, _, _, _, _, _, plan2, _, worker2 = _service(tmp_path / "bounded")
    monkeypatch.setattr(store, "MAX_MODEL_BYTES", 1)
    assert _record(bounded, plan2, worker2).error.error_code == "unavailable"
    monkeypatch.undo()

    clean, stub_store, _, _, _, _, plan3, _, worker3 = _service(tmp_path / "corrupt")
    assert _record(clean, plan3, worker3).disposition == "recorded"
    with sqlite3.connect(stub_store.database_path) as connection:
        connection.execute("UPDATE worker_admission_stubs SET stub_json = ?", ("{}",))
    assert clean.get(
        authenticated_operator_id=plan3.operator_id,
        permission_verified=True,
        stub_id=STUB_ID,
        correlation_id="corrupt",
    ).error.error_code == "unavailable"


def test_service_store_have_no_effect_imports_calls_or_production_consumers() -> None:
    root = Path(__file__).resolve().parents[1]
    forbidden_imports = {
        "subprocess", "docker", "podman", "requests", "httpx", "socket",
        "agent", "dispatch", "execution_worker", "provider", "repository", "workflow",
    }
    for module in (service, store):
        tree = ast.parse(Path(module.__file__).read_text())
        imported = {
            name
            for node in ast.walk(tree)
            if isinstance(node, (ast.Import, ast.ImportFrom))
            for name in (
                [alias.name for alias in node.names]
                if isinstance(node, ast.Import)
                else [node.module or ""]
            )
        }
        assert not [name for name in imported if any(term in name for term in forbidden_imports)]
        assert not any(
            isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name in {"enqueue", "execute", "dispatch", "retry", "resend", "start", "start_worker"}
            for node in ast.walk(tree)
        )
    consumers = []
    for path in root.rglob("*.py"):
        if path.parent.name == "worker_admission_stub" or path.name.startswith("test_"):
            continue
        source = path.read_text()
        if "worker_admission_stub.service" in source or "WorkerAdmissionStubService" in source:
            consumers.append(path)
    assert consumers == []


def test_store_has_no_update_delete_release_consume_or_enqueue_api() -> None:
    assert not any(
        hasattr(WorkerAdmissionStubStore, name)
        for name in ("update", "delete", "release", "consume", "enqueue", "start_worker")
    )
    source = Path(store.__file__).read_text()
    assert "UPDATE worker_admission_stubs" not in source
    assert "DELETE FROM worker_admission_stubs" not in source
