"""Append-only durable store for v0.39 worker queue reservation evidence."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from .contract import (
    MAX_MODEL_BYTES,
    WorkerQueueReservationAuditEvidenceV1,
    WorkerQueueReservationV1,
    WorkerQueueSubjectReservationV1,
    audit_fingerprint,
    opaque_fingerprint,
    record_fingerprint,
    reservation_fingerprint,
)

MAX_RECORDS_PER_OPERATOR = 16


class WorkerQueueReservationStoreError(RuntimeError):
    """Closed storage failure without database or record disclosure."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


class WorkerQueueReservationStore:
    """SQLite append-only evidence with permanent key and subject reservations."""

    def __init__(
        self,
        database_path: str | Path,
        *,
        max_records_per_operator: int = MAX_RECORDS_PER_OPERATOR,
        max_model_bytes: int = MAX_MODEL_BYTES,
    ) -> None:
        self.database_path = Path(database_path)
        self.max_records_per_operator = max_records_per_operator
        self.max_model_bytes = max_model_bytes
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
                    CREATE TABLE IF NOT EXISTS worker_queue_reservations (
                        operator_id TEXT NOT NULL,
                        reservation_id TEXT NOT NULL,
                        candidate_record_id TEXT NOT NULL,
                        worker_admission_stub_valid_until TEXT NOT NULL,
                        idempotency_key_fingerprint TEXT NOT NULL,
                        worker_admission_stub_fingerprint TEXT NOT NULL,
                        worker_reference_fingerprint TEXT NOT NULL,
                        queue_intake_reference_fingerprint TEXT NOT NULL,
                        queue_item_reference_fingerprint TEXT NOT NULL,
                        inherited_limits_fingerprint TEXT NOT NULL,
                        subject_fingerprint TEXT NOT NULL,
                        request_fingerprint TEXT NOT NULL,
                        record_fingerprint TEXT NOT NULL,
                        recorded_at TEXT NOT NULL,
                        record_json TEXT NOT NULL,
                        reservation_json TEXT NOT NULL,
                        audit_json TEXT NOT NULL,
                        PRIMARY KEY (operator_id, reservation_id),
                        UNIQUE (operator_id, idempotency_key_fingerprint),
                        UNIQUE (operator_id, subject_fingerprint),
                        UNIQUE (operator_id, record_fingerprint)
                    )
                    """
                )
        except sqlite3.Error as error:
            raise WorkerQueueReservationStoreError("unavailable") from error

    def resolve_idempotency(
        self, *, operator_id: str, idempotency_key_fingerprint: str,
        worker_admission_stub_valid_until: str,
    ) -> WorkerQueueReservationV1 | None:
        try:
            with self._connect() as connection:
                row = connection.execute(
                    """SELECT * FROM worker_queue_reservations
                    WHERE operator_id = ? AND idempotency_key_fingerprint = ?""",
                    (operator_id, idempotency_key_fingerprint),
                ).fetchone()
        except sqlite3.Error as error:
            raise WorkerQueueReservationStoreError("unavailable") from error
        if row is None:
            return None
        if row["worker_admission_stub_valid_until"] != worker_admission_stub_valid_until:
            raise WorkerQueueReservationStoreError("conflict")
        return self._decode(row, operator_id=operator_id)

    def append(
        self,
        *,
        record: WorkerQueueReservationV1,
        reservation: WorkerQueueSubjectReservationV1,
        audit_evidence: WorkerQueueReservationAuditEvidenceV1,
        worker_admission_stub_valid_until: str,
    ) -> tuple[WorkerQueueReservationV1, bool]:
        record_json = record.model_dump_json()
        reservation_json = reservation.model_dump_json()
        audit_json = audit_evidence.model_dump_json()
        if max(
            len(value.encode()) for value in (record_json, reservation_json, audit_json)
        ) > self.max_model_bytes:
            raise WorkerQueueReservationStoreError("record_too_large")
        try:
            with self._connect() as connection:
                connection.execute("BEGIN IMMEDIATE")
                rows = connection.execute(
                    """SELECT * FROM worker_queue_reservations WHERE operator_id = ?
                    AND (idempotency_key_fingerprint = ? OR subject_fingerprint = ?
                    OR reservation_id = ? OR record_fingerprint = ?)""",
                    (
                        record.operator_id,
                        record.idempotency_key_fingerprint.value,
                        reservation.subject_fingerprint.value,
                        record.reservation_id,
                        record.record_fingerprint.value,
                    ),
                ).fetchall()
                if rows:
                    if len(rows) != 1 or not self._is_exact(
                        rows[0], record, reservation
                    ):
                        raise WorkerQueueReservationStoreError("conflict")
                    existing = self._decode(rows[0], operator_id=record.operator_id)
                    connection.execute("COMMIT")
                    return existing, False
                count = connection.execute(
                    """SELECT COUNT(*) FROM worker_queue_reservations
                    WHERE operator_id = ?""",
                    (record.operator_id,),
                ).fetchone()[0]
                if count >= self.max_records_per_operator:
                    raise WorkerQueueReservationStoreError("quota_exceeded")
                link = record.linkage
                connection.execute(
                    """INSERT INTO worker_queue_reservations (
                    operator_id, reservation_id, candidate_record_id,
                    worker_admission_stub_valid_until,
                    idempotency_key_fingerprint,
                    worker_admission_stub_fingerprint,
                    worker_reference_fingerprint,
                    queue_intake_reference_fingerprint,
                    queue_item_reference_fingerprint,
                    inherited_limits_fingerprint, subject_fingerprint,
                    request_fingerprint, record_fingerprint, recorded_at,
                    record_json, reservation_json, audit_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        record.operator_id,
                        record.reservation_id,
                        record.candidate_record_id,
                        worker_admission_stub_valid_until,
                        record.idempotency_key_fingerprint.value,
                        link.worker_admission_stub_fingerprint.value,
                        link.worker_reference_fingerprint.value,
                        link.queue_intake_reference_fingerprint.value,
                        link.queue_item_reference_fingerprint.value,
                        link.inherited_limits_fingerprint.value,
                        reservation.subject_fingerprint.value,
                        record.request_fingerprint.value,
                        record.record_fingerprint.value,
                        record.recorded_at,
                        record_json,
                        reservation_json,
                        audit_json,
                    ),
                )
                connection.execute("COMMIT")
                return record, True
        except WorkerQueueReservationStoreError:
            raise
        except sqlite3.IntegrityError as error:
            raise WorkerQueueReservationStoreError("conflict") from error
        except sqlite3.Error as error:
            raise WorkerQueueReservationStoreError("unavailable") from error

    def get(self, *, operator_id: str, reservation_id: str) -> WorkerQueueReservationV1:
        try:
            with self._connect() as connection:
                row = connection.execute(
                    """SELECT * FROM worker_queue_reservations
                    WHERE operator_id = ? AND reservation_id = ?""",
                    (operator_id, reservation_id),
                ).fetchone()
        except sqlite3.Error as error:
            raise WorkerQueueReservationStoreError("unavailable") from error
        if row is None:
            raise WorkerQueueReservationStoreError("not_found")
        return self._decode(row, operator_id=operator_id)

    def list_owned(self, *, operator_id: str) -> tuple[WorkerQueueReservationV1, ...]:
        try:
            with self._connect() as connection:
                rows = connection.execute(
                    """SELECT * FROM worker_queue_reservations
                    WHERE operator_id = ?
                    ORDER BY recorded_at DESC, reservation_id DESC""",
                    (operator_id,),
                ).fetchall()
        except sqlite3.Error as error:
            raise WorkerQueueReservationStoreError("unavailable") from error
        if len(rows) > self.max_records_per_operator:
            raise WorkerQueueReservationStoreError("unavailable")
        return tuple(self._decode(row, operator_id=operator_id) for row in rows)

    @staticmethod
    def _is_exact(
        row: sqlite3.Row,
        record: WorkerQueueReservationV1,
        reservation: WorkerQueueSubjectReservationV1,
    ) -> bool:
        link = record.linkage
        return (
            row["operator_id"] == record.operator_id == reservation.operator_id
            and row["candidate_record_id"]
            == record.candidate_record_id
            == reservation.candidate_record_id
            and row["reservation_id"]
            == record.reservation_id
            == reservation.reservation_id
            and row["idempotency_key_fingerprint"]
            == record.idempotency_key_fingerprint.value
            == reservation.idempotency_key_fingerprint.value
            and row["worker_admission_stub_fingerprint"]
            == link.worker_admission_stub_fingerprint.value
            == reservation.worker_admission_stub_fingerprint.value
            and row["worker_reference_fingerprint"]
            == link.worker_reference_fingerprint.value
            == reservation.worker_reference_fingerprint.value
            and row["queue_intake_reference_fingerprint"]
            == link.queue_intake_reference_fingerprint.value
            == reservation.queue_intake_reference_fingerprint.value
            and row["queue_item_reference_fingerprint"]
            == link.queue_item_reference_fingerprint.value
            == reservation.queue_item_reference_fingerprint.value
            and row["inherited_limits_fingerprint"]
            == link.inherited_limits_fingerprint.value
            == reservation.inherited_limits_fingerprint.value
            and row["subject_fingerprint"] == reservation.subject_fingerprint.value
            and row["request_fingerprint"]
            == record.request_fingerprint.value
            == reservation.request_fingerprint.value
            and row["record_fingerprint"] == record.record_fingerprint.value
            and row["record_json"] == record.model_dump_json()
            and row["reservation_json"] == reservation.model_dump_json()
        )

    def _decode(
        self, row: sqlite3.Row, *, operator_id: str
    ) -> WorkerQueueReservationV1:
        try:
            payloads = (
                row["record_json"], row["reservation_json"], row["audit_json"]
            )
            if max(len(value.encode()) for value in payloads) > self.max_model_bytes:
                raise ValueError("persisted record exceeds bound")
            record = WorkerQueueReservationV1.model_validate_json(row["record_json"])
            reservation = WorkerQueueSubjectReservationV1.model_validate_json(
                row["reservation_json"]
            )
            audit = WorkerQueueReservationAuditEvidenceV1.model_validate_json(
                row["audit_json"]
            )
            if (
                operator_id != row["operator_id"]
                or row["worker_admission_stub_valid_until"] < record.valid_until
                or record.record_fingerprint != record_fingerprint(record)
                or reservation.reservation_fingerprint
                != reservation_fingerprint(reservation)
                or audit.audit_fingerprint != audit_fingerprint(audit)
                or not self._is_exact(row, record, reservation)
                or audit.event != "reservation_recorded"
                or audit.outcome != "recorded"
                or audit.operator_fingerprint
                != opaque_fingerprint(
                    "atlas:worker-queue-reservation-operator:v1",
                    record.operator_id,
                )
                or audit.candidate_record_fingerprint
                != opaque_fingerprint(
                    "atlas:worker-queue-reservation-candidate:v1",
                    record.candidate_record_id,
                )
                or audit.reservation_id != record.reservation_id
                or audit.subject_fingerprint != record.subject_fingerprint
                or audit.record_fingerprint != record.record_fingerprint
                or audit.occurred_at != record.recorded_at
            ):
                raise ValueError("persisted identity mismatch")
            return record
        except Exception as error:
            raise WorkerQueueReservationStoreError("unavailable") from error
