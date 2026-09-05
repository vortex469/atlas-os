from __future__ import annotations

import ast
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path

from app.controlled_dequeue_admission import service, store
from app.controlled_dequeue_admission.contract import (
    PERMISSION,
    ControlledDequeueAdmissionAuthorityContextV1,
    ControlledDequeueAdmissionValidationInputV1,
    build_admission,
    build_audit,
    build_collection,
    build_reservations,
    opaque_fingerprint,
)
from app.controlled_dequeue_admission.service import (
    create_controlled_dequeue_admission_service,
)
from app.controlled_dequeue_admission.store import ControlledDequeueAdmissionStore
from app.controlled_dequeue_admission.test_contract import _facts


class Reader:
    def __init__(self, value) -> None:
        self.value = value
        self.calls = 0

    def read_owned(self, **_kwargs):
        self.calls += 1
        return self.value


def _clock(second: int = 35):
    instant = datetime(2026, 8, 27, 12, 0, tzinfo=UTC) + timedelta(seconds=second)
    return lambda: instant


def _service(
    tmp_path: Path,
    *,
    evidence=None,
    second: int = 35,
    quota: int = 16,
    max_model_bytes: int = 192 * 1024,
    enabled: bool = True,
):
    receipt, status, create = _facts(tmp_path)
    evidence_reader = Reader(evidence if evidence is not None else (receipt, status))
    admission_store = ControlledDequeueAdmissionStore(
        tmp_path / "controlled-dequeue-admission.sqlite3",
        max_records_per_operator=quota,
        max_model_bytes=max_model_bytes,
    )
    admission_service = create_controlled_dequeue_admission_service(
        evidence_reader=evidence_reader,
        store=admission_store,
        clock=_clock(second),
        enabled=enabled,
    )
    return admission_service, admission_store, evidence_reader, receipt, status, create


def _record(admission_service, receipt, create, **changes):
    values = {
        "authenticated_operator_id": receipt.operator_id,
        "permission_verified": True,
        "candidate_record_id": receipt.candidate_record_id,
        "idempotency_key": "controlled-dequeue-admission-key-1",
        "correlation_id": "controlled-dequeue-admission-correlation-1",
    }
    values.update(changes)
    return admission_service.create(create, **values)


def test_create_get_list_and_restart_safe_owner_readback(tmp_path: Path) -> None:
    admission_service, admission_store, reader, receipt, _status, create = _service(
        tmp_path
    )
    created = _record(admission_service, receipt, create)
    assert created.ok
    assert created.record.disposition == "controlled_dequeue_admission_recorded"
    assert created.status.lifecycle == "active"
    assert reader.calls == 1
    assert not created.record.dequeue_allowed
    assert not created.record.dequeue_attempted
    assert not created.record.dequeued
    assert not created.record.queue_polling_allowed
    assert not created.record.queue_claim_allowed
    assert not created.record.queue_lease_allowed
    assert not created.record.queue_ack_allowed
    assert not created.record.worker_contact_allowed
    assert not created.record.agent_invocation_allowed
    assert not created.record.process_execution_allowed

    restarted = create_controlled_dequeue_admission_service(
        evidence_reader=Reader(None),
        store=ControlledDequeueAdmissionStore(admission_store.database_path),
        clock=_clock(70),
    )
    readback = restarted.get(
        authenticated_operator_id=receipt.operator_id,
        permission_verified=True,
        admission_id=created.record.admission_id,
        correlation_id="readback",
    )
    assert readback.record == created.record
    assert readback.status.lifecycle == "expired"
    listed = restarted.list(
        authenticated_operator_id=receipt.operator_id,
        permission_verified=True,
        candidate_record_id=receipt.candidate_record_id,
        correlation_id="list",
    )
    assert tuple(item.admission_id for item in listed.items) == (
        created.record.admission_id,
    )
    assert restarted.get(
        authenticated_operator_id="operator-b",
        permission_verified=True,
        admission_id=created.record.admission_id,
        correlation_id="foreign",
    ).error.error_code == "not_found"
    foreign = restarted.list(
        authenticated_operator_id="operator-b",
        permission_verified=True,
        candidate_record_id=receipt.candidate_record_id,
        correlation_id="foreign-list",
    )
    assert foreign.count == 0


def test_disabled_auth_permission_and_missing_fail_before_reservation(
    tmp_path: Path,
) -> None:
    admission_service, admission_store, reader, receipt, _status, create = _service(
        tmp_path, enabled=False
    )
    assert _record(admission_service, receipt, create).error.error_code == (
        "installation_capability_unsupported"
    )
    assert _record(
        admission_service, receipt, create, authenticated_operator_id=None
    ).error.error_code == "unauthenticated"
    assert _record(
        admission_service, receipt, create, permission_verified=False
    ).error.error_code == "forbidden"
    assert reader.calls == 0
    assert admission_store.list_owned(
        operator_id=receipt.operator_id,
        candidate_record_id=receipt.candidate_record_id,
    ) == ()

    missing, missing_store, missing_reader, receipt2, _status2, create2 = _service(
        tmp_path / "missing", evidence=None
    )
    missing_reader.value = None
    result = _record(missing, receipt2, create2, correlation_id="secret/internal/path")
    assert result.error.error_code == "not_found"
    assert missing_store.list_owned(
        operator_id=receipt2.operator_id,
        candidate_record_id=receipt2.candidate_record_id,
    ) == ()
    assert "secret/internal/path" not in result.model_dump_json()


def test_factory_default_is_disabled_and_has_zero_effect_before_enablement(
    tmp_path: Path,
) -> None:
    receipt, status, create = _facts(tmp_path)
    reader = Reader((receipt, status))
    admission_store = ControlledDequeueAdmissionStore(
        tmp_path / "default-off" / "controlled-dequeue-admission.sqlite3"
    )
    admission_service = create_controlled_dequeue_admission_service(
        evidence_reader=reader,
        store=admission_store,
        clock=_clock(),
    )
    result = _record(admission_service, receipt, create)
    assert result.error.error_code == "installation_capability_unsupported"
    assert reader.calls == 0
    assert admission_store.list_owned(
        operator_id=receipt.operator_id,
        candidate_record_id=receipt.candidate_record_id,
    ) == ()


def test_exact_duplicate_zero_reader_raw_key_not_persisted_and_expiry_readable(
    tmp_path: Path,
) -> None:
    admission_service, admission_store, reader, receipt, _status, create = _service(
        tmp_path
    )
    created = _record(admission_service, receipt, create)
    assert created.ok

    duplicate_service = create_controlled_dequeue_admission_service(
        evidence_reader=reader,
        store=ControlledDequeueAdmissionStore(admission_store.database_path),
        clock=_clock(70),
        enabled=True,
    )
    duplicate = _record(duplicate_service, receipt, create)
    assert duplicate.ok
    assert duplicate.record == created.record
    assert duplicate.status.lifecycle == "expired"
    assert reader.calls == 1
    with sqlite3.connect(admission_store.database_path) as connection:
        rows = []
        for table in (
            "controlled_dequeue_admission_reservations",
            "controlled_dequeue_admissions",
            "controlled_dequeue_admission_attempts",
        ):
            rows.extend(connection.execute(f"SELECT * FROM {table}").fetchall())
        schema_rows = connection.execute(
            "SELECT sql FROM sqlite_master WHERE name LIKE 'controlled_dequeue%'"
        ).fetchall()
    persisted = "\n".join(str(value) for row in rows + schema_rows for value in row)
    assert "controlled-dequeue-admission-key-1" not in persisted
    assert "secret" not in persisted
    assert "sh -c" not in persisted
    assert "token" not in persisted.lower()


def test_idempotency_subject_conflicts_and_p1_validation_integration(
    tmp_path: Path,
) -> None:
    admission_service, admission_store, reader, receipt, _status, create = _service(
        tmp_path
    )
    assert _record(admission_service, receipt, create).ok
    subject_retry = _record(
        admission_service,
        receipt,
        create,
        idempotency_key="another-permanent-key",
    )
    assert subject_retry.error.error_code == "permanent_subject_reserved"
    changed = create.model_copy(
        update={"queue_observation_receipt_valid_until": "2026-08-27T12:00:44Z"}
    )
    assert _record(admission_service, receipt, changed).error.error_code == (
        "idempotency_conflict"
    )

    mismatch, mismatch_store, mismatch_reader, receipt2, _status2, create2 = _service(
        tmp_path / "mismatch"
    )
    bad = create2.model_copy(
        update={
            "inherited_limits_fingerprint": (
                create2.inherited_limits_fingerprint.model_copy(update={"value": "f" * 64})
            )
        }
    )
    assert _record(mismatch, receipt2, bad).error.error_code == (
        "inherited_limits_mismatch"
    )
    assert mismatch_reader.calls == 1
    assert mismatch_store.list_owned(
        operator_id=receipt2.operator_id,
        candidate_record_id=receipt2.candidate_record_id,
    ) == ()
    assert reader.calls == 2
    assert admission_store.list_owned(
        operator_id=receipt.operator_id,
        candidate_record_id=receipt.candidate_record_id,
    )


def test_concurrent_duplicate_reservation_yields_one_durable_record(
    tmp_path: Path,
) -> None:
    admission_service, admission_store, _reader, receipt, _status, create = _service(
        tmp_path
    )
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(
            pool.map(lambda _index: _record(admission_service, receipt, create), range(8))
        )
    assert any(result.ok for result in results)
    assert all(
        result.ok or result.error.error_code == "append_indeterminate"
        for result in results
    )
    listed = admission_store.list_owned(
        operator_id=receipt.operator_id,
        candidate_record_id=receipt.candidate_record_id,
    )
    assert len(listed) == 1
    assert {
        result.record.admission_record_fingerprint.value
        for result in results
        if result.ok
    } == {listed[0].admission_record_fingerprint.value}


def test_permanent_no_replay_after_attempt_start_and_indeterminate_readback(
    tmp_path: Path,
) -> None:
    _admission_service, admission_store, _reader, receipt, status, create = _service(
        tmp_path
    )
    validation = ControlledDequeueAdmissionValidationInputV1(
        operator_id=receipt.operator_id,
        authority=ControlledDequeueAdmissionAuthorityContextV1(
            authenticated_operator_id=receipt.operator_id,
            permission=PERMISSION,
            request_received_at="2026-08-27T12:00:35Z",
        ),
        candidate_record_id=receipt.candidate_record_id,
        create=create,
        queue_observation_receipt=receipt,
        queue_observation_receipt_status=status,
        idempotency_key="controlled-dequeue-admission-key-1",
    )
    record = build_admission(validation)
    idempotency, reservation = build_reservations(validation, record)
    audit = build_audit(
        record,
        event="controlled_dequeue_admission_indeterminate",
        outcome="indeterminate",
        correlation_fingerprint=opaque_fingerprint("atlas:test:v1", "indeterminate"),
        occurred_at=record.recorded_at,
    )
    try:
        admission_store.append(
            record=record,
            idempotency_reservation=idempotency,
            subject_reservation=reservation,
            audit_evidence=audit,
            v043_receipt_valid_until=create.queue_observation_receipt_valid_until,
            force_indeterminate=True,
        )
    except store.ControlledDequeueAdmissionStoreError as error:
        assert error.code == "append_indeterminate"
    retry_service = create_controlled_dequeue_admission_service(
        evidence_reader=Reader((receipt, status)),
        store=ControlledDequeueAdmissionStore(admission_store.database_path),
        clock=_clock(),
        enabled=True,
    )
    retry = _record(retry_service, receipt, create)
    assert retry.error.error_code == "append_indeterminate"
    assert not retry.ok
    assert retry.outcome == "indeterminate"
    with sqlite3.connect(admission_store.database_path) as connection:
        reservations = connection.execute(
            "SELECT COUNT(*) FROM controlled_dequeue_admission_reservations"
        ).fetchone()[0]
        records = connection.execute(
            "SELECT COUNT(*) FROM controlled_dequeue_admissions"
        ).fetchone()[0]
        attempts = connection.execute(
            "SELECT COUNT(*) FROM controlled_dequeue_admission_attempts"
        ).fetchone()[0]
    assert reservations == 1
    assert records == 0
    assert attempts == 1


def test_quota_record_bounds_and_corruption_fail_closed(tmp_path: Path) -> None:
    quota_fixtures = _service(tmp_path / "quota", quota=0)
    quota_service = quota_fixtures[0]
    receipt = quota_fixtures[3]
    create = quota_fixtures[5]
    assert _record(quota_service, receipt, create).error.error_code == "quota_exceeded"

    bounded_fixtures = _service(tmp_path / "bounded", max_model_bytes=1)
    bounded = bounded_fixtures[0]
    receipt2 = bounded_fixtures[3]
    create2 = bounded_fixtures[5]
    assert _record(bounded, receipt2, create2).error.error_code == "record_too_large"

    clean, admission_store, _reader, receipt3, _status3, create3 = _service(
        tmp_path / "corrupt"
    )
    created = _record(clean, receipt3, create3)
    assert created.ok
    with sqlite3.connect(admission_store.database_path) as connection:
        connection.execute("UPDATE controlled_dequeue_admissions SET record_json = ?", ("{}",))
    assert clean.get(
        authenticated_operator_id=receipt3.operator_id,
        permission_verified=True,
        admission_id=created.record.admission_id,
        correlation_id="corrupt",
    ).error.error_code == "store_corrupt"


def test_store_is_append_only_bounded_and_has_no_effect_api(tmp_path: Path) -> None:
    admission_service, admission_store, _reader, receipt, _status, create = _service(
        tmp_path
    )
    created = _record(admission_service, receipt, create)
    assert created.ok
    collection = build_collection(
        operator_id=receipt.operator_id,
        candidate_record_id=receipt.candidate_record_id,
        items=admission_store.list_owned(
            operator_id=receipt.operator_id,
            candidate_record_id=receipt.candidate_record_id,
        ),
    )
    assert collection.count == 1
    assert not any(
        hasattr(ControlledDequeueAdmissionStore, name)
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
    assert "DELETE FROM controlled_dequeue" not in source
    assert "UPDATE controlled_dequeue" not in source


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
        if path.parent.name == "controlled_dequeue_admission":
            continue
        if path.name.startswith("test_"):
            continue
        source_text = path.read_text()
        if (
            "controlled_dequeue_admission.service" in source_text
            or "ControlledDequeueAdmissionService" in source_text
        ):
            consumers.append(path)
    assert consumers == []


def test_agent_and_execution_worker_do_not_consume_controlled_dequeue_admissions() -> None:
    root = Path(__file__).resolve().parents[4]
    forbidden_markers = (
        "controlled_dequeue_admission",
        "ControlledDequeueAdmission",
        "controlledDequeueAdmission",
        "controlled-dequeue-admissions",
        "controlled_dequeue_admission_recorded",
    )
    consumers = []
    for directory in (
        root / "services" / "atlas-agent",
        root / "services" / "atlas-execution-worker",
    ):
        for path in directory.rglob("*"):
            if path.is_dir() or path.suffix not in {".py", ".ts", ".tsx", ".md"}:
                continue
            if path.name.startswith("test_") or "/tests/" in path.as_posix():
                continue
            source_text = path.read_text(encoding="utf-8")
            if any(marker in source_text for marker in forbidden_markers):
                consumers.append(path.relative_to(root).as_posix())
    assert consumers == []
