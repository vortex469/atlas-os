from __future__ import annotations

import ast
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path

from app.one_shot_dequeue_worker_binding import service, store
from app.one_shot_dequeue_worker_binding.contract import (
    PERMISSION,
    OneShotDequeueWorkerBindingAuthorityContextV1,
    OneShotDequeueWorkerBindingValidationInputV1,
    build_audit,
    build_binding,
    build_collection,
    build_reservations,
    opaque_fingerprint,
)
from app.one_shot_dequeue_worker_binding.service import (
    create_one_shot_dequeue_worker_binding_service,
)
from app.one_shot_dequeue_worker_binding.store import (
    OneShotDequeueWorkerBindingStore,
)
from app.one_shot_dequeue_worker_binding.test_contract import _facts


class Reader:
    def __init__(self, value) -> None:
        self.value = value
        self.calls = 0

    def read_owned(self, **_kwargs):
        self.calls += 1
        return self.value


def _clock(second: int = 36):
    instant = datetime(2026, 8, 27, 12, 0, tzinfo=UTC) + timedelta(seconds=second)
    return lambda: instant


def _service(
    tmp_path: Path,
    *,
    dequeue_evidence=None,
    worker_evidence=None,
    second: int = 36,
    quota: int = 16,
    max_model_bytes: int = 192 * 1024,
    enabled: bool = True,
):
    dequeue, dequeue_status, worker, worker_status, create = _facts(tmp_path)
    dequeue_reader = Reader(
        dequeue_evidence if dequeue_evidence is not None else (dequeue, dequeue_status)
    )
    worker_reader = Reader(
        worker_evidence if worker_evidence is not None else (worker, worker_status)
    )
    binding_store = OneShotDequeueWorkerBindingStore(
        tmp_path / "one-shot-dequeue-worker-binding.sqlite3",
        max_records_per_operator=quota,
        max_model_bytes=max_model_bytes,
    )
    binding_service = create_one_shot_dequeue_worker_binding_service(
        dequeue_reader=dequeue_reader,
        worker_reader=worker_reader,
        store=binding_store,
        clock=_clock(second),
        enabled=enabled,
    )
    return (
        binding_service,
        binding_store,
        dequeue_reader,
        worker_reader,
        dequeue,
        dequeue_status,
        worker,
        worker_status,
        create,
    )


def _record(binding_service, dequeue, create, **changes):
    values = {
        "authenticated_operator_id": dequeue.operator_id,
        "permission_verified": True,
        "candidate_record_id": dequeue.candidate_record_id,
        "idempotency_key": "one-shot-dequeue-worker-binding-key-1",
        "correlation_id": "one-shot-dequeue-worker-binding-correlation-1",
    }
    values.update(changes)
    return binding_service.create(create, **values)


def test_create_get_list_and_restart_safe_owner_readback(tmp_path: Path) -> None:
    (
        binding_service,
        binding_store,
        dequeue_reader,
        worker_reader,
        dequeue,
        _dequeue_status,
        _worker,
        _worker_status,
        create,
    ) = _service(tmp_path)
    created = _record(binding_service, dequeue, create)
    assert created.ok
    assert created.record.binding_state == "readiness_gated"
    assert created.status.lifecycle == "active"
    assert dequeue_reader.calls == 1
    assert worker_reader.calls == 1
    assert not created.record.worker_contact_allowed
    assert not created.record.worker_start_allowed
    assert not created.record.agent_invocation_allowed
    assert not created.record.execution_start_allowed
    assert not created.record.runtime_contact_allowed
    assert not created.record.store_contact_allowed

    restarted = create_one_shot_dequeue_worker_binding_service(
        dequeue_reader=Reader(None),
        worker_reader=Reader(None),
        store=OneShotDequeueWorkerBindingStore(binding_store.database_path),
        clock=_clock(70),
    )
    readback = restarted.get(
        authenticated_operator_id=dequeue.operator_id,
        permission_verified=True,
        binding_id=created.record.binding_id,
        correlation_id="readback",
    )
    assert readback.record == created.record
    assert readback.status.lifecycle == "expired"
    listed = restarted.list(
        authenticated_operator_id=dequeue.operator_id,
        permission_verified=True,
        candidate_record_id=dequeue.candidate_record_id,
        correlation_id="list",
    )
    assert tuple(item.binding_id for item in listed.items) == (
        created.record.binding_id,
    )
    assert restarted.get(
        authenticated_operator_id="operator-b",
        permission_verified=True,
        binding_id=created.record.binding_id,
        correlation_id="foreign",
    ).error.error_code == "not_found"


def test_default_disabled_auth_permission_missing_and_zero_effect(
    tmp_path: Path,
) -> None:
    binding_service, binding_store, dequeue_reader, worker_reader, dequeue, *_rest = (
        _service(tmp_path, enabled=False)
    )
    create = _rest[-1]
    assert _record(binding_service, dequeue, create).error.error_code == (
        "installation_capability_unsupported"
    )
    assert _record(
        binding_service, dequeue, create, authenticated_operator_id=None
    ).error.error_code == "unauthenticated"
    assert _record(
        binding_service, dequeue, create, permission_verified=False
    ).error.error_code == "forbidden"
    assert dequeue_reader.calls == 0
    assert worker_reader.calls == 0
    assert binding_store.list_owned(
        operator_id=dequeue.operator_id,
        candidate_record_id=dequeue.candidate_record_id,
    ) == ()

    missing = _service(tmp_path / "missing", dequeue_evidence=None)
    missing[2].value = None
    result = _record(
        missing[0],
        missing[4],
        missing[8],
        correlation_id="secret/internal/path/token",
    )
    assert result.error.error_code == "not_found"
    assert missing[3].calls == 1
    assert "secret/internal/path/token" not in result.model_dump_json()


def test_exact_duplicate_zero_reader_and_secret_free_persistence(
    tmp_path: Path,
) -> None:
    binding_service, binding_store, dequeue_reader, worker_reader, dequeue, *rest = (
        _service(tmp_path)
    )
    create = rest[-1]
    created = _record(binding_service, dequeue, create)
    assert created.ok

    duplicate_service = create_one_shot_dequeue_worker_binding_service(
        dequeue_reader=dequeue_reader,
        worker_reader=worker_reader,
        store=OneShotDequeueWorkerBindingStore(binding_store.database_path),
        clock=_clock(70),
        enabled=True,
    )
    duplicate = _record(duplicate_service, dequeue, create)
    assert duplicate.ok
    assert duplicate.record == created.record
    assert duplicate.status.lifecycle == "expired"
    assert dequeue_reader.calls == 1
    assert worker_reader.calls == 1

    with sqlite3.connect(binding_store.database_path) as connection:
        rows = []
        for table in (
            "one_shot_dequeue_worker_binding_reservations",
            "one_shot_dequeue_worker_bindings",
            "one_shot_dequeue_worker_binding_attempts",
        ):
            rows.extend(connection.execute(f"SELECT * FROM {table}").fetchall())
        schema_rows = connection.execute(
            "SELECT sql FROM sqlite_master WHERE name LIKE 'one_shot_dequeue_worker%'"
        ).fetchall()
    persisted = "\n".join(str(value) for row in rows + schema_rows for value in row)
    assert "one-shot-dequeue-worker-binding-key-1" not in persisted
    assert "secret" not in persisted.lower()
    assert "token" not in persisted.lower()
    assert "worker.invalid" not in persisted.lower()
    assert "sh -c" not in persisted.lower()


def test_idempotency_subject_conflicts_and_prerequisite_validation(
    tmp_path: Path,
) -> None:
    binding_service, binding_store, dequeue_reader, _worker_reader, dequeue, *rest = (
        _service(tmp_path)
    )
    create = rest[-1]
    assert _record(binding_service, dequeue, create).ok
    subject_retry = _record(
        binding_service,
        dequeue,
        create,
        idempotency_key="another-permanent-key",
    )
    assert subject_retry.error.error_code == "permanent_subject_reserved"
    changed = create.model_copy(
        update={"one_shot_controlled_dequeue_valid_until": "2026-08-27T12:00:44Z"}
    )
    assert _record(binding_service, dequeue, changed).error.error_code == (
        "idempotency_conflict"
    )

    mismatch = _service(tmp_path / "mismatch")
    bad = mismatch[8].model_copy(
        update={
            "worker_subject_fingerprint": mismatch[8].worker_subject_fingerprint.model_copy(
                update={"value": "f" * 64}
            )
        }
    )
    assert _record(mismatch[0], mismatch[4], bad).error.error_code == (
        "worker_subject_mismatch"
    )
    assert mismatch[1].list_owned(
        operator_id=mismatch[4].operator_id,
        candidate_record_id=mismatch[4].candidate_record_id,
    ) == ()
    assert dequeue_reader.calls == 2
    assert binding_store.list_owned(
        operator_id=dequeue.operator_id,
        candidate_record_id=dequeue.candidate_record_id,
    )


def test_concurrent_duplicate_reservation_yields_one_durable_record(
    tmp_path: Path,
) -> None:
    binding_service, binding_store, _dequeue_reader, _worker_reader, dequeue, *rest = (
        _service(tmp_path)
    )
    create = rest[-1]
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(
            pool.map(lambda _index: _record(binding_service, dequeue, create), range(8))
        )
    assert any(result.ok for result in results)
    assert all(
        result.ok or result.error.error_code == "append_indeterminate"
        for result in results
    )
    listed = binding_store.list_owned(
        operator_id=dequeue.operator_id,
        candidate_record_id=dequeue.candidate_record_id,
    )
    assert len(listed) == 1
    assert {
        result.record.binding_record_fingerprint.value for result in results if result.ok
    } == {listed[0].binding_record_fingerprint.value}


def test_indeterminate_reservation_is_terminal_across_restart(
    tmp_path: Path,
) -> None:
    _binding_service, binding_store, _dr, _wr, dequeue, dequeue_status, worker, worker_status, create = (
        _service(tmp_path)
    )
    validation = OneShotDequeueWorkerBindingValidationInputV1(
        operator_id=dequeue.operator_id,
        authority=OneShotDequeueWorkerBindingAuthorityContextV1(
            authenticated_operator_id=dequeue.operator_id,
            permission=PERMISSION,
            request_received_at="2026-08-27T12:00:36Z",
        ),
        candidate_record_id=dequeue.candidate_record_id,
        create=create,
        one_shot_controlled_dequeue=dequeue,
        one_shot_controlled_dequeue_status=dequeue_status,
        worker_intake_admission=worker,
        worker_intake_admission_status=worker_status,
        idempotency_key="one-shot-dequeue-worker-binding-key-1",
    )
    record = build_binding(validation)
    idempotency, reservation = build_reservations(validation, record)
    audit = build_audit(
        record,
        event="one_shot_dequeue_worker_binding_indeterminate",
        outcome="indeterminate",
        correlation_fingerprint=opaque_fingerprint("atlas:test:v1", "indeterminate"),
        occurred_at=record.recorded_at,
    )
    try:
        binding_store.append(
            record=record,
            idempotency_reservation=idempotency,
            subject_reservation=reservation,
            audit_evidence=audit,
            v045_dequeue_valid_until=create.one_shot_controlled_dequeue_valid_until,
            v040_worker_intake_valid_until=create.worker_intake_admission_valid_until,
            force_indeterminate=True,
        )
    except store.OneShotDequeueWorkerBindingStoreError as error:
        assert error.code == "append_indeterminate"
    retry = create_one_shot_dequeue_worker_binding_service(
        dequeue_reader=Reader((dequeue, dequeue_status)),
        worker_reader=Reader((worker, worker_status)),
        store=OneShotDequeueWorkerBindingStore(binding_store.database_path),
        clock=_clock(),
        enabled=True,
    )
    result = _record(retry, dequeue, create)
    assert result.error.error_code == "append_indeterminate"
    assert result.outcome == "indeterminate"


def test_quota_bounds_corruption_and_append_only_surface(tmp_path: Path) -> None:
    quota = _service(tmp_path / "quota", quota=0)
    assert _record(quota[0], quota[4], quota[8]).error.error_code == "quota_exceeded"

    bounded = _service(tmp_path / "bounded", max_model_bytes=1)
    assert _record(bounded[0], bounded[4], bounded[8]).error.error_code == (
        "record_too_large"
    )

    clean = _service(tmp_path / "surface")
    assert _record(clean[0], clean[4], clean[8]).ok
    collection = build_collection(
        operator_id=clean[4].operator_id,
        candidate_record_id=clean[4].candidate_record_id,
        items=clean[1].list_owned(
            operator_id=clean[4].operator_id,
            candidate_record_id=clean[4].candidate_record_id,
        ),
    )
    assert collection.count == 1
    assert not any(
        hasattr(OneShotDequeueWorkerBindingStore, name)
        for name in (
            "delete",
            "release",
            "consume",
            "claim",
            "lease",
            "refresh",
            "replace",
            "supersede",
            "retry",
            "resend",
            "repair",
            "enqueue",
            "dequeue",
            "dispatch",
            "execute",
            "start_worker",
        )
    )
    source = Path(store.__file__).read_text()
    assert "DELETE FROM one_shot_dequeue_worker" not in source
    assert "UPDATE one_shot_dequeue_worker" not in source

    corrupt = _service(tmp_path / "corrupt")
    created = _record(corrupt[0], corrupt[4], corrupt[8])
    assert created.ok
    with sqlite3.connect(corrupt[1].database_path) as connection:
        connection.execute("UPDATE one_shot_dequeue_worker_bindings SET record_json = ?", ("{}",))
    assert corrupt[0].get(
        authenticated_operator_id=corrupt[4].operator_id,
        permission_verified=True,
        binding_id=created.record.binding_id,
        correlation_id="corrupt",
    ).error.error_code == "store_corrupt"


def test_service_store_have_no_effect_imports_calls_or_production_consumers() -> None:
    root = Path(__file__).resolve().parents[1]
    forbidden_imports = {
        "subprocess",
        "docker",
        "podman",
        "requests",
        "httpx",
        "socket",
        "agent",
        "dispatch",
        "execution_worker",
        "provider",
        "repository",
        "workflow",
        "transport",
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
        assert not [
            name for name in imported if any(term in name for term in forbidden_imports)
        ]
        assert not any(
            isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name
            in {
                "enqueue",
                "consume",
                "claim",
                "lease",
                "delete",
                "release",
                "refresh",
                "replace",
                "supersede",
                "retry",
                "resend",
                "repair",
                "replay_bypass",
                "dequeue",
                "execute",
                "dispatch",
                "start",
                "start_worker",
            }
            for node in ast.walk(tree)
        )
    consumers = []
    for path in root.rglob("*.py"):
        if path.parent.name == "one_shot_dequeue_worker_binding":
            continue
        if path.name.startswith("test_"):
            continue
        source_text = path.read_text()
        if (
            "one_shot_dequeue_worker_binding.service" in source_text
            or "OneShotDequeueWorkerBindingService" in source_text
        ):
            consumers.append(path)
    assert consumers == []
