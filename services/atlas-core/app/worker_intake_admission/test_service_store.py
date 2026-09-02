from __future__ import annotations

import ast
import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path

from app.worker_intake_admission import service, store
from app.worker_intake_admission.service import create_worker_intake_admission_service
from app.worker_intake_admission.store import WorkerIntakeAdmissionStore
from app.worker_intake_admission.test_contract import (
    ADMISSION_ID,
    DECISION_ID,
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
    identity=None,
    intake=None,
    second: int = 34,
    quota: int = 16,
    max_model_bytes: int = 128 * 1024,
    enabled: bool = True,
):
    reservation, status, worker_identity, intake_reference, create = _facts(tmp_path)
    evidence_reader = Reader(
        evidence if evidence is not None else (reservation, status, False)
    )
    identity_reader = Reader(worker_identity if identity is None else identity)
    intake_reader = Reader(intake_reference if intake is None else intake)
    admission_factory = Factory(ADMISSION_ID)
    decision_factory = Factory(DECISION_ID)
    admission_store = WorkerIntakeAdmissionStore(
        tmp_path / "worker-intake-admissions.sqlite3",
        max_records_per_operator=quota,
        max_model_bytes=max_model_bytes,
    )
    admission_service = create_worker_intake_admission_service(
        evidence_reader=evidence_reader,
        worker_identity_reader=identity_reader,
        worker_intake_reference_reader=intake_reader,
        store=admission_store,
        clock=_clock(second),
        admission_id_factory=admission_factory,
        decision_id_factory=decision_factory,
        enabled=enabled,
    )
    return (
        admission_service,
        admission_store,
        evidence_reader,
        identity_reader,
        intake_reader,
        admission_factory,
        decision_factory,
        reservation,
        status,
        worker_identity,
        intake_reference,
        create,
    )


def _record(admission_service, reservation, create, **changes):
    values = {
        "authenticated_operator_id": reservation.operator_id,
        "permission_verified": True,
        "candidate_record_id": reservation.candidate_record_id,
        "idempotency_key": "worker-intake-admission-key-1",
        "correlation_id": "worker-intake-admission-correlation-1",
    }
    values.update(changes)
    return admission_service.create(create, **values)


def test_create_get_list_and_restart_safe_owner_readback(tmp_path: Path) -> None:
    (
        admission_service,
        admission_store,
        evidence_reader,
        identity_reader,
        intake_reader,
        *_,
        reservation,
        _status,
        _identity,
        _intake,
        create,
    ) = _service(tmp_path)
    created = _record(admission_service, reservation, create)
    assert created.ok
    assert created.admission.eligibility == "worker_intake_admission_recorded"
    assert evidence_reader.calls == identity_reader.calls == intake_reader.calls == 1
    assert not created.admission.live_enqueue_allowed
    assert not created.admission.dequeue_allowed
    assert not created.admission.worker_start_allowed
    assert not created.admission.execution_start_allowed

    restarted = create_worker_intake_admission_service(
        evidence_reader=Reader(None),
        worker_identity_reader=Reader(None),
        worker_intake_reference_reader=Reader(None),
        store=WorkerIntakeAdmissionStore(admission_store.database_path),
        clock=_clock(50),
        admission_id_factory=Factory("6f80fe47-d0dc-4449-b65d-bdb0e0a365e3"),
        decision_id_factory=Factory("f87d1208-4b38-5a6d-8a79-fc9887367c0f"),
    )
    readback = restarted.get(
        authenticated_operator_id=reservation.operator_id,
        permission_verified=True,
        admission_id=ADMISSION_ID,
        correlation_id="readback",
    )
    assert readback.admission == created.admission
    listed = restarted.list(
        authenticated_operator_id=reservation.operator_id,
        permission_verified=True,
        candidate_record_id=reservation.candidate_record_id,
        correlation_id="list",
    )
    assert tuple(item.admission_id for item in listed.items) == (ADMISSION_ID,)
    assert restarted.get(
        authenticated_operator_id="operator-b",
        permission_verified=True,
        admission_id=ADMISSION_ID,
        correlation_id="foreign",
    ).error.error_code == "not_found"
    foreign = restarted.list(
        authenticated_operator_id="operator-b",
        permission_verified=True,
        candidate_record_id=reservation.candidate_record_id,
        correlation_id="foreign-list",
    )
    assert foreign.count == 0


def test_disabled_auth_and_permission_fail_before_readers(tmp_path: Path) -> None:
    admission_service, _, evidence_reader, identity_reader, intake_reader, *tail = (
        _service(tmp_path, enabled=False)
    )
    reservation, create = tail[-5], tail[-1]
    assert _record(admission_service, reservation, create).error.error_code == (
        "installation_capability_unsupported"
    )
    assert _record(
        admission_service, reservation, create, authenticated_operator_id=None
    ).error.error_code == "unauthenticated"
    assert _record(
        admission_service, reservation, create, permission_verified=False
    ).error.error_code == "forbidden"
    assert evidence_reader.calls == identity_reader.calls == intake_reader.calls == 0


def test_exact_duplicate_is_zero_reader_and_raw_key_is_not_persisted(
    tmp_path: Path,
) -> None:
    (
        admission_service,
        admission_store,
        evidence_reader,
        identity_reader,
        intake_reader,
        admission_factory,
        decision_factory,
        reservation,
        _status,
        _identity,
        _intake,
        create,
    ) = _service(tmp_path)
    created = _record(admission_service, reservation, create)
    duplicate = _record(admission_service, reservation, create)
    assert duplicate.ok
    assert duplicate.admission == created.admission
    assert evidence_reader.calls == identity_reader.calls == intake_reader.calls == 1
    assert admission_factory.calls == decision_factory.calls == 1
    with sqlite3.connect(admission_store.database_path) as connection:
        schema = connection.execute(
            """SELECT sql FROM sqlite_master
            WHERE name = 'worker_intake_admissions'"""
        ).fetchone()[0]
        row = connection.execute("SELECT * FROM worker_intake_admissions").fetchone()
    assert "worker-intake-admission-key-1" not in schema
    assert all("worker-intake-admission-key-1" not in str(value) for value in row)


def test_idempotency_conflict_and_permanent_subject_no_replay(tmp_path: Path) -> None:
    admission_service, *_tail, reservation, _status, _identity, _intake, create = (
        _service(tmp_path)
    )
    assert _record(admission_service, reservation, create).ok
    subject_retry = _record(
        admission_service,
        reservation,
        create,
        idempotency_key="another-permanent-key",
    )
    assert subject_retry.error.error_code == "conflict"
    changed = create.model_copy(
        update={"worker_queue_reservation_valid_until": "2026-08-27T12:00:44Z"}
    )
    conflict = admission_service.create(
        changed,
        authenticated_operator_id=reservation.operator_id,
        permission_verified=True,
        candidate_record_id=reservation.candidate_record_id,
        idempotency_key="worker-intake-admission-key-1",
        correlation_id="conflict",
    )
    assert conflict.error.error_code == "conflict"


def test_owner_missing_and_redaction_fail_closed(tmp_path: Path) -> None:
    fixtures = _service(tmp_path)
    admission_service = fixtures[0]
    evidence_reader = fixtures[2]
    reservation = fixtures[7]
    create = fixtures[11]
    assert _record(
        admission_service, reservation, create, authenticated_operator_id="operator-b"
    ).error.error_code == "not_found"
    assert evidence_reader.calls == 1
    missing, *_missing_tail = _service(tmp_path / "missing")
    missing._evidence_reader = Reader(None)  # explicitly injected test dependency
    result = _record(
        missing, reservation, create, correlation_id="secret/internal/path"
    )
    assert result.error.error_code == "not_found"
    assert "secret/internal/path" not in result.model_dump_json()


def test_stale_home_assistant_linkage_and_limits_are_blocked(tmp_path: Path) -> None:
    stale, *_tail, reservation, _status, _identity, _intake, create = _service(
        tmp_path / "stale", second=50
    )
    assert _record(stale, reservation, create).error.error_code == "evidence_expired"

    reservation2, status2, identity2, intake2, create2 = _facts(tmp_path / "home-facts")
    home, *_ = _service(
        tmp_path / "home",
        evidence=(reservation2, status2, True),
        identity=identity2,
        intake=intake2,
    )
    assert _record(home, reservation2, create2).error.error_code == (
        "installation_capability_unsupported"
    )

    mismatch, *_tail, reservation3, _status3, _identity3, _intake3, create3 = (
        _service(tmp_path / "mismatch")
    )
    bad = create3.model_copy(
        update={
            "worker_intake_reference_fingerprint": (
                create3.worker_intake_reference_fingerprint.model_copy(
                    update={"value": "f" * 64}
                )
            )
        }
    )
    assert _record(
        mismatch,
        reservation3,
        bad,
        idempotency_key="intake-linkage-mismatch-key",
    ).error.error_code == "linkage_mismatch"
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
        reservation3,
        limits,
        idempotency_key="intake-limits-mismatch-key",
    ).error.error_code == "inherited_limits_mismatch"


def test_quota_record_bounds_and_corruption_fail_closed(tmp_path: Path) -> None:
    quota_service, *_tail, reservation, _status, _identity, _intake, create = (
        _service(tmp_path / "quota", quota=0)
    )
    assert _record(quota_service, reservation, create).error.error_code == (
        "quota_exceeded"
    )

    bounded, *_tail, reservation2, _status2, _identity2, _intake2, create2 = _service(
        tmp_path / "bounded", max_model_bytes=1
    )
    assert _record(
        bounded, reservation2, create2
    ).error.error_code == "record_too_large"

    corrupt_fixtures = _service(tmp_path / "corrupt")
    clean = corrupt_fixtures[0]
    admission_store = corrupt_fixtures[1]
    reservation3 = corrupt_fixtures[7]
    create3 = corrupt_fixtures[11]
    assert _record(clean, reservation3, create3).ok
    with sqlite3.connect(admission_store.database_path) as connection:
        connection.execute(
            "UPDATE worker_intake_admissions SET record_json = ?", ("{}",)
        )
    assert clean.get(
        authenticated_operator_id=reservation3.operator_id,
        permission_verified=True,
        admission_id=ADMISSION_ID,
        correlation_id="corrupt",
    ).error.error_code == "store_corrupt"


def test_store_is_append_only_and_has_no_effect_api() -> None:
    assert not any(
        hasattr(WorkerIntakeAdmissionStore, name)
        for name in (
            "update",
            "delete",
            "release",
            "consume",
            "enqueue",
            "dequeue",
            "dispatch",
            "execute",
            "start_worker",
        )
    )
    source = Path(store.__file__).read_text()
    assert "UPDATE worker_intake_admissions" not in source
    assert "DELETE FROM worker_intake_admissions" not in source


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
            name for name in imported if any(term in name for term in forbidden_imports)
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
        if path.parent.name == "worker_intake_admission" or path.name.startswith(
            "test_"
        ):
            continue
        source = path.read_text()
        if (
            "worker_intake_admission.service" in source
            or "WorkerIntakeAdmissionService" in source
        ):
            consumers.append(path)
    assert consumers == []
