from __future__ import annotations

import ast
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path

from app.installation_one_shot_live_enqueue import service, store
from app.installation_one_shot_live_enqueue.contract import (
    PERMISSION,
    OneShotLiveEnqueueAuthorityContextV1,
    OneShotLiveEnqueueValidationInputV1,
    build_audit,
    build_collection,
    build_enqueue,
    opaque_fingerprint,
)
from app.installation_one_shot_live_enqueue.service import (
    create_one_shot_live_enqueue_service,
)
from app.installation_one_shot_live_enqueue.store import OneShotLiveEnqueueStore
from app.installation_one_shot_live_enqueue.test_contract import _facts


class Reader:
    def __init__(self, value) -> None:
        self.value = value
        self.calls = 0

    def read_owned(self, **_kwargs):
        self.calls += 1
        return self.value


def _clock(second: int = 34):
    instant = datetime(2026, 8, 27, 12, 0, tzinfo=UTC) + timedelta(seconds=second)
    return lambda: instant


def _service(
    tmp_path: Path,
    *,
    evidence=None,
    second: int = 34,
    quota: int = 16,
    max_model_bytes: int = 128 * 1024,
    enabled: bool = True,
):
    live, live_status, intake, intake_status, queue, queue_status, create = _facts(
        tmp_path
    )
    evidence_reader = Reader(
        evidence
        if evidence is not None
        else (live, live_status, intake, intake_status, queue, queue_status)
    )
    enqueue_store = OneShotLiveEnqueueStore(
        tmp_path / "one-shot-live-enqueue.sqlite3",
        max_records_per_operator=quota,
        max_model_bytes=max_model_bytes,
    )
    enqueue_service = create_one_shot_live_enqueue_service(
        evidence_reader=evidence_reader,
        store=enqueue_store,
        clock=_clock(second),
        enabled=enabled,
    )
    return (
        enqueue_service,
        enqueue_store,
        evidence_reader,
        live,
        live_status,
        intake,
        intake_status,
        queue,
        queue_status,
        create,
    )


def _record(enqueue_service, live, create, **changes):
    values = {
        "authenticated_operator_id": live.operator_id,
        "permission_verified": True,
        "candidate_record_id": live.candidate_record_id,
        "idempotency_key": "one-shot-live-enqueue-key-1",
        "correlation_id": "one-shot-live-enqueue-correlation-1",
    }
    values.update(changes)
    return enqueue_service.create(create, **values)


def test_create_get_list_and_restart_safe_owner_readback(tmp_path: Path) -> None:
    enqueue_service, enqueue_store, reader, live, *_tail, create = _service(tmp_path)
    created = _record(enqueue_service, live, create)
    assert created.ok
    assert created.record.outcome == "one_shot_live_enqueue_recorded"
    assert created.status.lifecycle == "active"
    assert reader.calls == 1
    assert created.record.reference_only
    assert not created.record.payload_constructed
    assert not created.record.dequeue_allowed
    assert not created.record.queue_polling_allowed
    assert not created.record.worker_contact_allowed
    assert not created.record.process_execution_allowed

    restarted = create_one_shot_live_enqueue_service(
        evidence_reader=Reader(None),
        store=OneShotLiveEnqueueStore(enqueue_store.database_path),
        clock=_clock(70),
    )
    readback = restarted.get(
        authenticated_operator_id=live.operator_id,
        permission_verified=True,
        enqueue_id=created.record.enqueue_id,
        correlation_id="readback",
    )
    assert readback.record == created.record
    assert readback.status.lifecycle == "expired"
    listed = restarted.list(
        authenticated_operator_id=live.operator_id,
        permission_verified=True,
        candidate_record_id=live.candidate_record_id,
        correlation_id="list",
    )
    assert tuple(item.enqueue_id for item in listed.items) == (
        created.record.enqueue_id,
    )
    assert restarted.get(
        authenticated_operator_id="operator-b",
        permission_verified=True,
        enqueue_id=created.record.enqueue_id,
        correlation_id="foreign",
    ).error.error_code == "not_found"
    foreign = restarted.list(
        authenticated_operator_id="operator-b",
        permission_verified=True,
        candidate_record_id=live.candidate_record_id,
        correlation_id="foreign-list",
    )
    assert foreign.count == 0


def test_disabled_auth_permission_and_missing_fail_before_reservation(
    tmp_path: Path,
) -> None:
    enqueue_service, enqueue_store, reader, live, *_tail, create = _service(
        tmp_path, enabled=False
    )
    assert _record(enqueue_service, live, create).error.error_code == (
        "installation_capability_unsupported"
    )
    assert _record(
        enqueue_service, live, create, authenticated_operator_id=None
    ).error.error_code == "unauthenticated"
    assert _record(
        enqueue_service, live, create, permission_verified=False
    ).error.error_code == "forbidden"
    assert reader.calls == 0
    assert enqueue_store.list_owned(
        operator_id=live.operator_id,
        candidate_record_id=live.candidate_record_id,
    ) == ()

    missing, missing_store, missing_reader, live2, *_tail2, create2 = _service(
        tmp_path / "missing", evidence=None
    )
    missing_reader.value = None
    result = _record(missing, live2, create2, correlation_id="secret/internal/path")
    assert result.error.error_code == "not_found"
    assert missing_store.list_owned(
        operator_id=live2.operator_id,
        candidate_record_id=live2.candidate_record_id,
    ) == ()
    assert "secret/internal/path" not in result.model_dump_json()


def test_exact_duplicate_zero_reader_raw_key_not_persisted_and_expiry_readable(
    tmp_path: Path,
) -> None:
    enqueue_service, enqueue_store, reader, live, *_tail, create = _service(tmp_path)
    created = _record(enqueue_service, live, create)
    assert created.ok

    duplicate_service = create_one_shot_live_enqueue_service(
        evidence_reader=reader,
        store=OneShotLiveEnqueueStore(enqueue_store.database_path),
        clock=_clock(70),
        enabled=True,
    )
    duplicate = _record(duplicate_service, live, create)
    assert duplicate.ok
    assert duplicate.record == created.record
    assert duplicate.status.lifecycle == "expired"
    assert reader.calls == 1
    with sqlite3.connect(enqueue_store.database_path) as connection:
        rows = []
        for table in (
            "one_shot_live_enqueue_reservations",
            "one_shot_live_enqueue_records",
            "one_shot_live_enqueue_attempts",
        ):
            rows.extend(connection.execute(f"SELECT * FROM {table}").fetchall())
        schema_rows = connection.execute(
            "SELECT sql FROM sqlite_master WHERE name LIKE 'one_shot_live_enqueue%'"
        ).fetchall()
    persisted = "\n".join(str(value) for row in rows + schema_rows for value in row)
    assert "one-shot-live-enqueue-key-1" not in persisted
    assert "secret" not in persisted


def test_idempotency_subject_conflicts_and_p1_validation_integration(
    tmp_path: Path,
) -> None:
    enqueue_service, enqueue_store, reader, live, *_tail, create = _service(tmp_path)
    assert _record(enqueue_service, live, create).ok
    subject_retry = _record(
        enqueue_service,
        live,
        create,
        idempotency_key="another-permanent-key",
    )
    assert subject_retry.error.error_code == "conflict"
    changed = create.model_copy(
        update={"live_enqueue_admission_valid_until": "2026-08-27T12:00:44Z"}
    )
    conflict = _record(enqueue_service, live, changed)
    assert conflict.error.error_code == "conflict"

    mismatch, mismatch_store, mismatch_reader, live2, *_tail2, create2 = _service(
        tmp_path / "mismatch"
    )
    bad = create2.model_copy(
        update={
            "queue_item_reference_fingerprint": (
                create2.queue_item_reference_fingerprint.model_copy(
                    update={"value": "f" * 64}
                )
            )
        }
    )
    assert _record(mismatch, live2, bad).error.error_code == "linkage_mismatch"
    assert mismatch_reader.calls == 1
    assert mismatch_store.list_owned(
        operator_id=live2.operator_id,
        candidate_record_id=live2.candidate_record_id,
    ) == ()
    assert reader.calls == 2
    assert enqueue_store.list_owned(
        operator_id=live.operator_id,
        candidate_record_id=live.candidate_record_id,
    )


def test_concurrent_duplicate_reservation_yields_one_durable_record(
    tmp_path: Path,
) -> None:
    fixtures = _service(tmp_path)
    enqueue_service = fixtures[0]
    enqueue_store = fixtures[1]
    live = fixtures[3]
    create = fixtures[9]
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(
            pool.map(lambda _index: _record(enqueue_service, live, create), range(8))
        )
    assert any(result.ok for result in results)
    assert all(
        result.ok or result.error.error_code == "append_indeterminate"
        for result in results
    )
    listed = enqueue_store.list_owned(
        operator_id=live.operator_id,
        candidate_record_id=live.candidate_record_id,
    )
    assert len(listed) == 1
    assert {result.record.record_fingerprint.value for result in results if result.ok} == {
        listed[0].record_fingerprint.value
    }


def test_permanent_no_replay_after_attempt_start_and_indeterminate_readback(
    tmp_path: Path,
) -> None:
    (
        _enqueue_service,
        enqueue_store,
        _reader,
        live,
        live_status,
        intake,
        intake_status,
        queue,
        queue_status,
        create,
    ) = _service(tmp_path)
    validation = OneShotLiveEnqueueValidationInputV1(
        operator_id=live.operator_id,
        authority=OneShotLiveEnqueueAuthorityContextV1(
            authenticated_operator_id=live.operator_id,
            permission=PERMISSION,
            request_received_at="2026-08-27T12:00:34Z",
        ),
        candidate_record_id=live.candidate_record_id,
        create=create,
        live_enqueue_admission=live,
        live_enqueue_admission_status=live_status,
        worker_intake_admission=intake,
        worker_intake_admission_status=intake_status,
        worker_queue_reservation=queue,
        worker_queue_reservation_status=queue_status,
        idempotency_key="one-shot-live-enqueue-key-1",
    )
    record, idempotency, reservation = build_enqueue(validation)
    audit = build_audit(
        record,
        event="one_shot_live_enqueue_indeterminate",
        outcome="indeterminate",
        correlation_fingerprint=opaque_fingerprint("atlas:test:v1", "indeterminate"),
        occurred_at=record.recorded_at,
    )
    try:
        enqueue_store.append(
            record=record,
            idempotency_reservation=idempotency,
            subject_reservation=reservation,
            audit_evidence=audit,
            live_enqueue_admission_valid_until=create.live_enqueue_admission_valid_until,
            force_indeterminate=True,
        )
    except store.OneShotLiveEnqueueStoreError as error:
        assert error.code == "append_indeterminate"
    retry_service = create_one_shot_live_enqueue_service(
        evidence_reader=Reader((live, live_status, intake, intake_status, queue, queue_status)),
        store=OneShotLiveEnqueueStore(enqueue_store.database_path),
        clock=_clock(),
        enabled=True,
    )
    retry = _record(retry_service, live, create)
    assert retry.error.error_code == "append_indeterminate"
    assert not retry.ok
    assert retry.outcome == "indeterminate"
    with sqlite3.connect(enqueue_store.database_path) as connection:
        reservations = connection.execute(
            "SELECT COUNT(*) FROM one_shot_live_enqueue_reservations"
        ).fetchone()[0]
        records = connection.execute(
            "SELECT COUNT(*) FROM one_shot_live_enqueue_records"
        ).fetchone()[0]
        attempts = connection.execute(
            "SELECT COUNT(*) FROM one_shot_live_enqueue_attempts"
        ).fetchone()[0]
    assert reservations == 1
    assert records == 0
    assert attempts == 1


def test_quota_record_bounds_and_corruption_fail_closed(tmp_path: Path) -> None:
    quota_fixtures = _service(tmp_path / "quota", quota=0)
    quota_service = quota_fixtures[0]
    live = quota_fixtures[3]
    create = quota_fixtures[9]
    assert _record(quota_service, live, create).error.error_code == "quota_exceeded"

    bounded_fixtures = _service(tmp_path / "bounded", max_model_bytes=1)
    bounded = bounded_fixtures[0]
    live2 = bounded_fixtures[3]
    create2 = bounded_fixtures[9]
    assert _record(bounded, live2, create2).error.error_code == "record_too_large"

    clean, enqueue_store, _reader, live3, *_tail3, create3 = _service(
        tmp_path / "corrupt"
    )
    created = _record(clean, live3, create3)
    assert created.ok
    with sqlite3.connect(enqueue_store.database_path) as connection:
        connection.execute(
            "UPDATE one_shot_live_enqueue_records SET record_json = ?",
            ("{}",),
        )
    assert clean.get(
        authenticated_operator_id=live3.operator_id,
        permission_verified=True,
        enqueue_id=created.record.enqueue_id,
        correlation_id="corrupt",
    ).error.error_code == "store_corrupt"


def test_store_is_append_only_bounded_and_has_no_effect_api(tmp_path: Path) -> None:
    enqueue_service, enqueue_store, _reader, live, *_tail, create = _service(tmp_path)
    created = _record(enqueue_service, live, create)
    assert created.ok
    collection = build_collection(
        operator_id=live.operator_id,
        candidate_record_id=live.candidate_record_id,
        items=enqueue_store.list_owned(
            operator_id=live.operator_id,
            candidate_record_id=live.candidate_record_id,
        ),
    )
    assert collection.count == 1
    assert not any(
        hasattr(OneShotLiveEnqueueStore, name)
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
    assert "DELETE FROM one_shot_live_enqueue" not in source
    assert "UPDATE one_shot_live_enqueue" not in source


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
        if path.parent.name == "installation_one_shot_live_enqueue":
            continue
        if path.name.startswith("test_"):
            continue
        source_text = path.read_text()
        if (
            "installation_one_shot_live_enqueue.service" in source_text
            or "OneShotLiveEnqueueService" in source_text
        ):
            consumers.append(path)
    assert consumers == []
