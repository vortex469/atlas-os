"""Durable append-only store for v0.46 one-shot dequeue worker binding evidence."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from .contract import (
    MAX_MODEL_BYTES,
    OneShotDequeueWorkerBindingAuditEvidenceV1,
    OneShotDequeueWorkerBindingIdempotencyReservationV1,
    OneShotDequeueWorkerBindingSubjectReservationV1,
    OneShotDequeueWorkerBindingV1,
    audit_fingerprint,
    binding_record_fingerprint,
    reservation_fingerprint,
)

MAX_RECORDS_PER_OPERATOR = 16


class OneShotDequeueWorkerBindingStoreError(RuntimeError):
    """Closed storage failure without database or record disclosure."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


class OneShotDequeueWorkerBindingStore:
    """SQLite reservations and records; no worker, runtime, queue, or effect API."""

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
                    CREATE TABLE IF NOT EXISTS one_shot_dequeue_worker_binding_reservations (
                        operator_id TEXT NOT NULL,
                        candidate_record_id TEXT NOT NULL,
                        binding_id TEXT NOT NULL,
                        idempotency_key_fingerprint TEXT NOT NULL,
                        request_fingerprint TEXT NOT NULL,
                        subject_fingerprint TEXT NOT NULL,
                        binding_record_fingerprint TEXT NOT NULL,
                        v045_dequeue_valid_until TEXT NOT NULL,
                        v040_worker_intake_valid_until TEXT NOT NULL,
                        reserved_at TEXT NOT NULL,
                        idempotency_json TEXT NOT NULL,
                        reservation_json TEXT NOT NULL,
                        attempt_started TEXT NOT NULL,
                        PRIMARY KEY (operator_id, binding_id),
                        UNIQUE (operator_id, idempotency_key_fingerprint),
                        UNIQUE (operator_id, subject_fingerprint),
                        UNIQUE (operator_id, binding_record_fingerprint)
                    )
                    """
                )
                connection.execute(
                    """
                    CREATE TABLE IF NOT EXISTS one_shot_dequeue_worker_binding_attempts (
                        operator_id TEXT NOT NULL,
                        binding_id TEXT NOT NULL,
                        audit_fingerprint TEXT NOT NULL,
                        audit_json TEXT NOT NULL,
                        PRIMARY KEY (operator_id, binding_id, audit_fingerprint),
                        FOREIGN KEY (operator_id, binding_id)
                            REFERENCES one_shot_dequeue_worker_binding_reservations(
                                operator_id, binding_id
                            )
                    )
                    """
                )
                connection.execute(
                    """
                    CREATE TABLE IF NOT EXISTS one_shot_dequeue_worker_bindings (
                        operator_id TEXT NOT NULL,
                        binding_id TEXT NOT NULL,
                        candidate_record_id TEXT NOT NULL,
                        idempotency_key_fingerprint TEXT NOT NULL,
                        request_fingerprint TEXT NOT NULL,
                        subject_fingerprint TEXT NOT NULL,
                        binding_record_fingerprint TEXT NOT NULL,
                        v045_dequeue_id TEXT NOT NULL,
                        v045_dequeue_record_fingerprint TEXT NOT NULL,
                        v045_dequeue_status_fingerprint TEXT NOT NULL,
                        v040_worker_intake_admission_id TEXT NOT NULL,
                        v040_worker_intake_record_fingerprint TEXT NOT NULL,
                        v040_worker_intake_status_fingerprint TEXT NOT NULL,
                        worker_subject_fingerprint TEXT NOT NULL,
                        queue_item_reference_fingerprint TEXT NOT NULL,
                        recorded_at TEXT NOT NULL,
                        valid_until TEXT NOT NULL,
                        record_json TEXT NOT NULL,
                        audit_json TEXT NOT NULL,
                        PRIMARY KEY (operator_id, binding_id),
                        UNIQUE (operator_id, idempotency_key_fingerprint),
                        UNIQUE (operator_id, subject_fingerprint),
                        UNIQUE (operator_id, binding_record_fingerprint),
                        FOREIGN KEY (operator_id, binding_id)
                            REFERENCES one_shot_dequeue_worker_binding_reservations(
                                operator_id, binding_id
                            )
                    )
                    """
                )
        except sqlite3.Error as error:
            raise OneShotDequeueWorkerBindingStoreError("unavailable") from error

    def resolve_idempotency(
        self,
        *,
        operator_id: str,
        idempotency_key_fingerprint: str,
        request_fingerprint: str,
        v045_dequeue_valid_until: str,
        v040_worker_intake_valid_until: str,
    ) -> OneShotDequeueWorkerBindingV1 | None:
        try:
            with self._connect() as connection:
                reservation = connection.execute(
                    """SELECT * FROM one_shot_dequeue_worker_binding_reservations
                    WHERE operator_id = ? AND idempotency_key_fingerprint = ?""",
                    (operator_id, idempotency_key_fingerprint),
                ).fetchone()
                if reservation is None:
                    return None
                if (
                    reservation["request_fingerprint"] != request_fingerprint
                    or reservation["v045_dequeue_valid_until"] != v045_dequeue_valid_until
                    or reservation["v040_worker_intake_valid_until"]
                    != v040_worker_intake_valid_until
                ):
                    raise OneShotDequeueWorkerBindingStoreError("idempotency_conflict")
                row = connection.execute(
                    """SELECT * FROM one_shot_dequeue_worker_bindings
                    WHERE operator_id = ? AND binding_id = ?""",
                    (operator_id, reservation["binding_id"]),
                ).fetchone()
        except OneShotDequeueWorkerBindingStoreError:
            raise
        except sqlite3.Error as error:
            raise OneShotDequeueWorkerBindingStoreError("unavailable") from error
        self._validate_reservation(reservation, operator_id=operator_id)
        if row is None:
            raise OneShotDequeueWorkerBindingStoreError("append_indeterminate")
        return self._decode_record(row, reservation, operator_id=operator_id)

    def append(
        self,
        *,
        record: OneShotDequeueWorkerBindingV1,
        idempotency_reservation: OneShotDequeueWorkerBindingIdempotencyReservationV1,
        subject_reservation: OneShotDequeueWorkerBindingSubjectReservationV1,
        audit_evidence: OneShotDequeueWorkerBindingAuditEvidenceV1,
        v045_dequeue_valid_until: str,
        v040_worker_intake_valid_until: str,
        force_indeterminate: bool = False,
    ) -> tuple[OneShotDequeueWorkerBindingV1, bool]:
        record_json = record.model_dump_json()
        idempotency_json = idempotency_reservation.model_dump_json()
        reservation_json = subject_reservation.model_dump_json()
        audit_json = audit_evidence.model_dump_json()
        if (
            max(
                len(value.encode())
                for value in (record_json, idempotency_json, reservation_json, audit_json)
            )
            > self.max_model_bytes
        ):
            raise OneShotDequeueWorkerBindingStoreError("record_too_large")
        self._reserve_attempt(
            record=record,
            idempotency_reservation=idempotency_reservation,
            subject_reservation=subject_reservation,
            v045_dequeue_valid_until=v045_dequeue_valid_until,
            v040_worker_intake_valid_until=v040_worker_intake_valid_until,
        )
        if force_indeterminate:
            self.mark_indeterminate(
                operator_id=record.operator_id,
                binding_id=record.binding_id,
                audit_evidence=audit_evidence,
            )
            raise OneShotDequeueWorkerBindingStoreError("append_indeterminate")
        return self._append_record(
            record=record,
            subject_reservation=subject_reservation,
            audit_json=audit_json,
        )

    def mark_indeterminate(
        self,
        *,
        operator_id: str,
        binding_id: str,
        audit_evidence: OneShotDequeueWorkerBindingAuditEvidenceV1,
    ) -> None:
        audit_json = audit_evidence.model_dump_json()
        if len(audit_json.encode()) > self.max_model_bytes:
            raise OneShotDequeueWorkerBindingStoreError("record_too_large")
        try:
            with self._connect() as connection:
                connection.execute("BEGIN IMMEDIATE")
                row = connection.execute(
                    """SELECT * FROM one_shot_dequeue_worker_binding_reservations
                    WHERE operator_id = ? AND binding_id = ?""",
                    (operator_id, binding_id),
                ).fetchone()
                if row is None:
                    raise OneShotDequeueWorkerBindingStoreError("not_found")
                connection.execute(
                    """INSERT OR IGNORE INTO one_shot_dequeue_worker_binding_attempts (
                    operator_id, binding_id, audit_fingerprint, audit_json
                    ) VALUES (?, ?, ?, ?)""",
                    (
                        operator_id,
                        binding_id,
                        audit_evidence.audit_fingerprint.value,
                        audit_json,
                    ),
                )
                connection.execute("COMMIT")
        except OneShotDequeueWorkerBindingStoreError:
            raise
        except sqlite3.Error as error:
            raise OneShotDequeueWorkerBindingStoreError("unavailable") from error

    def get(self, *, operator_id: str, binding_id: str) -> OneShotDequeueWorkerBindingV1:
        try:
            with self._connect() as connection:
                row = connection.execute(
                    """SELECT * FROM one_shot_dequeue_worker_bindings
                    WHERE operator_id = ? AND binding_id = ?""",
                    (operator_id, binding_id),
                ).fetchone()
                reservation = connection.execute(
                    """SELECT * FROM one_shot_dequeue_worker_binding_reservations
                    WHERE operator_id = ? AND binding_id = ?""",
                    (operator_id, binding_id),
                ).fetchone()
        except sqlite3.Error as error:
            raise OneShotDequeueWorkerBindingStoreError("unavailable") from error
        if row is None or reservation is None:
            raise OneShotDequeueWorkerBindingStoreError("not_found")
        return self._decode_record(row, reservation, operator_id=operator_id)

    def list_owned(
        self, *, operator_id: str, candidate_record_id: str
    ) -> tuple[OneShotDequeueWorkerBindingV1, ...]:
        try:
            with self._connect() as connection:
                rows = connection.execute(
                    """SELECT * FROM one_shot_dequeue_worker_bindings
                    WHERE operator_id = ? AND candidate_record_id = ?
                    ORDER BY recorded_at ASC, binding_id ASC
                    LIMIT ?""",
                    (
                        operator_id,
                        candidate_record_id,
                        self.max_records_per_operator + 1,
                    ),
                ).fetchall()
                reservations = {
                    row["binding_id"]: row
                    for row in connection.execute(
                        """SELECT * FROM one_shot_dequeue_worker_binding_reservations
                        WHERE operator_id = ?""",
                        (operator_id,),
                    ).fetchall()
                }
        except sqlite3.Error as error:
            raise OneShotDequeueWorkerBindingStoreError("unavailable") from error
        if len(rows) > self.max_records_per_operator:
            raise OneShotDequeueWorkerBindingStoreError("quota_exceeded")
        return tuple(
            self._decode_record(
                row, reservations.get(row["binding_id"]), operator_id=operator_id
            )
            for row in rows
        )

    def _reserve_attempt(
        self,
        *,
        record: OneShotDequeueWorkerBindingV1,
        idempotency_reservation: OneShotDequeueWorkerBindingIdempotencyReservationV1,
        subject_reservation: OneShotDequeueWorkerBindingSubjectReservationV1,
        v045_dequeue_valid_until: str,
        v040_worker_intake_valid_until: str,
    ) -> None:
        idempotency_json = idempotency_reservation.model_dump_json()
        reservation_json = subject_reservation.model_dump_json()
        try:
            with self._connect() as connection:
                connection.execute("BEGIN IMMEDIATE")
                rows = connection.execute(
                    """SELECT * FROM one_shot_dequeue_worker_binding_reservations
                    WHERE operator_id = ?
                    AND (idempotency_key_fingerprint = ?
                    OR subject_fingerprint = ?
                    OR binding_id = ?
                    OR binding_record_fingerprint = ?)""",
                    (
                        record.operator_id,
                        idempotency_reservation.idempotency_key_fingerprint.value,
                        record.subject_fingerprint.value,
                        record.binding_id,
                        record.binding_record_fingerprint.value,
                    ),
                ).fetchall()
                if rows:
                    if len(rows) != 1:
                        raise OneShotDequeueWorkerBindingStoreError("conflict")
                    row = rows[0]
                    if not self._is_exact_reservation(
                        row,
                        record,
                        idempotency_reservation,
                        subject_reservation,
                        v045_dequeue_valid_until,
                        v040_worker_intake_valid_until,
                    ):
                        if (
                            row["idempotency_key_fingerprint"]
                            == idempotency_reservation.idempotency_key_fingerprint.value
                        ):
                            raise OneShotDequeueWorkerBindingStoreError(
                                "idempotency_conflict"
                            )
                        raise OneShotDequeueWorkerBindingStoreError(
                            "permanent_subject_reserved"
                        )
                    existing = connection.execute(
                        """SELECT 1 FROM one_shot_dequeue_worker_bindings
                        WHERE operator_id = ? AND binding_id = ?""",
                        (record.operator_id, record.binding_id),
                    ).fetchone()
                    if existing is None:
                        raise OneShotDequeueWorkerBindingStoreError(
                            "append_indeterminate"
                        )
                    connection.execute("COMMIT")
                    return
                count = connection.execute(
                    """SELECT COUNT(*) FROM one_shot_dequeue_worker_binding_reservations
                    WHERE operator_id = ?""",
                    (record.operator_id,),
                ).fetchone()[0]
                if count >= self.max_records_per_operator:
                    raise OneShotDequeueWorkerBindingStoreError("quota_exceeded")
                connection.execute(
                    """INSERT INTO one_shot_dequeue_worker_binding_reservations (
                    operator_id, candidate_record_id, binding_id,
                    idempotency_key_fingerprint, request_fingerprint,
                    subject_fingerprint, binding_record_fingerprint,
                    v045_dequeue_valid_until, v040_worker_intake_valid_until,
                    reserved_at, idempotency_json, reservation_json, attempt_started
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        record.operator_id,
                        record.candidate_record_id,
                        record.binding_id,
                        idempotency_reservation.idempotency_key_fingerprint.value,
                        idempotency_reservation.request_fingerprint.value,
                        record.subject_fingerprint.value,
                        record.binding_record_fingerprint.value,
                        v045_dequeue_valid_until,
                        v040_worker_intake_valid_until,
                        record.recorded_at,
                        idempotency_json,
                        reservation_json,
                        "true",
                    ),
                )
                connection.execute("COMMIT")
        except OneShotDequeueWorkerBindingStoreError:
            raise
        except sqlite3.IntegrityError as error:
            raise OneShotDequeueWorkerBindingStoreError("conflict") from error
        except sqlite3.Error as error:
            raise OneShotDequeueWorkerBindingStoreError("unavailable") from error

    def _append_record(
        self,
        *,
        record: OneShotDequeueWorkerBindingV1,
        subject_reservation: OneShotDequeueWorkerBindingSubjectReservationV1,
        audit_json: str,
    ) -> tuple[OneShotDequeueWorkerBindingV1, bool]:
        try:
            with self._connect() as connection:
                connection.execute("BEGIN IMMEDIATE")
                row = connection.execute(
                    """SELECT * FROM one_shot_dequeue_worker_bindings
                    WHERE operator_id = ? AND binding_id = ?""",
                    (record.operator_id, record.binding_id),
                ).fetchone()
                reservation = connection.execute(
                    """SELECT * FROM one_shot_dequeue_worker_binding_reservations
                    WHERE operator_id = ? AND binding_id = ?""",
                    (record.operator_id, record.binding_id),
                ).fetchone()
                if reservation is None:
                    raise OneShotDequeueWorkerBindingStoreError(
                        "reservation_before_effect_failed"
                    )
                if row is not None:
                    existing = self._decode_record(
                        row, reservation, operator_id=record.operator_id
                    )
                    connection.execute("COMMIT")
                    return existing, False
                dequeue = record.one_shot_controlled_dequeue
                dequeue_status = record.one_shot_controlled_dequeue_status
                worker = record.worker_intake_admission
                worker_status = record.worker_intake_admission_status
                connection.execute(
                    """INSERT INTO one_shot_dequeue_worker_bindings (
                    operator_id, binding_id, candidate_record_id,
                    idempotency_key_fingerprint, request_fingerprint,
                    subject_fingerprint, binding_record_fingerprint,
                    v045_dequeue_id, v045_dequeue_record_fingerprint,
                    v045_dequeue_status_fingerprint,
                    v040_worker_intake_admission_id,
                    v040_worker_intake_record_fingerprint,
                    v040_worker_intake_status_fingerprint,
                    worker_subject_fingerprint, queue_item_reference_fingerprint,
                    recorded_at, valid_until, record_json, audit_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        record.operator_id,
                        record.binding_id,
                        record.candidate_record_id,
                        subject_reservation.idempotency_key_fingerprint.value,
                        subject_reservation.request_fingerprint.value,
                        record.subject_fingerprint.value,
                        record.binding_record_fingerprint.value,
                        dequeue.dequeue_id,
                        dequeue.dequeue_record_fingerprint.value,
                        dequeue_status.status_fingerprint.value,
                        worker.admission_id,
                        worker.record_fingerprint.value,
                        worker_status.status_fingerprint.value,
                        record.worker_subject_fingerprint.value,
                        record.queue_item_reference_fingerprint.value,
                        record.recorded_at,
                        record.valid_until,
                        record.model_dump_json(),
                        audit_json,
                    ),
                )
                connection.execute("COMMIT")
                return record, True
        except OneShotDequeueWorkerBindingStoreError:
            raise
        except sqlite3.IntegrityError as error:
            raise OneShotDequeueWorkerBindingStoreError("conflict") from error
        except sqlite3.Error as error:
            raise OneShotDequeueWorkerBindingStoreError("unavailable") from error

    @staticmethod
    def _is_exact_reservation(
        row: sqlite3.Row,
        record: OneShotDequeueWorkerBindingV1,
        idempotency_reservation: OneShotDequeueWorkerBindingIdempotencyReservationV1,
        subject_reservation: OneShotDequeueWorkerBindingSubjectReservationV1,
        v045_dequeue_valid_until: str,
        v040_worker_intake_valid_until: str,
    ) -> bool:
        return (
            row["operator_id"] == record.operator_id == subject_reservation.operator_id
            and row["operator_id"] == idempotency_reservation.operator_id
            and row["candidate_record_id"]
            == record.candidate_record_id
            == subject_reservation.candidate_record_id
            == idempotency_reservation.candidate_record_id
            and row["binding_id"]
            == record.binding_id
            == subject_reservation.binding_id
            == idempotency_reservation.binding_id
            and row["idempotency_key_fingerprint"]
            == idempotency_reservation.idempotency_key_fingerprint.value
            == subject_reservation.idempotency_key_fingerprint.value
            and row["request_fingerprint"]
            == idempotency_reservation.request_fingerprint.value
            == subject_reservation.request_fingerprint.value
            and row["subject_fingerprint"]
            == record.subject_fingerprint.value
            == idempotency_reservation.subject_fingerprint.value
            == subject_reservation.subject_fingerprint.value
            and row["binding_record_fingerprint"]
            == record.binding_record_fingerprint.value
            == idempotency_reservation.binding_record_fingerprint.value
            == subject_reservation.binding_record_fingerprint.value
            and row["v045_dequeue_valid_until"] == v045_dequeue_valid_until
            and row["v040_worker_intake_valid_until"] == v040_worker_intake_valid_until
            and row["reserved_at"] == record.recorded_at
            and row["idempotency_json"] == idempotency_reservation.model_dump_json()
            and row["reservation_json"] == subject_reservation.model_dump_json()
            and row["attempt_started"] == "true"
        )

    def _validate_reservation(
        self, row: sqlite3.Row | None, *, operator_id: str
    ) -> None:
        try:
            if row is None or operator_id != row["operator_id"]:
                raise ValueError("reservation missing")
            payloads = (row["idempotency_json"], row["reservation_json"])
            if max(len(value.encode()) for value in payloads) > self.max_model_bytes:
                raise ValueError("persisted reservation exceeds bound")
            idempotency = (
                OneShotDequeueWorkerBindingIdempotencyReservationV1.model_validate_json(
                    row["idempotency_json"]
                )
            )
            reservation = (
                OneShotDequeueWorkerBindingSubjectReservationV1.model_validate_json(
                    row["reservation_json"]
                )
            )
            if (
                reservation.reservation_fingerprint
                != reservation_fingerprint(reservation)
                or row["attempt_started"] != "true"
                or not self._is_row_reservation_exact(row, idempotency, reservation)
            ):
                raise ValueError("persisted reservation mismatch")
        except Exception as error:
            raise OneShotDequeueWorkerBindingStoreError("store_corrupt") from error

    @staticmethod
    def _is_row_reservation_exact(
        row: sqlite3.Row,
        idempotency: OneShotDequeueWorkerBindingIdempotencyReservationV1,
        reservation: OneShotDequeueWorkerBindingSubjectReservationV1,
    ) -> bool:
        return (
            row["operator_id"] == idempotency.operator_id == reservation.operator_id
            and row["candidate_record_id"]
            == idempotency.candidate_record_id
            == reservation.candidate_record_id
            and row["binding_id"] == idempotency.binding_id == reservation.binding_id
            and row["idempotency_key_fingerprint"]
            == idempotency.idempotency_key_fingerprint.value
            == reservation.idempotency_key_fingerprint.value
            and row["request_fingerprint"]
            == idempotency.request_fingerprint.value
            == reservation.request_fingerprint.value
            and row["subject_fingerprint"]
            == idempotency.subject_fingerprint.value
            == reservation.subject_fingerprint.value
            and row["binding_record_fingerprint"]
            == idempotency.binding_record_fingerprint.value
            == reservation.binding_record_fingerprint.value
            and row["reserved_at"] == idempotency.reserved_at == reservation.reserved_at
            and row["idempotency_json"] == idempotency.model_dump_json()
            and row["reservation_json"] == reservation.model_dump_json()
        )

    def _decode_record(
        self,
        row: sqlite3.Row,
        reservation_row: sqlite3.Row | None,
        *,
        operator_id: str,
    ) -> OneShotDequeueWorkerBindingV1:
        try:
            self._validate_reservation(reservation_row, operator_id=operator_id)
            payloads = (row["record_json"], row["audit_json"])
            if max(len(value.encode()) for value in payloads) > self.max_model_bytes:
                raise ValueError("persisted record exceeds bound")
            record = OneShotDequeueWorkerBindingV1.model_validate_json(
                row["record_json"]
            )
            audit = OneShotDequeueWorkerBindingAuditEvidenceV1.model_validate_json(
                row["audit_json"]
            )
            dequeue = record.one_shot_controlled_dequeue
            dequeue_status = record.one_shot_controlled_dequeue_status
            worker = record.worker_intake_admission
            worker_status = record.worker_intake_admission_status
            if (
                operator_id != row["operator_id"]
                or record.binding_record_fingerprint
                != binding_record_fingerprint(record)
                or audit.audit_fingerprint != audit_fingerprint(audit)
                or row["operator_id"] != record.operator_id
                or row["candidate_record_id"] != record.candidate_record_id
                or row["binding_id"] != record.binding_id
                or row["idempotency_key_fingerprint"]
                != reservation_row["idempotency_key_fingerprint"]
                or row["request_fingerprint"] != reservation_row["request_fingerprint"]
                or row["subject_fingerprint"] != record.subject_fingerprint.value
                or row["binding_record_fingerprint"]
                != record.binding_record_fingerprint.value
                or row["v045_dequeue_id"] != dequeue.dequeue_id
                or row["v045_dequeue_record_fingerprint"]
                != dequeue.dequeue_record_fingerprint.value
                or row["v045_dequeue_status_fingerprint"]
                != dequeue_status.status_fingerprint.value
                or row["v040_worker_intake_admission_id"] != worker.admission_id
                or row["v040_worker_intake_record_fingerprint"]
                != worker.record_fingerprint.value
                or row["v040_worker_intake_status_fingerprint"]
                != worker_status.status_fingerprint.value
                or row["worker_subject_fingerprint"]
                != record.worker_subject_fingerprint.value
                or row["queue_item_reference_fingerprint"]
                != record.queue_item_reference_fingerprint.value
                or row["recorded_at"] != record.recorded_at
                or row["valid_until"] != record.valid_until
                or audit.event != "one_shot_dequeue_worker_binding_recorded"
                or audit.outcome != "recorded"
                or audit.operator_id != record.operator_id
                or audit.candidate_record_id != record.candidate_record_id
                or audit.binding_id != record.binding_id
                or audit.subject_fingerprint != record.subject_fingerprint
                or audit.binding_record_fingerprint
                != record.binding_record_fingerprint
                or audit.occurred_at != record.recorded_at
            ):
                raise ValueError("persisted record mismatch")
            return record
        except OneShotDequeueWorkerBindingStoreError:
            raise
        except Exception as error:
            raise OneShotDequeueWorkerBindingStoreError("store_corrupt") from error
