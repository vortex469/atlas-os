"""Append-only durable store for v0.40 worker intake admission evidence."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from .contract import (
    MAX_MODEL_BYTES,
    WorkerIntakeAdmissionAuditEvidenceV1,
    WorkerIntakeAdmissionSubjectReservationV1,
    WorkerIntakeAdmissionV1,
    audit_fingerprint,
    opaque_fingerprint,
    record_fingerprint,
    reservation_fingerprint,
)

MAX_RECORDS_PER_OPERATOR = 16


class WorkerIntakeAdmissionStoreError(RuntimeError):
    """Closed storage failure without database or record disclosure."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


class WorkerIntakeAdmissionStore:
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
        connection = sqlite3.connect(
            self.database_path, timeout=5, isolation_level=None
        )
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
                    CREATE TABLE IF NOT EXISTS worker_intake_admissions (
                        operator_id TEXT NOT NULL,
                        admission_id TEXT NOT NULL,
                        candidate_record_id TEXT NOT NULL,
                        worker_queue_reservation_valid_until TEXT NOT NULL,
                        idempotency_key_fingerprint TEXT NOT NULL,
                        worker_queue_reservation_fingerprint TEXT NOT NULL,
                        worker_queue_reservation_status_fingerprint TEXT NOT NULL,
                        worker_identity_fingerprint TEXT NOT NULL,
                        worker_intake_reference_fingerprint TEXT NOT NULL,
                        worker_intake_admission_decision_fingerprint TEXT NOT NULL,
                        inherited_limits_fingerprint TEXT NOT NULL,
                        subject_fingerprint TEXT NOT NULL,
                        request_fingerprint TEXT NOT NULL,
                        record_fingerprint TEXT NOT NULL,
                        recorded_at TEXT NOT NULL,
                        record_json TEXT NOT NULL,
                        reservation_json TEXT NOT NULL,
                        audit_json TEXT NOT NULL,
                        PRIMARY KEY (operator_id, admission_id),
                        UNIQUE (operator_id, idempotency_key_fingerprint),
                        UNIQUE (operator_id, subject_fingerprint),
                        UNIQUE (operator_id, record_fingerprint)
                    )
                    """
                )
        except sqlite3.Error as error:
            raise WorkerIntakeAdmissionStoreError("unavailable") from error

    def resolve_idempotency(
        self,
        *,
        operator_id: str,
        idempotency_key_fingerprint: str,
        worker_queue_reservation_valid_until: str,
    ) -> WorkerIntakeAdmissionV1 | None:
        try:
            with self._connect() as connection:
                row = connection.execute(
                    """SELECT * FROM worker_intake_admissions
                    WHERE operator_id = ? AND idempotency_key_fingerprint = ?""",
                    (operator_id, idempotency_key_fingerprint),
                ).fetchone()
        except sqlite3.Error as error:
            raise WorkerIntakeAdmissionStoreError("unavailable") from error
        if row is None:
            return None
        if (
            row["worker_queue_reservation_valid_until"]
            != worker_queue_reservation_valid_until
        ):
            raise WorkerIntakeAdmissionStoreError("conflict")
        return self._decode(row, operator_id=operator_id)

    def append(
        self,
        *,
        record: WorkerIntakeAdmissionV1,
        reservation: WorkerIntakeAdmissionSubjectReservationV1,
        audit_evidence: WorkerIntakeAdmissionAuditEvidenceV1,
        worker_queue_reservation_valid_until: str,
    ) -> tuple[WorkerIntakeAdmissionV1, bool]:
        record_json = record.model_dump_json()
        reservation_json = reservation.model_dump_json()
        audit_json = audit_evidence.model_dump_json()
        if (
            max(
                len(value.encode())
                for value in (record_json, reservation_json, audit_json)
            )
            > self.max_model_bytes
        ):
            raise WorkerIntakeAdmissionStoreError("record_too_large")
        try:
            with self._connect() as connection:
                connection.execute("BEGIN IMMEDIATE")
                rows = connection.execute(
                    """SELECT * FROM worker_intake_admissions WHERE operator_id = ?
                    AND (idempotency_key_fingerprint = ? OR subject_fingerprint = ?
                    OR admission_id = ? OR record_fingerprint = ?)""",
                    (
                        record.operator_id,
                        record.idempotency_key_fingerprint.value,
                        reservation.subject_fingerprint.value,
                        record.admission_id,
                        record.record_fingerprint.value,
                    ),
                ).fetchall()
                if rows:
                    if len(rows) != 1 or not self._is_exact(
                        rows[0], record, reservation
                    ):
                        raise WorkerIntakeAdmissionStoreError("conflict")
                    existing = self._decode(rows[0], operator_id=record.operator_id)
                    connection.execute("COMMIT")
                    return existing, False
                count = connection.execute(
                    """SELECT COUNT(*) FROM worker_intake_admissions
                    WHERE operator_id = ?""",
                    (record.operator_id,),
                ).fetchone()[0]
                if count >= self.max_records_per_operator:
                    raise WorkerIntakeAdmissionStoreError("quota_exceeded")
                link = record.linkage
                connection.execute(
                    """INSERT INTO worker_intake_admissions (
                    operator_id, admission_id, candidate_record_id,
                    worker_queue_reservation_valid_until,
                    idempotency_key_fingerprint,
                    worker_queue_reservation_fingerprint,
                    worker_queue_reservation_status_fingerprint,
                    worker_identity_fingerprint,
                    worker_intake_reference_fingerprint,
                    worker_intake_admission_decision_fingerprint,
                    inherited_limits_fingerprint, subject_fingerprint,
                    request_fingerprint, record_fingerprint, recorded_at,
                    record_json, reservation_json, audit_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        record.operator_id,
                        record.admission_id,
                        record.candidate_record_id,
                        worker_queue_reservation_valid_until,
                        record.idempotency_key_fingerprint.value,
                        link.queue_reservation_fingerprint.value,
                        link.queue_reservation_status_fingerprint.value,
                        link.worker_identity_fingerprint.value,
                        link.worker_intake_reference_fingerprint.value,
                        link.worker_intake_admission_decision_fingerprint.value,
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
        except WorkerIntakeAdmissionStoreError:
            raise
        except sqlite3.IntegrityError as error:
            raise WorkerIntakeAdmissionStoreError("conflict") from error
        except sqlite3.Error as error:
            raise WorkerIntakeAdmissionStoreError("unavailable") from error

    def get(self, *, operator_id: str, admission_id: str) -> WorkerIntakeAdmissionV1:
        try:
            with self._connect() as connection:
                row = connection.execute(
                    """SELECT * FROM worker_intake_admissions
                    WHERE operator_id = ? AND admission_id = ?""",
                    (operator_id, admission_id),
                ).fetchone()
        except sqlite3.Error as error:
            raise WorkerIntakeAdmissionStoreError("unavailable") from error
        if row is None:
            raise WorkerIntakeAdmissionStoreError("not_found")
        return self._decode(row, operator_id=operator_id)

    def list_owned(
        self, *, operator_id: str, candidate_record_id: str
    ) -> tuple[WorkerIntakeAdmissionV1, ...]:
        try:
            with self._connect() as connection:
                rows = connection.execute(
                    """SELECT * FROM worker_intake_admissions
                    WHERE operator_id = ? AND candidate_record_id = ?
                    ORDER BY recorded_at ASC, admission_id ASC""",
                    (operator_id, candidate_record_id),
                ).fetchall()
        except sqlite3.Error as error:
            raise WorkerIntakeAdmissionStoreError("unavailable") from error
        if len(rows) > self.max_records_per_operator:
            raise WorkerIntakeAdmissionStoreError("unavailable")
        return tuple(self._decode(row, operator_id=operator_id) for row in rows)

    @staticmethod
    def _is_exact(
        row: sqlite3.Row,
        record: WorkerIntakeAdmissionV1,
        reservation: WorkerIntakeAdmissionSubjectReservationV1,
    ) -> bool:
        link = record.linkage
        return (
            row["operator_id"] == record.operator_id == reservation.operator_id
            and row["candidate_record_id"]
            == record.candidate_record_id
            == reservation.candidate_record_id
            and row["admission_id"]
            == record.admission_id
            == reservation.admission_id
            and row["idempotency_key_fingerprint"]
            == record.idempotency_key_fingerprint.value
            == reservation.idempotency_key_fingerprint.value
            and row["worker_queue_reservation_fingerprint"]
            == link.queue_reservation_fingerprint.value
            == reservation.worker_queue_reservation_fingerprint.value
            and row["worker_queue_reservation_status_fingerprint"]
            == link.queue_reservation_status_fingerprint.value
            and row["worker_identity_fingerprint"]
            == link.worker_identity_fingerprint.value
            == reservation.worker_identity_fingerprint.value
            and row["worker_intake_reference_fingerprint"]
            == link.worker_intake_reference_fingerprint.value
            == reservation.worker_intake_reference_fingerprint.value
            and row["worker_intake_admission_decision_fingerprint"]
            == link.worker_intake_admission_decision_fingerprint.value
            == reservation.worker_intake_admission_decision_fingerprint.value
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
    ) -> WorkerIntakeAdmissionV1:
        try:
            payloads = (row["record_json"], row["reservation_json"], row["audit_json"])
            if max(len(value.encode()) for value in payloads) > self.max_model_bytes:
                raise ValueError("persisted record exceeds bound")
            record = WorkerIntakeAdmissionV1.model_validate_json(row["record_json"])
            reservation = WorkerIntakeAdmissionSubjectReservationV1.model_validate_json(
                row["reservation_json"]
            )
            audit = WorkerIntakeAdmissionAuditEvidenceV1.model_validate_json(
                row["audit_json"]
            )
            if (
                operator_id != row["operator_id"]
                or row["worker_queue_reservation_valid_until"] < record.valid_until
                or record.record_fingerprint != record_fingerprint(record)
                or reservation.reservation_fingerprint
                != reservation_fingerprint(reservation)
                or audit.audit_fingerprint != audit_fingerprint(audit)
                or not self._is_exact(row, record, reservation)
                or audit.event != "intake_admission_recorded"
                or audit.outcome != "recorded"
                or audit.operator_fingerprint
                != opaque_fingerprint(
                    "atlas:worker-intake-admission-operator:v1",
                    record.operator_id,
                )
                or audit.candidate_record_fingerprint
                != opaque_fingerprint(
                    "atlas:worker-intake-admission-candidate:v1",
                    record.candidate_record_id,
                )
                or audit.admission_id != record.admission_id
                or audit.subject_fingerprint != record.subject_fingerprint
                or audit.record_fingerprint != record.record_fingerprint
                or audit.occurred_at != record.recorded_at
            ):
                raise ValueError("persisted identity mismatch")
            return record
        except Exception as error:
            raise WorkerIntakeAdmissionStoreError("store_corrupt") from error
