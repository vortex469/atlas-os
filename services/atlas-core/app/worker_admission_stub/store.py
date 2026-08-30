"""Append-only durable store for v0.38 worker-admission evidence."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from .contract import (
    MAX_MODEL_BYTES,
    WorkerAdmissionStubAuditEvidenceV1,
    WorkerAdmissionStubReservationV1,
    WorkerAdmissionStubV1,
    opaque_fingerprint,
)

MAX_RECORDS_PER_OPERATOR = 16


class WorkerAdmissionStubStoreError(RuntimeError):
    """Closed storage failure with no database or record disclosure."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


class WorkerAdmissionStubStore:
    """SQLite append-only evidence with permanent key/subject reservations."""

    def __init__(
        self,
        database_path: str | Path,
        *,
        max_records_per_operator: int = MAX_RECORDS_PER_OPERATOR,
    ) -> None:
        self.database_path = Path(database_path)
        self.max_records_per_operator = max_records_per_operator
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path, timeout=5, isolation_level=None)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self) -> None:
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with self._connect() as connection:
                connection.execute("PRAGMA journal_mode=WAL")
                connection.execute("PRAGMA synchronous=FULL")
                connection.execute(
                    """
                    CREATE TABLE IF NOT EXISTS worker_admission_stubs (
                        operator_id TEXT NOT NULL,
                        stub_id TEXT NOT NULL,
                        candidate_record_id TEXT NOT NULL,
                        runner_binding_plan_valid_until TEXT NOT NULL,
                        idempotency_key_fingerprint TEXT NOT NULL,
                        runner_binding_plan_fingerprint TEXT NOT NULL,
                        worker_reference_fingerprint TEXT NOT NULL,
                        worker_admission_intent_fingerprint TEXT NOT NULL,
                        inherited_limits_fingerprint TEXT NOT NULL,
                        subject_fingerprint TEXT NOT NULL,
                        request_fingerprint TEXT NOT NULL,
                        stub_fingerprint TEXT NOT NULL,
                        recorded_at TEXT NOT NULL,
                        stub_json TEXT NOT NULL,
                        reservation_json TEXT NOT NULL,
                        audit_json TEXT NOT NULL,
                        PRIMARY KEY (operator_id, stub_id),
                        UNIQUE (operator_id, idempotency_key_fingerprint),
                        UNIQUE (operator_id, subject_fingerprint),
                        UNIQUE (operator_id, stub_fingerprint)
                    )
                    """
                )
        except sqlite3.Error as error:
            raise WorkerAdmissionStubStoreError("unavailable") from error

    def resolve_idempotency(
        self,
        *,
        operator_id: str,
        idempotency_key_fingerprint: str,
        runner_binding_plan_valid_until: str,
    ) -> WorkerAdmissionStubV1 | None:
        try:
            with self._connect() as connection:
                row = connection.execute(
                    """SELECT * FROM worker_admission_stubs
                    WHERE operator_id = ? AND idempotency_key_fingerprint = ?""",
                    (operator_id, idempotency_key_fingerprint),
                ).fetchone()
        except sqlite3.Error as error:
            raise WorkerAdmissionStubStoreError("unavailable") from error
        if row is None:
            return None
        if row["runner_binding_plan_valid_until"] != runner_binding_plan_valid_until:
            raise WorkerAdmissionStubStoreError("conflict")
        return self._decode(row, operator_id=operator_id)

    def append(
        self,
        *,
        stub: WorkerAdmissionStubV1,
        reservation: WorkerAdmissionStubReservationV1,
        audit_evidence: WorkerAdmissionStubAuditEvidenceV1,
        runner_binding_plan_valid_until: str,
    ) -> tuple[WorkerAdmissionStubV1, bool]:
        stub_json = stub.model_dump_json()
        reservation_json = reservation.model_dump_json()
        audit_json = audit_evidence.model_dump_json()
        if max(len(value.encode()) for value in (stub_json, reservation_json, audit_json)) > MAX_MODEL_BYTES:
            raise WorkerAdmissionStubStoreError("unavailable")
        try:
            with self._connect() as connection:
                connection.execute("BEGIN IMMEDIATE")
                rows = connection.execute(
                    """SELECT * FROM worker_admission_stubs WHERE operator_id = ? AND (
                    idempotency_key_fingerprint = ? OR subject_fingerprint = ? OR
                    stub_id = ? OR stub_fingerprint = ?)""",
                    (
                        stub.operator_id,
                        stub.idempotency_key_fingerprint.value,
                        reservation.subject_fingerprint.value,
                        stub.stub_id,
                        stub.stub_fingerprint.value,
                    ),
                ).fetchall()
                if rows:
                    if len(rows) != 1 or not self._is_exact(rows[0], stub, reservation):
                        raise WorkerAdmissionStubStoreError("conflict")
                    existing = self._decode(rows[0], operator_id=stub.operator_id)
                    connection.execute("COMMIT")
                    return existing, False
                count = connection.execute(
                    "SELECT COUNT(*) FROM worker_admission_stubs WHERE operator_id = ?",
                    (stub.operator_id,),
                ).fetchone()[0]
                if count >= self.max_records_per_operator:
                    raise WorkerAdmissionStubStoreError("quota_exceeded")
                connection.execute(
                    """INSERT INTO worker_admission_stubs (
                    operator_id, stub_id, candidate_record_id,
                    runner_binding_plan_valid_until, idempotency_key_fingerprint,
                    runner_binding_plan_fingerprint, worker_reference_fingerprint,
                    worker_admission_intent_fingerprint, inherited_limits_fingerprint,
                    subject_fingerprint, request_fingerprint, stub_fingerprint,
                    recorded_at, stub_json, reservation_json, audit_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        stub.operator_id,
                        stub.stub_id,
                        stub.candidate_record_id,
                        runner_binding_plan_valid_until,
                        stub.idempotency_key_fingerprint.value,
                        stub.linkage.runner_binding_plan_fingerprint.value,
                        stub.linkage.worker_reference_fingerprint.value,
                        stub.linkage.worker_admission_intent_fingerprint.value,
                        stub.linkage.inherited_limits_fingerprint.value,
                        reservation.subject_fingerprint.value,
                        stub.request_fingerprint.value,
                        stub.stub_fingerprint.value,
                        stub.recorded_at,
                        stub_json,
                        reservation_json,
                        audit_json,
                    ),
                )
                connection.execute("COMMIT")
                return stub, True
        except WorkerAdmissionStubStoreError:
            raise
        except sqlite3.IntegrityError as error:
            raise WorkerAdmissionStubStoreError("conflict") from error
        except sqlite3.Error as error:
            raise WorkerAdmissionStubStoreError("unavailable") from error

    def get(self, *, operator_id: str, stub_id: str) -> WorkerAdmissionStubV1:
        try:
            with self._connect() as connection:
                row = connection.execute(
                    "SELECT * FROM worker_admission_stubs WHERE operator_id = ? AND stub_id = ?",
                    (operator_id, stub_id),
                ).fetchone()
        except sqlite3.Error as error:
            raise WorkerAdmissionStubStoreError("unavailable") from error
        if row is None:
            raise WorkerAdmissionStubStoreError("not_found")
        return self._decode(row, operator_id=operator_id)

    def list_owned(self, *, operator_id: str) -> tuple[WorkerAdmissionStubV1, ...]:
        try:
            with self._connect() as connection:
                rows = connection.execute(
                    """SELECT * FROM worker_admission_stubs WHERE operator_id = ?
                    ORDER BY recorded_at DESC, stub_id DESC""",
                    (operator_id,),
                ).fetchall()
        except sqlite3.Error as error:
            raise WorkerAdmissionStubStoreError("unavailable") from error
        if len(rows) > self.max_records_per_operator:
            raise WorkerAdmissionStubStoreError("unavailable")
        return tuple(self._decode(row, operator_id=operator_id) for row in rows)

    @staticmethod
    def _is_exact(
        row: sqlite3.Row,
        stub: WorkerAdmissionStubV1,
        reservation: WorkerAdmissionStubReservationV1,
    ) -> bool:
        return (
            row["operator_id"] == stub.operator_id == reservation.operator_id
            and row["candidate_record_id"] == stub.candidate_record_id == reservation.candidate_record_id
            and row["stub_id"] == stub.stub_id == reservation.stub_id
            and row["idempotency_key_fingerprint"] == stub.idempotency_key_fingerprint.value == reservation.idempotency_key_fingerprint.value
            and row["runner_binding_plan_fingerprint"] == stub.linkage.runner_binding_plan_fingerprint.value == reservation.runner_binding_plan_fingerprint.value
            and row["worker_reference_fingerprint"] == stub.linkage.worker_reference_fingerprint.value == reservation.worker_reference_fingerprint.value
            and row["worker_admission_intent_fingerprint"] == stub.linkage.worker_admission_intent_fingerprint.value == reservation.worker_admission_intent_fingerprint.value
            and row["inherited_limits_fingerprint"] == stub.linkage.inherited_limits_fingerprint.value == reservation.inherited_limits_fingerprint.value
            and row["subject_fingerprint"] == reservation.subject_fingerprint.value
            and row["request_fingerprint"] == stub.request_fingerprint.value == reservation.request_fingerprint.value
            and row["stub_fingerprint"] == stub.stub_fingerprint.value
            and row["stub_json"] == stub.model_dump_json()
            and row["reservation_json"] == reservation.model_dump_json()
        )

    @staticmethod
    def _decode(row: sqlite3.Row, *, operator_id: str) -> WorkerAdmissionStubV1:
        try:
            payloads = (row["stub_json"], row["reservation_json"], row["audit_json"])
            if max(len(value.encode()) for value in payloads) > MAX_MODEL_BYTES:
                raise ValueError("persisted record exceeds bound")
            stub = WorkerAdmissionStubV1.model_validate_json(row["stub_json"])
            reservation = WorkerAdmissionStubReservationV1.model_validate_json(row["reservation_json"])
            audit = WorkerAdmissionStubAuditEvidenceV1.model_validate_json(row["audit_json"])
            if (
                operator_id != row["operator_id"]
                or row["runner_binding_plan_valid_until"] < stub.valid_until
                or not WorkerAdmissionStubStore._is_exact(row, stub, reservation)
                or audit.event != "worker_admission_stub_recorded"
                or audit.outcome != "recorded"
                or audit.operator_fingerprint != opaque_fingerprint("atlas:worker-admission-stub-operator:v1", stub.operator_id)
                or audit.candidate_record_fingerprint != opaque_fingerprint("atlas:worker-admission-stub-candidate:v1", stub.candidate_record_id)
                or audit.stub_fingerprint != stub.stub_fingerprint
                or audit.occurred_at != stub.recorded_at
            ):
                raise ValueError("persisted identity mismatch")
            return stub
        except Exception as error:
            raise WorkerAdmissionStubStoreError("unavailable") from error
