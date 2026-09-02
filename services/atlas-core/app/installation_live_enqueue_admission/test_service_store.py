from __future__ import annotations

import ast
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path

from app.installation_live_enqueue_admission import service, store
from app.installation_live_enqueue_admission.service import (
    create_live_enqueue_admission_service,
)
from app.installation_live_enqueue_admission.store import LiveEnqueueAdmissionStore
from app.installation_live_enqueue_admission.test_contract import _facts


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
    quota: int = 100,
    max_model_bytes: int = 128 * 1024,
    enabled: bool = True,
):
    intake, intake_status, queue, queue_status, create = _facts(tmp_path)
    evidence_reader = Reader(
        evidence
        if evidence is not None
        else (intake, intake_status, queue, queue_status)
    )
    admission_store = LiveEnqueueAdmissionStore(
        tmp_path / "live-enqueue-admissions.sqlite3",
        max_records_per_operator=quota,
        max_model_bytes=max_model_bytes,
    )
    admission_service = create_live_enqueue_admission_service(
        evidence_reader=evidence_reader,
        store=admission_store,
        clock=_clock(second),
        enabled=enabled,
    )
    return (
        admission_service,
        admission_store,
        evidence_reader,
        intake,
        intake_status,
        queue,
        queue_status,
        create,
    )


def _record(admission_service, intake, create, **changes):
    values = {
        "authenticated_operator_id": intake.operator_id,
        "permission_verified": True,
        "candidate_record_id": intake.candidate_record_id,
        "idempotency_key": "live-enqueue-admission-key-1",
        "correlation_id": "live-enqueue-admission-correlation-1",
    }
    values.update(changes)
    return admission_service.create(create, **values)


def test_create_get_list_and_restart_safe_owner_readback(tmp_path: Path) -> None:
    (
        admission_service,
        admission_store,
        evidence_reader,
        intake,
        _intake_status,
        _queue,
        _queue_status,
        create,
    ) = _service(tmp_path)
    created = _record(admission_service, intake, create)
    assert created.ok
    assert created.admission.eligibility == "live_enqueue_admission_recorded"
    assert created.status.lifecycle == "active"
    assert evidence_reader.calls == 1
    assert not created.admission.live_enqueue_allowed
    assert not created.admission.payload_constructed
    assert not created.admission.queue_send_allowed
    assert not created.admission.worker_contact_allowed
    assert not created.admission.execution_start_allowed

    restarted = create_live_enqueue_admission_service(
        evidence_reader=Reader(None),
        store=LiveEnqueueAdmissionStore(admission_store.database_path),
        clock=_clock(50),
    )
    readback = restarted.get(
        authenticated_operator_id=intake.operator_id,
        permission_verified=True,
        admission_id=created.admission.admission_id,
        correlation_id="readback",
    )
    assert readback.admission == created.admission
    assert readback.status.lifecycle == "expired"
    listed = restarted.list(
        authenticated_operator_id=intake.operator_id,
        permission_verified=True,
        candidate_record_id=intake.candidate_record_id,
        correlation_id="list",
    )
    assert tuple(item.admission_id for item in listed.items) == (
        created.admission.admission_id,
    )
    assert restarted.get(
        authenticated_operator_id="operator-b",
        permission_verified=True,
        admission_id=created.admission.admission_id,
        correlation_id="foreign",
    ).error.error_code == "not_found"
    foreign = restarted.list(
        authenticated_operator_id="operator-b",
        permission_verified=True,
        candidate_record_id=intake.candidate_record_id,
        correlation_id="foreign-list",
    )
    assert foreign.count == 0


def test_disabled_auth_permission_and_missing_fail_before_append(tmp_path: Path) -> None:
    admission_service, admission_store, evidence_reader, intake, *_tail, create = (
        _service(tmp_path, enabled=False)
    )
    assert _record(admission_service, intake, create).error.error_code == (
        "installation_capability_unsupported"
    )
    assert _record(
        admission_service, intake, create, authenticated_operator_id=None
    ).error.error_code == "unauthenticated"
    assert _record(
        admission_service, intake, create, permission_verified=False
    ).error.error_code == "forbidden"
    assert evidence_reader.calls == 0
    assert admission_store.list_owned(
        operator_id=intake.operator_id,
        candidate_record_id=intake.candidate_record_id,
    ) == ()

    missing, missing_store, missing_reader, intake2, *_missing_tail, create2 = (
        _service(tmp_path / "missing", evidence=None)
    )
    missing_reader.value = None
    result = _record(missing, intake2, create2, correlation_id="secret/internal/path")
    assert result.error.error_code == "not_found"
    assert missing_store.list_owned(
        operator_id=intake2.operator_id,
        candidate_record_id=intake2.candidate_record_id,
    ) == ()
    assert "secret/internal/path" not in result.model_dump_json()


def test_exact_duplicate_zero_reader_raw_key_not_persisted_and_expiry_readable(
    tmp_path: Path,
) -> None:
    (
        admission_service,
        admission_store,
        evidence_reader,
        intake,
        _intake_status,
        _queue,
        _queue_status,
        create,
    ) = _service(tmp_path)
    created = _record(admission_service, intake, create)

    duplicate_service = create_live_enqueue_admission_service(
        evidence_reader=evidence_reader,
        store=LiveEnqueueAdmissionStore(admission_store.database_path),
        clock=_clock(70),
        enabled=True,
    )
    duplicate = _record(duplicate_service, intake, create)
    assert duplicate.ok
    assert duplicate.admission == created.admission
    assert duplicate.status.lifecycle == "expired"
    assert evidence_reader.calls == 1
    with sqlite3.connect(admission_store.database_path) as connection:
        schema = connection.execute(
            """SELECT sql FROM sqlite_master
            WHERE name = 'live_enqueue_admissions'"""
        ).fetchone()[0]
        row = connection.execute("SELECT * FROM live_enqueue_admissions").fetchone()
    assert "live-enqueue-admission-key-1" not in schema
    assert all("live-enqueue-admission-key-1" not in str(value) for value in row)


def test_idempotency_subject_conflicts_and_mismatches_have_no_partial_row(
    tmp_path: Path,
) -> None:
    admission_service, admission_store, _reader, intake, *_tail, create = _service(
        tmp_path
    )
    assert _record(admission_service, intake, create).ok
    subject_retry = _record(
        admission_service,
        intake,
        create,
        idempotency_key="another-permanent-key",
    )
    assert subject_retry.error.error_code == "conflict"
    changed = create.model_copy(
        update={"worker_intake_admission_valid_until": "2026-08-27T12:00:44Z"}
    )
    conflict = _record(admission_service, intake, changed)
    assert conflict.error.error_code == "conflict"

    mismatch, mismatch_store, mismatch_reader, intake2, *_tail2, create2 = _service(
        tmp_path / "mismatch"
    )
    bad = create2.model_copy(
        update={
            "worker_intake_reference_fingerprint": (
                create2.worker_intake_reference_fingerprint.model_copy(
                    update={"value": "f" * 64}
                )
            )
        }
    )
    assert _record(mismatch, intake2, bad).error.error_code == "linkage_mismatch"
    assert mismatch_reader.calls == 1
    assert mismatch_store.list_owned(
        operator_id=intake2.operator_id,
        candidate_record_id=intake2.candidate_record_id,
    ) == ()
    assert admission_store.list_owned(
        operator_id=intake.operator_id,
        candidate_record_id=intake.candidate_record_id,
    )


def test_concurrent_duplicate_creates_yield_one_durable_record(tmp_path: Path) -> None:
    fixtures = _service(tmp_path)
    admission_service = fixtures[0]
    admission_store = fixtures[1]
    evidence_reader = fixtures[2]
    intake = fixtures[3]
    create = fixtures[7]
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(
            pool.map(lambda _index: _record(admission_service, intake, create), range(8))
        )
    assert all(result.ok for result in results)
    assert len({result.admission.record_fingerprint.value for result in results}) == 1
    listed = admission_store.list_owned(
        operator_id=intake.operator_id,
        candidate_record_id=intake.candidate_record_id,
    )
    assert len(listed) == 1
    assert evidence_reader.calls >= 1


def test_quota_record_bounds_and_corruption_fail_closed(tmp_path: Path) -> None:
    quota_service, *_tail, intake, _status, _queue, _queue_status, create = _service(
        tmp_path / "quota", quota=0
    )
    assert _record(quota_service, intake, create).error.error_code == (
        "quota_exceeded"
    )

    bounded, *_tail2, intake2, _status2, _queue2, _queue_status2, create2 = _service(
        tmp_path / "bounded", max_model_bytes=1
    )
    assert _record(bounded, intake2, create2).error.error_code == "record_too_large"

    clean, admission_store, _reader, intake3, *_tail3, create3 = _service(
        tmp_path / "corrupt"
    )
    created = _record(clean, intake3, create3)
    assert created.ok
    with sqlite3.connect(admission_store.database_path) as connection:
        connection.execute("UPDATE live_enqueue_admissions SET record_json = ?", ("{}",))
    assert clean.get(
        authenticated_operator_id=intake3.operator_id,
        permission_verified=True,
        admission_id=created.admission.admission_id,
        correlation_id="corrupt",
    ).error.error_code == "store_corrupt"


def test_store_is_append_only_and_has_no_effect_api() -> None:
    assert not any(
        hasattr(LiveEnqueueAdmissionStore, name)
        for name in (
            "update",
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
    assert "UPDATE live_enqueue_admissions" not in source
    assert "DELETE FROM live_enqueue_admissions" not in source


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
                "update",
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
        if path.parent.name == "installation_live_enqueue_admission" or path.name.startswith(
            "test_"
        ):
            continue
        source_text = path.read_text()
        if (
            "installation_live_enqueue_admission.service" in source_text
            or "LiveEnqueueAdmissionService" in source_text
        ):
            consumers.append(path)
    assert consumers == []
