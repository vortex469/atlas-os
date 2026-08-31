from __future__ import annotations

import ast
import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path

from app.worker_queue_reservation import service, store
from app.worker_queue_reservation.service import (
    create_worker_queue_reservation_service,
)
from app.worker_queue_reservation.store import WorkerQueueReservationStore
from app.worker_queue_reservation.test_contract import (
    RESERVATION_ID,
    _facts,
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


def _clock(second: int = 34):
    instant = datetime(2026, 8, 27, 12, 0, tzinfo=UTC) + timedelta(seconds=second)
    return lambda: instant


def _service(
    tmp_path: Path,
    *,
    evidence=None,
    queue_reference=None,
    second: int = 34,
    quota: int = 16,
    max_model_bytes: int = 128 * 1024,
    enabled: bool = True,
):
    stub, status, intake, create = _facts(tmp_path)
    evidence_reader = Reader(
        evidence if evidence is not None else (stub, status, False)
    )
    queue_reader = Reader(intake if queue_reference is None else queue_reference)
    id_factory = Factory(RESERVATION_ID)
    reservation_store = WorkerQueueReservationStore(
        tmp_path / "worker-queue-reservations.sqlite3",
        max_records_per_operator=quota,
        max_model_bytes=max_model_bytes,
    )
    reservation_service = create_worker_queue_reservation_service(
        evidence_reader=evidence_reader,
        queue_reference_reader=queue_reader,
        store=reservation_store,
        clock=_clock(second),
        reservation_id_factory=id_factory,
        enabled=enabled,
    )
    return (
        reservation_service,
        reservation_store,
        evidence_reader,
        queue_reader,
        id_factory,
        stub,
        status,
        intake,
        create,
    )


def _record(reservation_service, stub, create, **changes):
    values = {
        "authenticated_operator_id": stub.operator_id,
        "permission_verified": True,
        "candidate_record_id": stub.candidate_record_id,
        "idempotency_key": "worker-queue-reservation-key-1",
        "correlation_id": "worker-queue-reservation-correlation-1",
    }
    values.update(changes)
    return reservation_service.create(create, **values)


def test_create_get_list_and_restart_safe_owner_readback(tmp_path: Path) -> None:
    queue_service, queue_store, evidence_reader, queue_reader, _, stub, _, _, create = (
        _service(tmp_path)
    )
    created = _record(queue_service, stub, create)
    assert created.disposition == "recorded"
    assert created.status.lifecycle == "active"
    assert created.status.eligibility == "worker_queue_reservation_recorded"
    assert created.reservation.eligibility == "worker_queue_reservation_recorded"
    assert evidence_reader.calls == queue_reader.calls == 1
    assert not created.reservation.live_enqueue_allowed
    assert not created.reservation.dequeue_allowed
    assert not created.reservation.worker_start_allowed
    assert not created.reservation.execution_start_allowed

    restarted = create_worker_queue_reservation_service(
        evidence_reader=Reader(None),
        queue_reference_reader=Reader(None),
        store=WorkerQueueReservationStore(queue_store.database_path),
        clock=_clock(50),
        reservation_id_factory=Factory(
            "6f80fe47-d0dc-4449-b65d-bdb0e0a365e3"
        ),
    )
    readback = restarted.get(
        authenticated_operator_id=stub.operator_id,
        permission_verified=True,
        reservation_id=RESERVATION_ID,
        correlation_id="readback",
    )
    assert readback.reservation == created.reservation
    assert readback.status.lifecycle == "expired"
    listed = restarted.list(
        authenticated_operator_id=stub.operator_id,
        permission_verified=True,
        correlation_id="list",
    )
    assert tuple(item.reservation.reservation_id for item in listed) == (
        RESERVATION_ID,
    )
    assert restarted.get(
        authenticated_operator_id="operator-b",
        permission_verified=True,
        reservation_id=RESERVATION_ID,
        correlation_id="foreign",
    ).error.error_code == "not_found"
    assert restarted.list(
        authenticated_operator_id="operator-b",
        permission_verified=True,
        correlation_id="foreign-list",
    ) == ()


def test_default_disabled_auth_and_permission_fail_before_readers(tmp_path: Path) -> None:
    queue_service, _, evidence_reader, queue_reader, _, stub, _, _, create = _service(
        tmp_path, enabled=False
    )
    assert _record(queue_service, stub, create).error.error_code == "not_eligible"
    assert _record(
        queue_service, stub, create, authenticated_operator_id=None
    ).error.error_code == "unauthenticated"
    assert _record(
        queue_service, stub, create, permission_verified=False
    ).error.error_code == "forbidden"
    assert evidence_reader.calls == queue_reader.calls == 0


def test_exact_duplicate_is_zero_reader_and_raw_key_is_not_persisted(
    tmp_path: Path,
) -> None:
    queue_service, queue_store, evidence_reader, queue_reader, id_factory, stub, _, _, create = (
        _service(tmp_path)
    )
    created = _record(queue_service, stub, create)
    duplicate = _record(queue_service, stub, create)
    assert duplicate.disposition == "exact_duplicate"
    assert duplicate.reservation == created.reservation
    assert evidence_reader.calls == queue_reader.calls == 1
    assert id_factory.calls == 1
    with sqlite3.connect(queue_store.database_path) as connection:
        schema = connection.execute(
            """SELECT sql FROM sqlite_master
            WHERE name = 'worker_queue_reservations'"""
        ).fetchone()[0]
        row = connection.execute(
            "SELECT * FROM worker_queue_reservations"
        ).fetchone()
    assert "worker-queue-reservation-key-1" not in schema
    assert all("worker-queue-reservation-key-1" not in str(value) for value in row)


def test_idempotency_conflict_and_permanent_subject_no_replay(tmp_path: Path) -> None:
    queue_service, _, _, _, _, stub, _, _, create = _service(tmp_path)
    assert _record(queue_service, stub, create).disposition == "recorded"
    subject_retry = _record(
        queue_service,
        stub,
        create,
        idempotency_key="another-permanent-key",
    )
    assert subject_retry.error.error_code == "conflict"
    changed = create.model_copy(
        update={
            "worker_admission_stub_valid_until": "2026-08-27T12:00:44Z"
        }
    )
    conflict = queue_service.create(
        changed,
        authenticated_operator_id=stub.operator_id,
        permission_verified=True,
        candidate_record_id=stub.candidate_record_id,
        idempotency_key="worker-queue-reservation-key-1",
        correlation_id="conflict",
    )
    assert conflict.error.error_code == "conflict"


def test_owner_missing_and_redaction_fail_closed(tmp_path: Path) -> None:
    queue_service, _, evidence_reader, _, _, stub, _, _, create = _service(
        tmp_path
    )
    assert _record(
        queue_service, stub, create, authenticated_operator_id="operator-b"
    ).error.error_code == "not_found"
    assert evidence_reader.calls == 1
    missing, *_tail = _service(tmp_path / "missing")
    missing._evidence_reader = Reader(None)  # explicitly injected test dependency
    result = _record(
        missing, stub, create, correlation_id="secret/internal/path"
    )
    assert result.error.error_code == "not_found"
    assert "secret/internal/path" not in result.model_dump_json()


def test_stale_home_assistant_linkage_and_limits_are_blocked(tmp_path: Path) -> None:
    stale, _, _, _, _, stub, _, _, create = _service(
        tmp_path / "stale", second=50
    )
    assert _record(stale, stub, create).error.error_code == "expired"

    stub2, status2, intake2, create2 = _facts(tmp_path / "home-facts")
    home, *_ = _service(
        tmp_path / "home",
        evidence=(stub2, status2, True),
        queue_reference=intake2,
    )
    assert _record(home, stub2, create2).error.error_code == "not_eligible"

    mismatch, _, _, _, _, stub3, _, _, create3 = _service(
        tmp_path / "mismatch"
    )
    bad = create3.model_copy(
        update={
            "queue_intake_reference_fingerprint": (
                create3.queue_intake_reference_fingerprint.model_copy(
                    update={"value": "f" * 64}
                )
            )
        }
    )
    assert _record(
        mismatch,
        stub3,
        bad,
        idempotency_key="queue-linkage-mismatch-key",
    ).error.error_code == "not_eligible"
    limits = create3.model_copy(
        update={
            "inherited_limits_fingerprint": (
                create3.inherited_limits_fingerprint.model_copy(
                    update={"value": "e" * 64}
                )
            )
        }
    )
    assert _record(
        mismatch,
        stub3,
        limits,
        idempotency_key="queue-limits-mismatch-key",
    ).error.error_code == "not_eligible"


def test_quota_record_bounds_and_corruption_fail_closed(tmp_path: Path) -> None:
    quota_service, _, _, _, _, stub, _, _, create = _service(
        tmp_path / "quota", quota=0
    )
    assert _record(quota_service, stub, create).error.error_code == "quota_exceeded"

    bounded, _, _, _, _, stub2, _, _, create2 = _service(
        tmp_path / "bounded", max_model_bytes=1
    )
    assert _record(
        bounded, stub2, create2
    ).error.error_code == "record_too_large"

    clean, queue_store, _, _, _, stub3, _, _, create3 = _service(
        tmp_path / "corrupt"
    )
    assert _record(clean, stub3, create3).disposition == "recorded"
    with sqlite3.connect(queue_store.database_path) as connection:
        connection.execute(
            "UPDATE worker_queue_reservations SET record_json = ?", ("{}",)
        )
    assert clean.get(
        authenticated_operator_id=stub3.operator_id,
        permission_verified=True,
        reservation_id=RESERVATION_ID,
        correlation_id="corrupt",
    ).error.error_code == "internal_error"


def test_store_is_append_only_and_has_no_effect_api() -> None:
    assert not any(
        hasattr(WorkerQueueReservationStore, name)
        for name in (
            "update", "delete", "release", "consume", "enqueue", "dequeue",
            "dispatch", "execute", "start_worker",
        )
    )
    source = Path(store.__file__).read_text()
    assert "UPDATE worker_queue_reservations" not in source
    assert "DELETE FROM worker_queue_reservations" not in source


def test_service_store_have_no_effect_imports_calls_or_production_consumers() -> None:
    root = Path(__file__).resolve().parents[1]
    forbidden_imports = {
        "subprocess", "docker", "podman", "requests", "httpx", "socket",
        "agent", "dispatch", "execution_worker", "provider", "repository",
        "workflow",
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
            name
            for name in imported
            if any(term in name for term in forbidden_imports)
        ]
        assert not any(
            isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name
            in {
                "enqueue", "dequeue", "execute", "dispatch", "retry",
                "resend", "start", "start_worker",
            }
            for node in ast.walk(tree)
        )
    consumers = []
    for path in root.rglob("*.py"):
        if path.parent.name == "worker_queue_reservation" or path.name.startswith(
            "test_"
        ):
            continue
        source = path.read_text()
        if (
            "worker_queue_reservation.service" in source
            or "WorkerQueueReservationService" in source
        ):
            consumers.append(path)
    assert consumers == []
