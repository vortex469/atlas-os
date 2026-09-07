from __future__ import annotations

import ast
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path

from app.controlled_worker_queue_claim_lease_acknowledgement import (
    service,
    store,
)
from app.controlled_worker_queue_claim_lease_acknowledgement.contract import (
    PERMISSION,
    ControlledWorkerQueueClaimLeaseAcknowledgementAuthorityContextV1,
    ControlledWorkerQueueClaimLeaseAcknowledgementValidationInputV1,
    build_audit,
    build_collection,
    build_receipt,
    build_reservations,
    opaque_fingerprint,
)
from app.controlled_worker_queue_claim_lease_acknowledgement.service import (
    create_controlled_worker_queue_claim_lease_acknowledgement_service,
)
from app.controlled_worker_queue_claim_lease_acknowledgement.store import (
    ControlledWorkerQueueClaimLeaseAcknowledgementStore,
)
from app.controlled_worker_queue_claim_lease_acknowledgement.test_contract import (
    _facts,
)


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
    admission_evidence=None,
    second: int = 44,
    quota: int = 16,
    max_model_bytes: int = 192 * 1024,
    enabled: bool = True,
):
    admission, admission_status, adapter_receipt, create = _facts(tmp_path)
    admission_reader = Reader(
        admission_evidence
        if admission_evidence is not None
        else (admission, admission_status)
    )
    adapter_reader = Reader(adapter_receipt)
    receipt_store = ControlledWorkerQueueClaimLeaseAcknowledgementStore(
        tmp_path / "controlled-worker-queue-claim-lease-ack-admission.sqlite3",
        max_records_per_operator=quota,
        max_model_bytes=max_model_bytes,
    )
    receipt_service = (
        create_controlled_worker_queue_claim_lease_acknowledgement_service(
            admission_reader=admission_reader,
            adapter_receipt_reader=adapter_reader,
            store=receipt_store,
            clock=_clock(second),
            enabled=enabled,
        )
    )
    return (
        receipt_service,
        receipt_store,
        admission_reader,
        adapter_reader,
        admission,
        admission_status,
        adapter_receipt,
        create,
    )


def _record(receipt_service, admission, create, **changes):
    values = {
        "authenticated_operator_id": admission.operator_id,
        "permission_verified": True,
        "candidate_record_id": admission.candidate_record_id,
        "idempotency_key": "controlled-worker-queue-claim-lease-ack-admission-key-1",
        "correlation_id": "controlled-worker-queue-claim-lease-ack-correlation-1",
    }
    values.update(changes)
    return receipt_service.create(create, **values)


def test_create_get_list_and_restart_safe_owner_readback(tmp_path: Path) -> None:
    (
        receipt_service,
        receipt_store,
        reader,
        adapter_reader,
        admission,
        _status,
        _adapter,
        create,
    ) = _service(tmp_path)
    created = _record(receipt_service, admission, create)
    assert created.ok
    assert created.record.receipt_state == "recorded"
    assert (
        created.record.eligibility
        == "controlled_worker_queue_claim_lease_acknowledgement_recorded"
    )
    assert created.status.lifecycle == "active"
    assert reader.calls == 3
    assert adapter_reader.calls == 1
    assert created.record.controlled_queue_claim_recorded
    assert created.record.controlled_queue_lease_recorded
    assert created.record.controlled_queue_acknowledgement_recorded
    assert not created.record.worker_start_allowed
    assert not created.record.agent_invocation_allowed
    assert not created.record.execution_start_allowed

    restarted = create_controlled_worker_queue_claim_lease_acknowledgement_service(
        admission_reader=Reader(None),
        adapter_receipt_reader=Reader(None),
        store=ControlledWorkerQueueClaimLeaseAcknowledgementStore(
            receipt_store.database_path
        ),
        clock=_clock(80),
    )
    readback = restarted.get(
        authenticated_operator_id=admission.operator_id,
        permission_verified=True,
        admission_id=created.record.admission_id,
        correlation_id="readback",
    )
    assert readback.record == created.record
    assert readback.status.lifecycle == "expired"
    listed = restarted.list(
        authenticated_operator_id=admission.operator_id,
        permission_verified=True,
        candidate_record_id=admission.candidate_record_id,
        correlation_id="list",
    )
    assert tuple(item.admission_id for item in listed.items) == (
        created.record.admission_id,
    )
    assert (
        restarted.get(
            authenticated_operator_id="operator-b",
            permission_verified=True,
            admission_id=created.record.admission_id,
            correlation_id="foreign",
        ).error.error_code
        == "not_found"
    )


def test_default_disabled_auth_permission_missing_and_redaction(
    tmp_path: Path,
) -> None:
    (
        receipt_service,
        receipt_store,
        reader,
        adapter_reader,
        admission,
        _status,
        _adapter,
        create,
    ) = _service(tmp_path, enabled=False)
    assert _record(receipt_service, admission, create).error.error_code == (
        "installation_capability_unsupported"
    )
    assert (
        _record(
            receipt_service, admission, create, authenticated_operator_id=None
        ).error.error_code
        == "unauthenticated"
    )
    assert (
        _record(
            receipt_service, admission, create, permission_verified=False
        ).error.error_code
        == "forbidden"
    )
    assert reader.calls == 0
    assert adapter_reader.calls == 0
    assert (
        receipt_store.list_owned(
            operator_id=admission.operator_id,
            candidate_record_id=admission.candidate_record_id,
        )
        == ()
    )

    missing = _service(tmp_path / "missing", admission_evidence=None)
    missing[2].value = None
    result = _record(
        missing[0],
        missing[4],
        missing[7],
        correlation_id="secret/internal/path/token",
    )
    assert result.error.error_code == "not_found"
    assert "secret/internal/path/token" not in result.model_dump_json()


def test_exact_duplicate_zero_reader_and_secret_free_persistence(
    tmp_path: Path,
) -> None:
    (
        receipt_service,
        receipt_store,
        reader,
        adapter_reader,
        admission,
        _status,
        _adapter,
        create,
    ) = _service(tmp_path)
    created = _record(receipt_service, admission, create)
    assert created.ok

    duplicate_service = (
        create_controlled_worker_queue_claim_lease_acknowledgement_service(
            admission_reader=reader,
            adapter_receipt_reader=adapter_reader,
            store=ControlledWorkerQueueClaimLeaseAcknowledgementStore(
                receipt_store.database_path
            ),
            clock=_clock(80),
            enabled=True,
        )
    )
    duplicate = _record(duplicate_service, admission, create)
    assert duplicate.ok
    assert duplicate.record == created.record
    assert duplicate.status.lifecycle == "expired"
    assert reader.calls == 3
    assert adapter_reader.calls == 1

    with sqlite3.connect(receipt_store.database_path) as connection:
        rows = []
        for table in (
            "cwqcla_receipt_reservations",
            "cwqcla_receipts",
            "cwqcla_receipt_attempts",
        ):
            rows.extend(connection.execute(f"SELECT * FROM {table}").fetchall())
        schema_rows = connection.execute(
            "SELECT sql FROM sqlite_master WHERE name LIKE 'cwqcla_receipt%'"
        ).fetchall()
    persisted = "\n".join(str(value) for row in rows + schema_rows for value in row)
    assert "controlled-worker-queue-claim-lease-ack-admission-key-1" not in persisted
    assert "secret/internal/path/token" not in persisted
    assert "worker.invalid" not in persisted.lower()
    assert "sh -c" not in persisted.lower()


def test_idempotency_subject_conflicts_and_admission_validation(
    tmp_path: Path,
) -> None:
    (
        receipt_service,
        receipt_store,
        reader,
        _adapter_reader,
        admission,
        _status,
        _adapter,
        create,
    ) = _service(tmp_path)
    assert _record(receipt_service, admission, create).ok
    subject_retry = _record(
        receipt_service,
        admission,
        create,
        idempotency_key="another-permanent-admission-key",
    )
    assert subject_retry.error.error_code == "permanent_subject_reserved"
    changed = create.model_copy(
        update={"admission_valid_until": "2026-08-27T12:00:44Z"}
    )
    assert _record(receipt_service, admission, changed).error.error_code == (
        "idempotency_conflict"
    )

    mismatch = _service(tmp_path / "mismatch")
    bad = mismatch[7].model_copy(
        update={
            "worker_subject_fingerprint": mismatch[
                7
            ].worker_subject_fingerprint.model_copy(update={"value": "f" * 64})
        }
    )
    assert _record(mismatch[0], mismatch[4], bad).error.error_code == (
        "fingerprint_mismatch"
    )
    assert (
        mismatch[1].list_owned(
            operator_id=mismatch[4].operator_id,
            candidate_record_id=mismatch[4].candidate_record_id,
        )
        == ()
    )
    assert reader.calls == 4
    assert receipt_store.list_owned(
        operator_id=admission.operator_id,
        candidate_record_id=admission.candidate_record_id,
    )


def test_concurrent_duplicate_reservation_yields_one_durable_record(
    tmp_path: Path,
) -> None:
    (
        receipt_service,
        receipt_store,
        _reader,
        _adapter_reader,
        admission,
        _status,
        _adapter,
        create,
    ) = _service(tmp_path)
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(
            pool.map(
                lambda _index: _record(receipt_service, admission, create),
                range(8),
            )
        )
    assert any(result.ok for result in results)
    assert all(
        result.ok or result.error.error_code == "append_indeterminate"
        for result in results
    )
    listed = receipt_store.list_owned(
        operator_id=admission.operator_id,
        candidate_record_id=admission.candidate_record_id,
    )
    assert len(listed) == 1
    assert {
        result.record.receipt_record_fingerprint.value
        for result in results
        if result.ok
    } == {listed[0].receipt_record_fingerprint.value}


def test_indeterminate_reservation_is_terminal_across_restart(tmp_path: Path) -> None:
    (
        _service_obj,
        receipt_store,
        _reader,
        _adapter_reader,
        admission,
        admission_status,
        adapter_receipt,
        create,
    ) = _service(tmp_path)
    validation = ControlledWorkerQueueClaimLeaseAcknowledgementValidationInputV1(
        operator_id=admission.operator_id,
        authority=ControlledWorkerQueueClaimLeaseAcknowledgementAuthorityContextV1(
            authenticated_operator_id=admission.operator_id,
            permission=PERMISSION,
            request_received_at="2026-08-27T12:00:44Z",
        ),
        candidate_record_id=admission.candidate_record_id,
        create=create,
        controlled_worker_queue_claim_lease_acknowledgement_admission=admission,
        controlled_worker_queue_claim_lease_acknowledgement_admission_status=(
            admission_status
        ),
        adapter_receipt=adapter_receipt,
        idempotency_key="controlled-worker-queue-claim-lease-ack-admission-key-1",
    )
    record = build_receipt(validation)
    idempotency, reservation = build_reservations(validation, record)
    audit = build_audit(
        record,
        event="controlled_worker_queue_claim_lease_acknowledgement_indeterminate",
        outcome="indeterminate",
        correlation_fingerprint=opaque_fingerprint("atlas:test:v1", "indeterminate"),
        occurred_at=record.recorded_at,
    )
    try:
        receipt_store.append(
            record=record,
            idempotency_reservation=idempotency,
            subject_reservation=reservation,
            audit_evidence=audit,
            admission_valid_until=create.admission_valid_until,
            force_indeterminate=True,
        )
    except store.ControlledWorkerQueueClaimLeaseAcknowledgementStoreError as error:
        assert error.code == "append_indeterminate"
    retry = create_controlled_worker_queue_claim_lease_acknowledgement_service(
        admission_reader=Reader((admission, admission_status)),
        adapter_receipt_reader=Reader(adapter_receipt),
        store=ControlledWorkerQueueClaimLeaseAcknowledgementStore(
            receipt_store.database_path
        ),
        clock=_clock(),
        enabled=True,
    )
    result = _record(retry, admission, create)
    assert result.error.error_code == "append_indeterminate"
    assert result.outcome == "indeterminate"


def test_quota_bounds_corruption_and_append_only_surface(tmp_path: Path) -> None:
    quota = _service(tmp_path / "quota", quota=0)
    assert _record(quota[0], quota[4], quota[7]).error.error_code == "quota_exceeded"

    bounded = _service(tmp_path / "bounded", max_model_bytes=1)
    assert _record(bounded[0], bounded[4], bounded[7]).error.error_code == (
        "record_too_large"
    )

    clean = _service(tmp_path / "surface")
    assert _record(clean[0], clean[4], clean[7]).ok
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
        hasattr(ControlledWorkerQueueClaimLeaseAcknowledgementStore, name)
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
    assert "DELETE FROM cwqcla_receipt" not in source
    assert "UPDATE cwqcla_receipt" not in source

    corrupt = _service(tmp_path / "corrupt")
    created = _record(corrupt[0], corrupt[4], corrupt[7])
    assert created.ok
    with sqlite3.connect(corrupt[1].database_path) as connection:
        connection.execute("UPDATE cwqcla_receipts SET record_json = ?", ("{}",))
    assert (
        corrupt[0]
        .get(
            authenticated_operator_id=corrupt[4].operator_id,
            permission_verified=True,
            admission_id=created.record.admission_id,
            correlation_id="corrupt",
        )
        .error.error_code
        == "store_corrupt"
    )

    lineage = _service(tmp_path / "lineage-corrupt")
    lineage_created = _record(lineage[0], lineage[4], lineage[7])
    assert lineage_created.ok
    with sqlite3.connect(lineage[1].database_path) as connection:
        connection.execute(
            "UPDATE cwqcla_receipt_reservations SET admission_valid_until = ?",
            ("2026-08-27T12:00:40Z",),
        )
    assert (
        lineage[0]
        .get(
            authenticated_operator_id=lineage[4].operator_id,
            permission_verified=True,
            admission_id=lineage_created.record.admission_id,
            correlation_id="lineage-corrupt",
        )
        .error.error_code
        == "store_corrupt"
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
        "transport",
    }
    for module in (service, store):
        tree = ast.parse(Path(module.__file__).read_text(encoding="utf-8"))
        imported = {
            name
            for node in ast.walk(tree)
            if isinstance(node, ast.Import | ast.ImportFrom)
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
            isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)
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
        if path.parent.name == ("controlled_worker_queue_claim_lease_acknowledgement"):
            continue
        if path.name.startswith("test_"):
            continue
        source_text = path.read_text(encoding="utf-8")
        if (
            "controlled_worker_queue_claim_lease_acknowledgement.service" in source_text
            or "ControlledWorkerQueueClaimLeaseAcknowledgementService" in source_text
        ):
            consumers.append(path)
    assert consumers == []


def test_agent_and_execution_worker_do_not_consume_v051_receipts() -> None:
    root = Path(__file__).resolve().parents[4]
    forbidden_markers = (
        "controlled_worker_queue_claim_lease_acknowledgement",
        "ControlledWorkerQueueClaimLeaseAcknowledgement",
        "controlled-worker-queue-claim-lease-acknowledgements",
        "controlled_worker_queue_claim_lease_acknowledgement_recorded",
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


def _append_values(fixture, *, terminal=False):
    validation = ControlledWorkerQueueClaimLeaseAcknowledgementValidationInputV1(
        operator_id=fixture[4].operator_id,
        authority=ControlledWorkerQueueClaimLeaseAcknowledgementAuthorityContextV1(
            authenticated_operator_id=fixture[4].operator_id,
            permission=PERMISSION,
            request_received_at="2026-08-27T12:00:44Z",
        ),
        candidate_record_id=fixture[4].candidate_record_id,
        create=fixture[7],
        controlled_worker_queue_claim_lease_acknowledgement_admission=fixture[4],
        controlled_worker_queue_claim_lease_acknowledgement_admission_status=fixture[5],
        adapter_receipt=fixture[6],
        idempotency_key="controlled-worker-queue-claim-lease-ack-admission-key-1",
    )
    record = build_receipt(validation)
    idem, subject = build_reservations(validation, record)
    return {
        "record": record,
        "idempotency_reservation": idem,
        "subject_reservation": subject,
        "audit_evidence": build_audit(
            record,
            event=(
                "controlled_worker_queue_claim_lease_acknowledgement_indeterminate"
                if terminal
                else "controlled_worker_queue_claim_lease_acknowledgement_recorded"
            ),
            outcome="indeterminate" if terminal else "recorded",
            correlation_fingerprint=opaque_fingerprint("atlas:test:v1", "audit"),
            occurred_at=record.recorded_at,
        ),
        "admission_valid_until": fixture[7].admission_valid_until,
        "force_indeterminate": terminal,
    }


def test_write_lock_revalidates_disappeared_or_changed_prerequisite(tmp_path: Path):
    import pytest

    for change in ("missing", "fingerprint", "expiry"):
        fixture = _service(tmp_path / change)
        reader = fixture[2]
        original = reader.read_owned

        def changed(
            *,
            original=original,
            reader=reader,
            change=change,
            fixture=fixture,
            **kwargs,
        ):
            value = original(**kwargs)
            if reader.calls == 2:
                if change == "missing":
                    return None
                if change == "expiry":
                    fixture[0]._clock = _clock(80)
                else:
                    return value[0], value[1].model_copy(
                        update={
                            "status_fingerprint": opaque_fingerprint(
                                "atlas:test:v1", "drift"
                            )
                        }
                    )
            return value

        reader.read_owned = changed
        result = _record(fixture[0], fixture[4], fixture[7])
        assert not result.ok
        assert reader.calls == 2
        with sqlite3.connect(fixture[1].database_path) as connection:
            assert (
                connection.execute(
                    "SELECT COUNT(*) FROM cwqcla_receipt_reservations"
                ).fetchone()[0]
                == 0
            )
        # No prerequisite failure may leave a success record behind.
        with pytest.raises(
            store.ControlledWorkerQueueClaimLeaseAcknowledgementStoreError,
            match="not_found",
        ):
            fixture[1].get(
                operator_id=fixture[4].operator_id, admission_id=fixture[4].admission_id
            )


def test_forged_append_inputs_do_not_reserve_or_persist(tmp_path: Path):
    import pytest

    fixture = _service(tmp_path)
    values = _append_values(fixture)
    for field, change in (
        ("record", {"worker_start_allowed": True}),
        ("idempotency_reservation", {"operator_id": "other-owner"}),
        ("audit_evidence", {"outcome": "indeterminate"}),
    ):
        forged = {**values, field: values[field].model_copy(update=change)}
        with pytest.raises(
            store.ControlledWorkerQueueClaimLeaseAcknowledgementStoreError,
            match="store_corrupt",
        ):
            fixture[1].append(**forged)
    with sqlite3.connect(fixture[1].database_path) as connection:
        assert (
            connection.execute(
                "SELECT COUNT(*) FROM cwqcla_receipt_reservations"
            ).fetchone()[0]
            == 0
        )
    assert fixture[1].append(**values)[1]


def test_corruption_cannot_hide_from_owner_lookup_or_restart(tmp_path: Path):
    import pytest

    corruptions = (
        "UPDATE cwqcla_receipt_reservations SET operator_id = 'other-owner'",
        "DELETE FROM cwqcla_receipt_reservations",
        "UPDATE cwqcla_receipts SET audit_json = '{}'",
        "UPDATE cwqcla_receipt_reservations SET reservation_json = '{}'",
        "UPDATE cwqcla_receipts SET record_json = zeroblob(200000)",
        "DROP TABLE cwqcla_receipt_attempts",
        "UPDATE cwqcla_receipt_reservations SET admission_valid_until = 'garbage'",
    )
    for index, statement in enumerate(corruptions):
        fixture = _service(tmp_path / str(index))
        assert _record(fixture[0], fixture[4], fixture[7]).ok
        with sqlite3.connect(fixture[1].database_path) as connection:
            connection.execute(statement)
        result = _record(
            fixture[0],
            fixture[4],
            fixture[7],
            idempotency_key="different-idempotency-key",
        )
        assert result.error.error_code == "store_corrupt"
        listed = fixture[0].list(
            authenticated_operator_id=fixture[4].operator_id,
            permission_verified=True,
            candidate_record_id=fixture[4].candidate_record_id,
            correlation_id="corrupt",
        )
        assert listed[0].error.error_code == "store_corrupt"
        with pytest.raises(
            store.ControlledWorkerQueueClaimLeaseAcknowledgementStoreError,
            match="store_corrupt",
        ):
            ControlledWorkerQueueClaimLeaseAcknowledgementStore(
                fixture[1].database_path
            )


def test_terminal_attempts_are_bounded_and_corruption_closes(tmp_path: Path):
    import pytest

    fixture = _service(tmp_path)
    values = _append_values(fixture, terminal=True)
    with pytest.raises(
        store.ControlledWorkerQueueClaimLeaseAcknowledgementStoreError,
        match="append_indeterminate",
    ):
        fixture[1].append(**values)
    for index in range(8):
        audit = build_audit(
            values["record"],
            event="controlled_worker_queue_claim_lease_acknowledgement_indeterminate",
            outcome="indeterminate",
            correlation_fingerprint=opaque_fingerprint("atlas:test:v1", str(index)),
            occurred_at=values["record"].recorded_at,
        )
        fixture[1].mark_indeterminate(
            operator_id=fixture[4].operator_id,
            admission_id=fixture[4].admission_id,
            audit_evidence=audit,
        )
    with sqlite3.connect(fixture[1].database_path) as connection:
        assert (
            connection.execute(
                "SELECT COUNT(*) FROM cwqcla_receipt_attempts"
            ).fetchone()[0]
            == 1
        )
        connection.execute("UPDATE cwqcla_receipt_attempts SET audit_json = '{}' ")
    assert (
        _record(fixture[0], fixture[4], fixture[7]).error.error_code == "store_corrupt"
    )


def test_append_failure_keeps_permanent_reservation(tmp_path: Path, monkeypatch):
    fixture = _service(tmp_path)

    def uncertain(**kwargs):
        raise OSError("secret/internal/database/path")

    monkeypatch.setattr(fixture[1], "_append_record", uncertain)
    result = _record(fixture[0], fixture[4], fixture[7])
    assert result.outcome == "indeterminate"
    assert "secret/internal" not in result.model_dump_json()
    fixture[0]._store = ControlledWorkerQueueClaimLeaseAcknowledgementStore(
        fixture[1].database_path
    )
    assert _record(fixture[0], fixture[4], fixture[7]).outcome == "indeterminate"
    assert (
        _record(
            fixture[0], fixture[4], fixture[7], idempotency_key="new-idempotency-key"
        ).error.error_code
        == "permanent_subject_reserved"
    )
    assert fixture[2].calls == 3


def test_separate_store_instances_serialize_competing_subject_keys(tmp_path: Path):
    fixture = _service(tmp_path)
    services = [
        create_controlled_worker_queue_claim_lease_acknowledgement_service(
            admission_reader=Reader((fixture[4], fixture[5])),
            adapter_receipt_reader=Reader(fixture[6]),
            store=ControlledWorkerQueueClaimLeaseAcknowledgementStore(
                fixture[1].database_path
            ),
            clock=_clock(),
            enabled=True,
        )
        for _ in range(4)
    ]
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(
            pool.map(
                lambda index: _record(
                    services[index],
                    fixture[4],
                    fixture[7],
                    idempotency_key=f"competing-subject-key-{index}",
                ),
                range(4),
            )
        )
    assert sum(result.ok for result in results) == 1
    assert all(
        result.ok or result.error.error_code == "permanent_subject_reserved"
        for result in results
    )
    with sqlite3.connect(fixture[1].database_path) as connection:
        assert (
            connection.execute(
                "SELECT COUNT(*) FROM cwqcla_receipt_reservations"
            ).fetchone()[0]
            == 1
        )
        assert (
            connection.execute("SELECT COUNT(*) FROM cwqcla_receipts").fetchone()[0]
            == 1
        )


def test_global_quota_and_configuration_caps(tmp_path: Path):
    import pytest

    fixture = _service(tmp_path)
    fixture[0]._store = ControlledWorkerQueueClaimLeaseAcknowledgementStore(
        tmp_path / "zero.sqlite3", max_total_records=0
    )
    assert (
        _record(fixture[0], fixture[4], fixture[7]).error.error_code == "quota_exceeded"
    )
    for options in (
        {"max_total_records": 257},
        {"max_records_per_operator": 17},
        {"max_model_bytes": 192 * 1024 + 1},
        {"max_total_records": -1},
        {"max_total_records": True},
    ):
        with pytest.raises(
            store.ControlledWorkerQueueClaimLeaseAcknowledgementStoreError,
            match="invalid_request",
        ):
            ControlledWorkerQueueClaimLeaseAcknowledgementStore(
                tmp_path / "invalid.sqlite3", **options
            )


def test_durable_prerequisite_reader_is_exact_owner_scoped(tmp_path: Path):
    from app.controlled_worker_queue_claim_lease_acknowledgement.readers import (
        ControlledWorkerQueueClaimLeaseAcknowledgementAdmissionStoreReader,
    )
    from app.controlled_worker_queue_claim_lease_acknowledgement_admission.test_service_store import (
        _record as record_v051,
    )
    from app.controlled_worker_queue_claim_lease_acknowledgement_admission.test_service_store import (
        _service as service_v051,
    )

    upstream = service_v051(tmp_path)
    created = record_v051(upstream[0], upstream[3], upstream[5])
    assert created.ok
    reader = ControlledWorkerQueueClaimLeaseAcknowledgementAdmissionStoreReader(
        store=upstream[1], clock=_clock()
    )
    args = {
        "operator_id": created.record.operator_id,
        "candidate_record_id": created.record.candidate_record_id,
        "admission_id": created.record.admission_id,
        "admission_valid_until": created.record.valid_until,
    }
    assert reader.read_owned(**args) == (created.record, created.status)
    for field, value in (
        ("operator_id", "other-owner"),
        ("candidate_record_id", "00000000-0000-4000-8000-000000000000"),
        ("admission_valid_until", "2026-08-27T12:00:43Z"),
    ):
        assert reader.read_owned(**{**args, field: value}) is None
    reader._clock = _clock(80)
    assert reader.read_owned(**args) is None


def test_duplicate_with_different_audit_returns_original(tmp_path: Path):
    fixture = _service(tmp_path)
    first = _append_values(fixture)
    original, created = fixture[1].append(**first)
    assert created
    later = {
        **first,
        "audit_evidence": build_audit(
            original,
            event="controlled_worker_queue_claim_lease_acknowledgement_recorded",
            outcome="recorded",
            correlation_fingerprint=opaque_fingerprint("atlas:test:v1", "later"),
            occurred_at=original.recorded_at,
        ),
    }
    stored, created = fixture[1].append(**later)
    assert not created
    assert stored == original
    with sqlite3.connect(fixture[1].database_path) as connection:
        assert (
            connection.execute("SELECT audit_json FROM cwqcla_receipts").fetchone()[0]
            == first["audit_evidence"].model_dump_json()
        )


def test_expiry_after_reservation_is_terminal(tmp_path: Path):
    fixture = _service(tmp_path)
    reader = fixture[2]
    original = reader.read_owned

    def expires(**kwargs):
        value = original(**kwargs)
        if reader.calls == 3:
            fixture[0]._clock = _clock(80)
        return value

    reader.read_owned = expires
    result = _record(fixture[0], fixture[4], fixture[7])
    assert result.outcome == "indeterminate"
    with sqlite3.connect(fixture[1].database_path) as connection:
        assert (
            connection.execute(
                "SELECT COUNT(*) FROM cwqcla_receipt_reservations"
            ).fetchone()[0]
            == 1
        )
        assert (
            connection.execute("SELECT COUNT(*) FROM cwqcla_receipts").fetchone()[0]
            == 0
        )
    assert _record(fixture[0], fixture[4], fixture[7]).outcome == "indeterminate"
    assert reader.calls == 3


def test_authority_flags_require_exact_booleans(tmp_path: Path):
    fixture = _service(tmp_path)
    for value in (1, "true", object()):
        assert (
            _record(
                fixture[0], fixture[4], fixture[7], permission_verified=value
            ).error.error_code
            == "forbidden"
        )
    assert fixture[2].calls == 0
    disabled = create_controlled_worker_queue_claim_lease_acknowledgement_service(
        admission_reader=fixture[2],
        adapter_receipt_reader=fixture[3],
        store=fixture[1],
        clock=_clock(),
        enabled="true",
    )
    assert (
        _record(disabled, fixture[4], fixture[7]).error.error_code
        == "installation_capability_unsupported"
    )
    assert fixture[2].calls == 0
