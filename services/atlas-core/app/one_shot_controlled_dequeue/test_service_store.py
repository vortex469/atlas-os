from __future__ import annotations

import ast
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path

from app.one_shot_controlled_dequeue import service, store
from app.one_shot_controlled_dequeue.contract import (
    OneShotControlledDequeueAdapterResultV1,
    build_reservations,
    idempotency_key_fingerprint,
    opaque_fingerprint,
    request_fingerprint,
)
from app.one_shot_controlled_dequeue.service import (
    create_one_shot_controlled_dequeue_reservation_service,
)
from app.one_shot_controlled_dequeue.store import (
    OneShotControlledDequeueStore,
    OneShotControlledDequeueStoreError,
)
from app.one_shot_controlled_dequeue.test_contract import _facts, _input


class Reader:
    def __init__(self, value) -> None:
        self.value = value
        self.calls = 0

    def read_owned(self, **_kwargs):
        self.calls += 1
        return self.value


class Adapter:
    def __init__(self, *, outcome: str = "success", fail: BaseException | None = None) -> None:
        self.outcome = outcome
        self.fail = fail
        self.calls = []

    def attempt_exact_item(self, request):
        self.calls.append(request)
        if self.fail is not None:
            raise self.fail
        return OneShotControlledDequeueAdapterResultV1(
            outcome=self.outcome,
            adapter_receipt_fingerprint=opaque_fingerprint(
                "atlas:one-shot-controlled-dequeue-adapter-receipt:v1",
                f"adapter:{self.outcome}",
            ),
            queue_identity_fingerprint=request.queue_identity_fingerprint,
            item_identity_fingerprint=request.item_identity_fingerprint,
        )


def _clock(second: int = 36):
    instant = datetime(2026, 8, 27, 12, 0, tzinfo=UTC) + timedelta(seconds=second)
    return lambda: instant


def _service(
    tmp_path: Path,
    *,
    evidence=None,
    second: int = 36,
    quota: int = 16,
    max_model_bytes: int = 224 * 1024,
    enabled: bool = True,
    queue_adapter=None,
):
    admission, admission_status, create = _facts(tmp_path)
    reader = Reader(evidence if evidence is not None else (admission, admission_status))
    reservation_store = OneShotControlledDequeueStore(
        tmp_path / "one-shot-controlled-dequeue.sqlite3",
        max_records_per_operator=quota,
        max_model_bytes=max_model_bytes,
    )
    reservation_service = create_one_shot_controlled_dequeue_reservation_service(
        evidence_reader=reader,
        store=reservation_store,
        clock=_clock(second),
        queue_adapter=queue_adapter,
        enabled=enabled,
    )
    return reservation_service, reservation_store, reader, admission, admission_status, create


def _record(reservation_service, admission, create, **changes):
    values = {
        "authenticated_operator_id": admission.operator_id,
        "permission_verified": True,
        "candidate_record_id": admission.candidate_record_id,
        "idempotency_key": "one-shot-controlled-dequeue-key-1",
        "correlation_id": "one-shot-controlled-dequeue-correlation-1",
    }
    values.update(changes)
    return reservation_service.create(create, **values)


def _reserved_dequeue_id(admission, create, tmp_path: Path) -> str:
    validation = _input(tmp_path)
    assert validation.controlled_dequeue_admission == admission
    assert validation.create == create
    _, reservation = build_reservations(validation)
    return reservation.dequeue_id


def test_create_reserves_before_effect_and_restart_keeps_no_replay(
    tmp_path: Path,
) -> None:
    dequeue_service, dequeue_store, reader, admission, _, create = _service(tmp_path)
    created = _record(dequeue_service, admission, create)
    assert created.outcome == "indeterminate"
    assert created.error.error_code == "dequeue_adapter_unavailable"
    assert created.record is None
    assert reader.calls == 1

    dequeue_id = _reserved_dequeue_id(admission, create, tmp_path)
    reservation = dequeue_store.get_reservation(
        operator_id=admission.operator_id,
        dequeue_id=dequeue_id,
    )
    attempts = dequeue_store.list_attempts(
        operator_id=admission.operator_id,
        dequeue_id=dequeue_id,
    )
    assert reservation.permanent
    assert reservation.dequeue_id == dequeue_id
    assert tuple(attempt.outcome for attempt in attempts) == ("indeterminate",)
    try:
        dequeue_store.get_reservation(operator_id="operator-b", dequeue_id=dequeue_id)
    except OneShotControlledDequeueStoreError as error:
        assert error.code == "not_found"
    else:
        raise AssertionError("foreign reservation readback must fail closed")
    restarted = create_one_shot_controlled_dequeue_reservation_service(
        evidence_reader=Reader(None),
        store=OneShotControlledDequeueStore(dequeue_store.database_path),
        clock=_clock(50),
        enabled=True,
    )
    duplicate = _record(restarted, admission, create)
    assert duplicate.outcome == "indeterminate"
    assert duplicate.error.error_code == "dequeue_adapter_unavailable"
    assert restarted.get(
        authenticated_operator_id=admission.operator_id,
        permission_verified=True,
        dequeue_id=dequeue_id,
        correlation_id="readback",
    ).error.error_code == "not_found"
    assert restarted.list(
        authenticated_operator_id=admission.operator_id,
        permission_verified=True,
        candidate_record_id=admission.candidate_record_id,
        correlation_id="list",
    ).count == 0


def test_injected_adapter_records_one_exact_success_and_never_replays(
    tmp_path: Path,
) -> None:
    adapter = Adapter(outcome="success")
    dequeue_service, dequeue_store, reader, admission, _, create = _service(
        tmp_path, queue_adapter=adapter
    )
    created = _record(dequeue_service, admission, create)
    assert created.ok is True
    assert created.outcome == "success"
    assert created.record is not None
    assert created.record.disposition == "exact_inert_item_dequeued"
    assert created.record.dequeue_id == _reserved_dequeue_id(admission, create, tmp_path)
    assert adapter.calls[0].dequeue_id == created.record.dequeue_id
    assert adapter.calls[0].inert_queue_item_id == (
        admission.queue_observation_receipt.v042_enqueue.queue_item.queue_item_id
    )
    assert reader.calls == 1

    duplicate = _record(dequeue_service, admission, create)
    assert duplicate.record == created.record
    assert len(adapter.calls) == 1
    assert reader.calls == 1
    attempts = dequeue_store.list_attempts(
        operator_id=admission.operator_id,
        dequeue_id=created.record.dequeue_id,
    )
    assert tuple(attempt.outcome for attempt in attempts) == ("indeterminate",)


def test_adapter_failure_and_timeout_are_terminal_redacted_records(
    tmp_path: Path,
) -> None:
    failure_adapter = Adapter(outcome="failure")
    failure_service, _, _, admission, _, create = _service(
        tmp_path / "failure", queue_adapter=failure_adapter
    )
    failure = _record(failure_service, admission, create)
    assert failure.ok is True
    assert failure.outcome == "failure"
    assert failure.record is not None
    assert failure.record.disposition == "exact_inert_item_not_dequeued"
    assert failure.error is None
    assert len(failure_adapter.calls) == 1

    timeout_adapter = Adapter(fail=TimeoutError("secret queue endpoint timed out"))
    timeout_service, _, _, admission2, _, create2 = _service(
        tmp_path / "timeout", queue_adapter=timeout_adapter
    )
    timeout = _record(timeout_service, admission2, create2)
    assert timeout.ok is True
    assert timeout.outcome == "indeterminate"
    assert timeout.record is not None
    assert timeout.record.disposition == "dequeue_completion_indeterminate"
    assert "secret queue endpoint" not in timeout.model_dump_json()

    duplicate = _record(timeout_service, admission2, create2)
    assert duplicate.record == timeout.record
    assert len(timeout_adapter.calls) == 1


def test_auth_permission_disabled_missing_and_redaction_fail_before_effect(
    tmp_path: Path,
) -> None:
    dequeue_service, _, reader, admission, _, create = _service(tmp_path, enabled=False)
    assert _record(dequeue_service, admission, create).error.error_code == (
        "installation_capability_unsupported"
    )
    assert _record(
        dequeue_service, admission, create, authenticated_operator_id=None
    ).error.error_code == "unauthenticated"
    assert _record(
        dequeue_service, admission, create, permission_verified=False
    ).error.error_code == "forbidden"
    assert reader.calls == 0

    missing, _, missing_reader, admission2, _, create2 = _service(
        tmp_path / "missing", evidence=None
    )
    missing_reader.value = None
    result = _record(
        missing,
        admission2,
        create2,
        correlation_id="secret/internal/path/token",
    )
    assert result.error.error_code == "not_found"
    assert "secret/internal/path/token" not in result.model_dump_json()


def test_idempotency_conflict_subject_no_replay_and_secret_free_persistence(
    tmp_path: Path,
) -> None:
    dequeue_service, dequeue_store, reader, admission, _, create = _service(tmp_path)
    assert _record(dequeue_service, admission, create).error.error_code == (
        "dequeue_adapter_unavailable"
    )
    exact = _record(dequeue_service, admission, create)
    assert exact.error.error_code == "dequeue_adapter_unavailable"
    assert reader.calls == 1

    changed = create.model_copy(
        update={"item_identity_fingerprint": create.item_identity_fingerprint.model_copy(update={"value": "a" * 64})}
    )
    conflict = _record(dequeue_service, admission, changed)
    assert conflict.error.error_code == "idempotency_conflict"

    subject_retry = _record(
        dequeue_service,
        admission,
        create,
        idempotency_key="one-shot-controlled-dequeue-key-2",
    )
    assert subject_retry.error.error_code == "permanent_subject_reserved"
    with sqlite3.connect(dequeue_store.database_path) as connection:
        schema = connection.execute(
            """SELECT sql FROM sqlite_master
            WHERE name = 'one_shot_controlled_dequeue_reservations'"""
        ).fetchone()[0]
        rows = connection.execute(
            "SELECT * FROM one_shot_controlled_dequeue_reservations"
        ).fetchall()
    assert "one-shot-controlled-dequeue-key-1" not in schema
    assert all("one-shot-controlled-dequeue-key-1" not in str(value) for row in rows for value in row)


def test_concurrent_same_request_has_one_permanent_reservation(tmp_path: Path) -> None:
    dequeue_service, dequeue_store, _, admission, _, create = _service(tmp_path)

    def submit():
        return _record(dequeue_service, admission, create).error.error_code

    with ThreadPoolExecutor(max_workers=8) as executor:
        results = tuple(executor.map(lambda _index: submit(), range(8)))
    assert set(results) == {"dequeue_adapter_unavailable"}
    with sqlite3.connect(dequeue_store.database_path) as connection:
        reservation_count = connection.execute(
            "SELECT COUNT(*) FROM one_shot_controlled_dequeue_reservations"
        ).fetchone()[0]
        attempt_count = connection.execute(
            "SELECT COUNT(*) FROM one_shot_controlled_dequeue_attempts"
        ).fetchone()[0]
    assert reservation_count == 1
    assert attempt_count >= 1


def test_quota_bounds_corruption_and_stable_request_fingerprint(tmp_path: Path) -> None:
    quota_service, _, _, admission, _, create = _service(tmp_path / "quota", quota=0)
    assert _record(quota_service, admission, create).error.error_code == "quota_exceeded"

    bounded, _, _, admission2, _, create2 = _service(
        tmp_path / "bounded", max_model_bytes=1
    )
    assert _record(bounded, admission2, create2).error.error_code == "record_too_large"

    corrupt, dequeue_store, _, admission3, _, create3 = _service(tmp_path / "corrupt")
    assert _record(corrupt, admission3, create3).error.error_code == (
        "dequeue_adapter_unavailable"
    )
    with sqlite3.connect(dequeue_store.database_path) as connection:
        connection.execute(
            "UPDATE one_shot_controlled_dequeue_reservations SET reservation_json = ?",
            ("{}",),
        )
    idem = idempotency_key_fingerprint(
        admission3.operator_id, "one-shot-controlled-dequeue-key-1"
    )
    assert corrupt.create(
        create3,
        authenticated_operator_id=admission3.operator_id,
        permission_verified=True,
        candidate_record_id=admission3.candidate_record_id,
        idempotency_key="one-shot-controlled-dequeue-key-1",
        correlation_id="corrupt",
    ).error.error_code == "store_corrupt"
    assert request_fingerprint(
        operator_id=admission3.operator_id,
        candidate_record_id=admission3.candidate_record_id,
        create=create3,
        request_received_at="2026-08-27T12:00:36Z",
        idempotency_fingerprint=idem,
    ) == request_fingerprint(
        operator_id=admission3.operator_id,
        candidate_record_id=admission3.candidate_record_id,
        create=create3,
        request_received_at="2026-08-27T12:00:50Z",
        idempotency_fingerprint=idem,
    )


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
                "enqueue",
                "dequeue",
                "execute",
                "dispatch",
                "retry",
                "resend",
                "start",
                "start_worker",
            }
            for node in ast.walk(tree)
        )
    consumers = []
    for path in root.rglob("*.py"):
        if path.parent.name == "one_shot_controlled_dequeue" or path.name.startswith(
            "test_"
        ):
            continue
        source = path.read_text()
        if (
            "one_shot_controlled_dequeue.service" in source
            or "OneShotControlledDequeueReservationService" in source
        ):
            consumers.append(path)
    assert consumers == []
