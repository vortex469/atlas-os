from __future__ import annotations

import ast
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path

from app.controlled_worker_queue_claim_admission import service, store
from app.controlled_worker_queue_claim_admission.contract import (
    PERMISSION,
    ControlledWorkerQueueClaimAdmissionAuthorityContextV1,
    ControlledWorkerQueueClaimAdmissionValidationInputV1,
    build_admission,
    build_audit,
    build_collection,
    build_reservations,
    opaque_fingerprint,
)
from app.controlled_worker_queue_claim_admission.service import (
    create_controlled_worker_queue_claim_admission_service,
)
from app.controlled_worker_queue_claim_admission.store import (
    ControlledWorkerQueueClaimAdmissionStore,
)
from app.controlled_worker_queue_claim_admission.test_contract import _facts


class Reader:
    def __init__(self, value) -> None:
        self.value = value
        self.calls = 0

    def read_owned(self, **_kwargs):
        self.calls += 1
        return self.value


def _clock(second: int = 44):
    instant = datetime(2026, 8, 27, 12, 0, tzinfo=UTC) + timedelta(seconds=second)
    return lambda: instant


def _service(
    tmp_path: Path,
    *,
    activation_evidence=None,
    second: int = 44,
    quota: int = 16,
    max_model_bytes: int = 192 * 1024,
    enabled: bool = True,
):
    activation, activation_status, create = _facts(tmp_path)
    evidence_reader = Reader(
        activation_evidence
        if activation_evidence is not None
        else (activation, activation_status)
    )
    admission_store = ControlledWorkerQueueClaimAdmissionStore(
        tmp_path / "controlled-worker-queue-claim-admission.sqlite3",
        max_records_per_operator=quota,
        max_model_bytes=max_model_bytes,
    )
    admission_service = create_controlled_worker_queue_claim_admission_service(
        evidence_reader=evidence_reader,
        store=admission_store,
        clock=_clock(second),
        enabled=enabled,
    )
    return (
        admission_service,
        admission_store,
        evidence_reader,
        activation,
        activation_status,
        create,
    )


def _record(admission_service, activation, create, **changes):
    values = {
        "authenticated_operator_id": activation.operator_id,
        "permission_verified": True,
        "candidate_record_id": activation.candidate_record_id,
        "idempotency_key": "controlled-worker-queue-claim-admission-key-1",
        "correlation_id": "controlled-worker-queue-claim-admission-correlation-1",
    }
    values.update(changes)
    return admission_service.create(create, **values)


def test_create_get_list_and_restart_safe_owner_readback(tmp_path: Path) -> None:
    admission_service, admission_store, reader, activation, _status, create = _service(
        tmp_path
    )
    created = _record(admission_service, activation, create)
    assert created.ok
    assert created.record.admission_state == "readiness_gated"
    assert created.record.eligibility == "controlled_worker_queue_claim_admission_recorded"
    assert created.status.lifecycle == "active"
    assert reader.calls == 1
    assert not created.record.queue_claim_allowed
    assert not created.record.queue_lease_allowed
    assert not created.record.queue_ack_allowed
    assert not created.record.worker_start_allowed
    assert not created.record.agent_invocation_allowed
    assert not created.record.execution_start_allowed

    restarted = create_controlled_worker_queue_claim_admission_service(
        evidence_reader=Reader(None),
        store=ControlledWorkerQueueClaimAdmissionStore(admission_store.database_path),
        clock=_clock(80),
    )
    readback = restarted.get(
        authenticated_operator_id=activation.operator_id,
        permission_verified=True,
        admission_id=created.record.admission_id,
        correlation_id="readback",
    )
    assert readback.record == created.record
    assert readback.status.lifecycle == "expired"
    listed = restarted.list(
        authenticated_operator_id=activation.operator_id,
        permission_verified=True,
        candidate_record_id=activation.candidate_record_id,
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
        candidate_record_id=activation.candidate_record_id,
        correlation_id="foreign-list",
    )
    assert foreign.count == 0


def test_default_disabled_auth_permission_missing_and_redaction(
    tmp_path: Path,
) -> None:
    admission_service, admission_store, reader, activation, _status, create = _service(
        tmp_path, enabled=False
    )
    assert _record(admission_service, activation, create).error.error_code == (
        "installation_capability_unsupported"
    )
    assert _record(
        admission_service, activation, create, authenticated_operator_id=None
    ).error.error_code == "unauthenticated"
    assert _record(
        admission_service, activation, create, permission_verified=False
    ).error.error_code == "forbidden"
    assert reader.calls == 0
    assert admission_store.list_owned(
        operator_id=activation.operator_id,
        candidate_record_id=activation.candidate_record_id,
    ) == ()

    missing = _service(tmp_path / "missing", activation_evidence=None)
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
    admission_service, admission_store, reader, activation, _status, create = _service(
        tmp_path
    )
    created = _record(admission_service, activation, create)
    assert created.ok

    duplicate_service = create_controlled_worker_queue_claim_admission_service(
        evidence_reader=reader,
        store=ControlledWorkerQueueClaimAdmissionStore(admission_store.database_path),
        clock=_clock(80),
        enabled=True,
    )
    duplicate = _record(duplicate_service, activation, create)
    assert duplicate.ok
    assert duplicate.record == created.record
    assert duplicate.status.lifecycle == "expired"
    assert reader.calls == 1

    with sqlite3.connect(admission_store.database_path) as connection:
        rows = []
        for table in (
            "controlled_worker_queue_claim_admission_reservations",
            "controlled_worker_queue_claim_admissions",
            "controlled_worker_queue_claim_admission_attempts",
        ):
            rows.extend(connection.execute(f"SELECT * FROM {table}").fetchall())
        schema_rows = connection.execute(
            "SELECT sql FROM sqlite_master WHERE name LIKE "
            "'controlled_worker_queue_claim_admission%'"
        ).fetchall()
    persisted = "\n".join(str(value) for row in rows + schema_rows for value in row)
    assert "controlled-worker-queue-claim-admission-key-1" not in persisted
    assert "secret" not in persisted.lower()
    assert "token" not in persisted.lower()
    assert "worker.invalid" not in persisted.lower()
    assert "sh -c" not in persisted.lower()


def test_idempotency_subject_conflicts_and_prerequisite_validation(
    tmp_path: Path,
) -> None:
    admission_service, admission_store, reader, activation, _status, create = _service(
        tmp_path
    )
    assert _record(admission_service, activation, create).ok
    subject_retry = _record(
        admission_service,
        activation,
        create,
        idempotency_key="another-permanent-key",
    )
    assert subject_retry.error.error_code == "permanent_subject_reserved"
    changed = create.model_copy(
        update={"activation_evidence_valid_until": "2026-08-27T12:00:44Z"}
    )
    assert _record(admission_service, activation, changed).error.error_code == (
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
    assert reader.calls == 2
    assert admission_store.list_owned(
        operator_id=activation.operator_id,
        candidate_record_id=activation.candidate_record_id,
    )


def test_concurrent_duplicate_reservation_yields_one_durable_record(
    tmp_path: Path,
) -> None:
    admission_service, admission_store, _reader, activation, _status, create = _service(
        tmp_path
    )
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(
            pool.map(lambda _index: _record(admission_service, activation, create), range(8))
        )
    assert any(result.ok for result in results)
    assert all(
        result.ok or result.error.error_code == "append_indeterminate"
        for result in results
    )
    listed = admission_store.list_owned(
        operator_id=activation.operator_id,
        candidate_record_id=activation.candidate_record_id,
    )
    assert len(listed) == 1
    assert {
        result.record.admission_record_fingerprint.value
        for result in results
        if result.ok
    } == {listed[0].admission_record_fingerprint.value}


def test_indeterminate_reservation_is_terminal_across_restart(tmp_path: Path) -> None:
    _service_obj, admission_store, _reader, activation, activation_status, create = (
        _service(tmp_path)
    )
    validation = ControlledWorkerQueueClaimAdmissionValidationInputV1(
        operator_id=activation.operator_id,
        authority=ControlledWorkerQueueClaimAdmissionAuthorityContextV1(
            authenticated_operator_id=activation.operator_id,
            permission=PERMISSION,
            request_received_at="2026-08-27T12:00:44Z",
        ),
        candidate_record_id=activation.candidate_record_id,
        create=create,
        worker_binding_activation_evidence=activation,
        worker_binding_activation_evidence_status=activation_status,
        idempotency_key="controlled-worker-queue-claim-admission-key-1",
    )
    record = build_admission(validation)
    idempotency, reservation = build_reservations(validation, record)
    audit = build_audit(
        record,
        event="controlled_worker_queue_claim_admission_indeterminate",
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
            activation_evidence_valid_until=create.activation_evidence_valid_until,
            force_indeterminate=True,
        )
    except store.ControlledWorkerQueueClaimAdmissionStoreError as error:
        assert error.code == "append_indeterminate"
    retry = create_controlled_worker_queue_claim_admission_service(
        evidence_reader=Reader((activation, activation_status)),
        store=ControlledWorkerQueueClaimAdmissionStore(admission_store.database_path),
        clock=_clock(),
        enabled=True,
    )
    result = _record(retry, activation, create)
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
        hasattr(ControlledWorkerQueueClaimAdmissionStore, name)
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
    assert "DELETE FROM controlled_worker_queue_claim" not in source
    assert "UPDATE controlled_worker_queue_claim" not in source

    corrupt = _service(tmp_path / "corrupt")
    created = _record(corrupt[0], corrupt[3], corrupt[5])
    assert created.ok
    with sqlite3.connect(corrupt[1].database_path) as connection:
        connection.execute(
            "UPDATE controlled_worker_queue_claim_admissions SET record_json = ?",
            ("{}",),
        )
    assert corrupt[0].get(
        authenticated_operator_id=corrupt[3].operator_id,
        permission_verified=True,
        admission_id=created.record.admission_id,
        correlation_id="corrupt",
    ).error.error_code == "store_corrupt"

    lineage = _service(tmp_path / "lineage-corrupt")
    lineage_created = _record(lineage[0], lineage[3], lineage[5])
    assert lineage_created.ok
    with sqlite3.connect(lineage[1].database_path) as connection:
        connection.execute(
            "UPDATE controlled_worker_queue_claim_admission_reservations "
            "SET activation_evidence_valid_until = ?",
            ("2026-08-27T12:00:40Z",),
        )
    assert lineage[0].get(
        authenticated_operator_id=lineage[3].operator_id,
        permission_verified=True,
        admission_id=lineage_created.record.admission_id,
        correlation_id="lineage-corrupt",
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
        if path.parent.name == "controlled_worker_queue_claim_admission":
            continue
        if path.name.startswith("test_"):
            continue
        source_text = path.read_text(encoding="utf-8")
        if (
            "controlled_worker_queue_claim_admission.service" in source_text
            or "ControlledWorkerQueueClaimAdmissionService" in source_text
        ):
            consumers.append(path)
    assert consumers == []


def test_agent_and_execution_worker_do_not_consume_queue_claim_admissions() -> None:
    root = Path(__file__).resolve().parents[4]
    forbidden_markers = (
        "controlled_worker_queue_claim_admission",
        "ControlledWorkerQueueClaimAdmission",
        "controlledWorkerQueueClaimAdmission",
        "controlled-worker-queue-claim-admissions",
        "controlled_worker_queue_claim_admission_recorded",
    )
    consumers = []
    for directory in (
        root / "services" / "atlas-agent",
        root / "services" / "atlas-execution-worker",
    ):
        if not directory.exists():
            continue
        for path in directory.rglob("*"):
            if path.is_dir() or path.suffix not in {".py", ".ts", ".tsx", ".md"}:
                continue
            if path.name.startswith("test_") or "/tests/" in path.as_posix():
                continue
            source_text = path.read_text(encoding="utf-8")
            if any(marker in source_text for marker in forbidden_markers):
                consumers.append(path.relative_to(root).as_posix())
    assert consumers == []
