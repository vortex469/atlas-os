from __future__ import annotations

import ast
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path

from app.worker_binding_activation_preflight import service, store
from app.worker_binding_activation_preflight.contract import (
    PERMISSION,
    WorkerBindingActivationPreflightAuthorityContextV1,
    WorkerBindingActivationPreflightValidationInputV1,
    build_audit,
    build_collection,
    build_preflight,
    build_reservations,
    opaque_fingerprint,
)
from app.worker_binding_activation_preflight.service import (
    create_worker_binding_activation_preflight_service,
)
from app.worker_binding_activation_preflight.store import (
    WorkerBindingActivationPreflightStore,
)
from app.worker_binding_activation_preflight.test_contract import _facts


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
    binding_evidence=None,
    second: int = 36,
    quota: int = 16,
    max_model_bytes: int = 192 * 1024,
    enabled: bool = True,
):
    binding, binding_status, create = _facts(tmp_path)
    binding_reader = Reader(
        binding_evidence if binding_evidence is not None else (binding, binding_status)
    )
    preflight_store = WorkerBindingActivationPreflightStore(
        tmp_path / "worker-binding-activation-preflight.sqlite3",
        max_records_per_operator=quota,
        max_model_bytes=max_model_bytes,
    )
    preflight_service = create_worker_binding_activation_preflight_service(
        binding_reader=binding_reader,
        store=preflight_store,
        clock=_clock(second),
        enabled=enabled,
    )
    return (
        preflight_service,
        preflight_store,
        binding_reader,
        binding,
        binding_status,
        create,
    )


def _record(preflight_service, binding, create, **changes):
    values = {
        "authenticated_operator_id": binding.operator_id,
        "permission_verified": True,
        "candidate_record_id": binding.candidate_record_id,
        "idempotency_key": "worker-binding-activation-preflight-key-1",
        "correlation_id": "worker-binding-activation-preflight-correlation-1",
    }
    values.update(changes)
    return preflight_service.create(create, **values)


def test_create_get_list_and_restart_safe_owner_readback(tmp_path: Path) -> None:
    (
        preflight_service,
        preflight_store,
        binding_reader,
        binding,
        _binding_status,
        create,
    ) = _service(tmp_path)
    created = _record(preflight_service, binding, create)
    assert created.ok
    assert created.record.preflight_state == "readiness_gated"
    assert created.status.lifecycle == "active"
    assert binding_reader.calls == 1
    assert not created.record.binding_activation_allowed
    assert not created.record.worker_store_contact_allowed
    assert not created.record.worker_runtime_contact_allowed
    assert not created.record.worker_start_allowed
    assert not created.record.agent_invocation_allowed
    assert not created.record.execution_start_allowed

    restarted = create_worker_binding_activation_preflight_service(
        binding_reader=Reader(None),
        store=WorkerBindingActivationPreflightStore(preflight_store.database_path),
        clock=_clock(70),
    )
    readback = restarted.get(
        authenticated_operator_id=binding.operator_id,
        permission_verified=True,
        preflight_id=created.record.preflight_id,
        correlation_id="readback",
    )
    assert readback.record == created.record
    assert readback.status.lifecycle == "expired"
    listed = restarted.list(
        authenticated_operator_id=binding.operator_id,
        permission_verified=True,
        candidate_record_id=binding.candidate_record_id,
        correlation_id="list",
    )
    assert tuple(item.preflight_id for item in listed.items) == (
        created.record.preflight_id,
    )
    assert restarted.get(
        authenticated_operator_id="operator-b",
        permission_verified=True,
        preflight_id=created.record.preflight_id,
        correlation_id="foreign",
    ).error.error_code == "not_found"


def test_default_disabled_auth_permission_missing_and_zero_effect(
    tmp_path: Path,
) -> None:
    preflight_service, preflight_store, binding_reader, binding, _status, create = (
        _service(tmp_path, enabled=False)
    )
    assert _record(preflight_service, binding, create).error.error_code == (
        "installation_capability_unsupported"
    )
    assert _record(
        preflight_service, binding, create, authenticated_operator_id=None
    ).error.error_code == "unauthenticated"
    assert _record(
        preflight_service, binding, create, permission_verified=False
    ).error.error_code == "forbidden"
    assert binding_reader.calls == 0
    assert preflight_store.list_owned(
        operator_id=binding.operator_id,
        candidate_record_id=binding.candidate_record_id,
    ) == ()

    missing = _service(tmp_path / "missing", binding_evidence=None)
    missing[2].value = None
    result = _record(
        missing[0],
        missing[3],
        missing[5],
        correlation_id="secret/internal/path/token",
    )
    assert result.error.error_code == "not_found"
    assert "secret/internal/path/token" not in result.model_dump_json()


def test_exact_duplicate_zero_reader_and_secret_free_persistence(
    tmp_path: Path,
) -> None:
    preflight_service, preflight_store, binding_reader, binding, _status, create = (
        _service(tmp_path)
    )
    created = _record(preflight_service, binding, create)
    assert created.ok

    duplicate_service = create_worker_binding_activation_preflight_service(
        binding_reader=binding_reader,
        store=WorkerBindingActivationPreflightStore(preflight_store.database_path),
        clock=_clock(70),
        enabled=True,
    )
    duplicate = _record(duplicate_service, binding, create)
    assert duplicate.ok
    assert duplicate.record == created.record
    assert duplicate.status.lifecycle == "expired"
    assert binding_reader.calls == 1

    with sqlite3.connect(preflight_store.database_path) as connection:
        rows = []
        for table in (
            "worker_binding_activation_preflight_reservations",
            "worker_binding_activation_preflights",
            "worker_binding_activation_preflight_attempts",
        ):
            rows.extend(connection.execute(f"SELECT * FROM {table}").fetchall())
        schema_rows = connection.execute(
            "SELECT sql FROM sqlite_master WHERE name LIKE 'worker_binding_activation_preflight%'"
        ).fetchall()
    persisted = "\n".join(str(value) for row in rows + schema_rows for value in row)
    assert "worker-binding-activation-preflight-key-1" not in persisted
    assert "secret" not in persisted.lower()
    assert "token" not in persisted.lower()
    assert "worker.invalid" not in persisted.lower()
    assert "sh -c" not in persisted.lower()


def test_idempotency_subject_conflicts_and_prerequisite_validation(
    tmp_path: Path,
) -> None:
    preflight_service, preflight_store, binding_reader, binding, _status, create = (
        _service(tmp_path)
    )
    assert _record(preflight_service, binding, create).ok
    subject_retry = _record(
        preflight_service,
        binding,
        create,
        idempotency_key="another-permanent-key",
    )
    assert subject_retry.error.error_code == "permanent_subject_reserved"
    changed = create.model_copy(
        update={"binding_valid_until": "2026-08-27T12:00:44Z"}
    )
    assert _record(preflight_service, binding, changed).error.error_code == (
        "idempotency_conflict"
    )

    mismatch = _service(tmp_path / "mismatch")
    bad = mismatch[5].model_copy(
        update={
            "worker_subject_fingerprint": mismatch[5].worker_subject_fingerprint.model_copy(
                update={"value": "f" * 64}
            )
        }
    )
    assert _record(mismatch[0], mismatch[3], bad).error.error_code == (
        "fingerprint_mismatch"
    )
    assert mismatch[1].list_owned(
        operator_id=mismatch[3].operator_id,
        candidate_record_id=mismatch[3].candidate_record_id,
    ) == ()
    assert binding_reader.calls == 2
    assert preflight_store.list_owned(
        operator_id=binding.operator_id,
        candidate_record_id=binding.candidate_record_id,
    )


def test_concurrent_duplicate_reservation_yields_one_durable_record(
    tmp_path: Path,
) -> None:
    preflight_service, preflight_store, _reader, binding, _status, create = _service(
        tmp_path
    )
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(
            pool.map(lambda _index: _record(preflight_service, binding, create), range(8))
        )
    assert any(result.ok for result in results)
    assert all(
        result.ok or result.error.error_code == "append_indeterminate"
        for result in results
    )
    listed = preflight_store.list_owned(
        operator_id=binding.operator_id,
        candidate_record_id=binding.candidate_record_id,
    )
    assert len(listed) == 1
    assert {
        result.record.preflight_record_fingerprint.value
        for result in results
        if result.ok
    } == {listed[0].preflight_record_fingerprint.value}


def test_indeterminate_reservation_is_terminal_across_restart(
    tmp_path: Path,
) -> None:
    _preflight_service, preflight_store, _reader, binding, binding_status, create = (
        _service(tmp_path)
    )
    validation = WorkerBindingActivationPreflightValidationInputV1(
        operator_id=binding.operator_id,
        authority=WorkerBindingActivationPreflightAuthorityContextV1(
            authenticated_operator_id=binding.operator_id,
            permission=PERMISSION,
            request_received_at="2026-08-27T12:00:36Z",
        ),
        candidate_record_id=binding.candidate_record_id,
        create=create,
        one_shot_dequeue_worker_binding=binding,
        one_shot_dequeue_worker_binding_status=binding_status,
        idempotency_key="worker-binding-activation-preflight-key-1",
    )
    record = build_preflight(validation)
    idempotency, reservation = build_reservations(validation, record)
    audit = build_audit(
        record,
        event="worker_binding_activation_preflight_indeterminate",
        outcome="indeterminate",
        correlation_fingerprint=opaque_fingerprint("atlas:test:v1", "indeterminate"),
        occurred_at=record.recorded_at,
    )
    try:
        preflight_store.append(
            record=record,
            idempotency_reservation=idempotency,
            subject_reservation=reservation,
            audit_evidence=audit,
            binding_valid_until=create.binding_valid_until,
            force_indeterminate=True,
        )
    except store.WorkerBindingActivationPreflightStoreError as error:
        assert error.code == "append_indeterminate"
    retry = create_worker_binding_activation_preflight_service(
        binding_reader=Reader((binding, binding_status)),
        store=WorkerBindingActivationPreflightStore(preflight_store.database_path),
        clock=_clock(),
        enabled=True,
    )
    result = _record(retry, binding, create)
    assert result.error.error_code == "append_indeterminate"
    assert result.outcome == "indeterminate"


def test_quota_bounds_corruption_and_append_only_surface(tmp_path: Path) -> None:
    quota = _service(tmp_path / "quota", quota=0)
    assert _record(quota[0], quota[3], quota[5]).error.error_code == "quota_exceeded"

    bounded = _service(tmp_path / "bounded", max_model_bytes=1)
    assert _record(bounded[0], bounded[3], bounded[5]).error.error_code == (
        "record_too_large"
    )

    clean = _service(tmp_path / "surface")
    assert _record(clean[0], clean[3], clean[5]).ok
    collection = build_collection(
        operator_id=clean[3].operator_id,
        candidate_record_id=clean[3].candidate_record_id,
        items=clean[1].list_owned(
            operator_id=clean[3].operator_id,
            candidate_record_id=clean[3].candidate_record_id,
        ),
    )
    assert collection.count == 1
    assert not any(
        hasattr(WorkerBindingActivationPreflightStore, name)
        for name in (
            "delete",
            "release",
            "activate",
            "contact",
            "consume",
            "claim",
            "lease",
            "ack",
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
    source = Path(store.__file__).read_text(encoding="utf-8")
    assert "DELETE FROM worker_binding_activation" not in source
    assert "UPDATE worker_binding_activation" not in source

    corrupt = _service(tmp_path / "corrupt")
    created = _record(corrupt[0], corrupt[3], corrupt[5])
    assert created.ok
    with sqlite3.connect(corrupt[1].database_path) as connection:
        connection.execute(
            "UPDATE worker_binding_activation_preflights SET record_json = ?", ("{}",)
        )
    assert corrupt[0].get(
        authenticated_operator_id=corrupt[3].operator_id,
        permission_verified=True,
        preflight_id=created.record.preflight_id,
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
        tree = ast.parse(Path(module.__file__).read_text(encoding="utf-8"))
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
                "activate",
                "contact",
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
        if path.parent.name == "worker_binding_activation_preflight":
            continue
        if path.name.startswith("test_"):
            continue
        source_text = path.read_text(encoding="utf-8")
        if (
            "worker_binding_activation_preflight.service" in source_text
            or "WorkerBindingActivationPreflightService" in source_text
        ):
            consumers.append(path)
    assert consumers == []
