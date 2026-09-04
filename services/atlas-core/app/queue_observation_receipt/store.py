"""Durable append-only store for v0.43 queue observation receipt evidence."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from .contract import (
    MAX_MODEL_BYTES,
    QueueObservationReceiptAuditEvidenceV1,
    QueueObservationReceiptIdempotencyReservationV1,
    QueueObservationReceiptSubjectReservationV1,
    QueueObservationReceiptV1,
    audit_fingerprint,
    receipt_record_fingerprint,
    reservation_fingerprint,
)

MAX_RECORDS_PER_OPERATOR = 16


class QueueObservationReceiptStoreError(RuntimeError):
    """Closed storage failure without database or record disclosure."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


class QueueObservationReceiptStore:
    """SQLite reservations and records; no dequeue, worker, queue, or effect API."""

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
                    CREATE TABLE IF NOT EXISTS queue_observation_receipt_reservations (
                        operator_id TEXT NOT NULL,
                        candidate_record_id TEXT NOT NULL,
                        receipt_id TEXT NOT NULL,
                        idempotency_key_fingerprint TEXT NOT NULL,
                        request_fingerprint TEXT NOT NULL,
                        subject_fingerprint TEXT NOT NULL,
                        receipt_record_fingerprint TEXT NOT NULL,
                        v042_enqueue_valid_until TEXT NOT NULL,
                        reserved_at TEXT NOT NULL,
                        idempotency_json TEXT NOT NULL,
                        reservation_json TEXT NOT NULL,
                        attempt_started TEXT NOT NULL,
                        PRIMARY KEY (operator_id, receipt_id),
                        UNIQUE (operator_id, idempotency_key_fingerprint),
                        UNIQUE (operator_id, subject_fingerprint),
                        UNIQUE (operator_id, receipt_record_fingerprint)
                    )
                    """
                )
                connection.execute(
                    """
                    CREATE TABLE IF NOT EXISTS queue_observation_receipt_attempts (
                        operator_id TEXT NOT NULL,
                        receipt_id TEXT NOT NULL,
                        audit_fingerprint TEXT NOT NULL,
                        audit_json TEXT NOT NULL,
                        PRIMARY KEY (operator_id, receipt_id, audit_fingerprint),
                        FOREIGN KEY (operator_id, receipt_id)
                            REFERENCES queue_observation_receipt_reservations(
                                operator_id, receipt_id
                            )
                    )
                    """
                )
                connection.execute(
                    """
                    CREATE TABLE IF NOT EXISTS queue_observation_receipts (
                        operator_id TEXT NOT NULL,
                        receipt_id TEXT NOT NULL,
                        candidate_record_id TEXT NOT NULL,
                        idempotency_key_fingerprint TEXT NOT NULL,
                        request_fingerprint TEXT NOT NULL,
                        subject_fingerprint TEXT NOT NULL,
                        receipt_record_fingerprint TEXT NOT NULL,
                        enqueue_id TEXT NOT NULL,
                        enqueue_record_fingerprint TEXT NOT NULL,
                        enqueue_status_fingerprint TEXT NOT NULL,
                        queue_item_fingerprint TEXT NOT NULL,
                        lineage_fingerprint TEXT NOT NULL,
                        recorded_at TEXT NOT NULL,
                        valid_until TEXT NOT NULL,
                        record_json TEXT NOT NULL,
                        audit_json TEXT NOT NULL,
                        PRIMARY KEY (operator_id, receipt_id),
                        UNIQUE (operator_id, idempotency_key_fingerprint),
                        UNIQUE (operator_id, subject_fingerprint),
                        UNIQUE (operator_id, receipt_record_fingerprint),
                        FOREIGN KEY (operator_id, receipt_id)
                            REFERENCES queue_observation_receipt_reservations(
                                operator_id, receipt_id
                            )
                    )
                    """
                )
        except sqlite3.Error as error:
            raise QueueObservationReceiptStoreError("unavailable") from error

    def resolve_idempotency(
        self,
        *,
        operator_id: str,
        idempotency_key_fingerprint: str,
        v042_enqueue_valid_until: str,
    ) -> QueueObservationReceiptV1 | None:
        try:
            with self._connect() as connection:
                reservation = connection.execute(
                    """SELECT * FROM queue_observation_receipt_reservations
                    WHERE operator_id = ? AND idempotency_key_fingerprint = ?""",
                    (operator_id, idempotency_key_fingerprint),
                ).fetchone()
                if reservation is None:
                    return None
                if reservation["v042_enqueue_valid_until"] != v042_enqueue_valid_until:
                    raise QueueObservationReceiptStoreError("conflict")
                row = connection.execute(
                    """SELECT * FROM queue_observation_receipts
                    WHERE operator_id = ? AND receipt_id = ?""",
                    (operator_id, reservation["receipt_id"]),
                ).fetchone()
        except QueueObservationReceiptStoreError:
            raise
        except sqlite3.Error as error:
            raise QueueObservationReceiptStoreError("unavailable") from error
        self._validate_reservation(reservation, operator_id=operator_id)
        if row is None:
            raise QueueObservationReceiptStoreError("append_indeterminate")
        return self._decode_record(row, reservation, operator_id=operator_id)

    def append(
        self,
        *,
        record: QueueObservationReceiptV1,
        idempotency_reservation: QueueObservationReceiptIdempotencyReservationV1,
        subject_reservation: QueueObservationReceiptSubjectReservationV1,
        audit_evidence: QueueObservationReceiptAuditEvidenceV1,
        v042_enqueue_valid_until: str,
        force_indeterminate: bool = False,
    ) -> tuple[QueueObservationReceiptV1, bool]:
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
            raise QueueObservationReceiptStoreError("record_too_large")
        self._reserve_attempt(
            record=record,
            idempotency_reservation=idempotency_reservation,
            subject_reservation=subject_reservation,
            v042_enqueue_valid_until=v042_enqueue_valid_until,
        )
        if force_indeterminate:
            self.mark_indeterminate(
                operator_id=record.operator_id,
                receipt_id=record.receipt_id,
                audit_evidence=audit_evidence,
            )
            raise QueueObservationReceiptStoreError("append_indeterminate")
        return self._append_record(
            record=record,
            subject_reservation=subject_reservation,
            audit_json=audit_json,
        )

    def mark_indeterminate(
        self,
        *,
        operator_id: str,
        receipt_id: str,
        audit_evidence: QueueObservationReceiptAuditEvidenceV1,
    ) -> None:
        audit_json = audit_evidence.model_dump_json()
        if len(audit_json.encode()) > self.max_model_bytes:
            raise QueueObservationReceiptStoreError("record_too_large")
        try:
            with self._connect() as connection:
                connection.execute("BEGIN IMMEDIATE")
                row = connection.execute(
                    """SELECT * FROM queue_observation_receipt_reservations
                    WHERE operator_id = ? AND receipt_id = ?""",
                    (operator_id, receipt_id),
                ).fetchone()
                if row is None:
                    raise QueueObservationReceiptStoreError("not_found")
                connection.execute(
                    """INSERT INTO queue_observation_receipt_attempts (
                    operator_id, receipt_id, audit_fingerprint, audit_json
                    ) VALUES (?, ?, ?, ?)""",
                    (
                        operator_id,
                        receipt_id,
                        audit_evidence.audit_fingerprint.value,
                        audit_json,
                    ),
                )
                connection.execute("COMMIT")
        except QueueObservationReceiptStoreError:
            raise
        except sqlite3.Error as error:
            raise QueueObservationReceiptStoreError("unavailable") from error

    def get(self, *, operator_id: str, receipt_id: str) -> QueueObservationReceiptV1:
        try:
            with self._connect() as connection:
                row = connection.execute(
                    """SELECT * FROM queue_observation_receipts
                    WHERE operator_id = ? AND receipt_id = ?""",
                    (operator_id, receipt_id),
                ).fetchone()
                reservation = connection.execute(
                    """SELECT * FROM queue_observation_receipt_reservations
                    WHERE operator_id = ? AND receipt_id = ?""",
                    (operator_id, receipt_id),
                ).fetchone()
        except sqlite3.Error as error:
            raise QueueObservationReceiptStoreError("unavailable") from error
        if row is None or reservation is None:
            raise QueueObservationReceiptStoreError("not_found")
        return self._decode_record(row, reservation, operator_id=operator_id)

    def list_owned(
        self, *, operator_id: str, candidate_record_id: str
    ) -> tuple[QueueObservationReceiptV1, ...]:
        try:
            with self._connect() as connection:
                rows = connection.execute(
                    """SELECT * FROM queue_observation_receipts
                    WHERE operator_id = ? AND candidate_record_id = ?
                    ORDER BY recorded_at ASC, receipt_id ASC
                    LIMIT ?""",
                    (
                        operator_id,
                        candidate_record_id,
                        self.max_records_per_operator + 1,
                    ),
                ).fetchall()
                reservations = {
                    row["receipt_id"]: row
                    for row in connection.execute(
                        """SELECT * FROM queue_observation_receipt_reservations
                        WHERE operator_id = ?""",
                        (operator_id,),
                    ).fetchall()
                }
        except sqlite3.Error as error:
            raise QueueObservationReceiptStoreError("unavailable") from error
        if len(rows) > self.max_records_per_operator:
            raise QueueObservationReceiptStoreError("quota_exceeded")
        return tuple(
            self._decode_record(
                row, reservations.get(row["receipt_id"]), operator_id=operator_id
            )
            for row in rows
        )

    def _reserve_attempt(
        self,
        *,
        record: QueueObservationReceiptV1,
        idempotency_reservation: QueueObservationReceiptIdempotencyReservationV1,
        subject_reservation: QueueObservationReceiptSubjectReservationV1,
        v042_enqueue_valid_until: str,
    ) -> None:
        idempotency_json = idempotency_reservation.model_dump_json()
        reservation_json = subject_reservation.model_dump_json()
        try:
            with self._connect() as connection:
                connection.execute("BEGIN IMMEDIATE")
                rows = connection.execute(
                    """SELECT * FROM queue_observation_receipt_reservations
                    WHERE operator_id = ?
                    AND (idempotency_key_fingerprint = ?
                    OR subject_fingerprint = ?
                    OR receipt_id = ?
                    OR receipt_record_fingerprint = ?)""",
                    (
                        record.operator_id,
                        idempotency_reservation.idempotency_key_fingerprint.value,
                        record.subject_fingerprint.value,
                        record.receipt_id,
                        record.receipt_record_fingerprint.value,
                    ),
                ).fetchall()
                if rows:
                    if len(rows) != 1 or not self._is_exact_reservation(
                        rows[0],
                        record,
                        idempotency_reservation,
                        subject_reservation,
                        v042_enqueue_valid_until,
                    ):
                        raise QueueObservationReceiptStoreError("conflict")
                    existing = connection.execute(
                        """SELECT 1 FROM queue_observation_receipts
                        WHERE operator_id = ? AND receipt_id = ?""",
                        (record.operator_id, record.receipt_id),
                    ).fetchone()
                    if existing is None:
                        raise QueueObservationReceiptStoreError("append_indeterminate")
                    connection.execute("COMMIT")
                    return
                count = connection.execute(
                    """SELECT COUNT(*) FROM queue_observation_receipt_reservations
                    WHERE operator_id = ?""",
                    (record.operator_id,),
                ).fetchone()[0]
                if count >= self.max_records_per_operator:
                    raise QueueObservationReceiptStoreError("quota_exceeded")
                connection.execute(
                    """INSERT INTO queue_observation_receipt_reservations (
                    operator_id, candidate_record_id, receipt_id,
                    idempotency_key_fingerprint, request_fingerprint,
                    subject_fingerprint, receipt_record_fingerprint,
                    v042_enqueue_valid_until, reserved_at, idempotency_json,
                    reservation_json, attempt_started
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        record.operator_id,
                        record.candidate_record_id,
                        record.receipt_id,
                        idempotency_reservation.idempotency_key_fingerprint.value,
                        idempotency_reservation.request_fingerprint.value,
                        record.subject_fingerprint.value,
                        record.receipt_record_fingerprint.value,
                        v042_enqueue_valid_until,
                        record.recorded_at,
                        idempotency_json,
                        reservation_json,
                        "true",
                    ),
                )
                connection.execute("COMMIT")
        except QueueObservationReceiptStoreError:
            raise
        except sqlite3.IntegrityError as error:
            raise QueueObservationReceiptStoreError("conflict") from error
        except sqlite3.Error as error:
            raise QueueObservationReceiptStoreError("unavailable") from error

    def _append_record(
        self,
        *,
        record: QueueObservationReceiptV1,
        subject_reservation: QueueObservationReceiptSubjectReservationV1,
        audit_json: str,
    ) -> tuple[QueueObservationReceiptV1, bool]:
        try:
            with self._connect() as connection:
                connection.execute("BEGIN IMMEDIATE")
                row = connection.execute(
                    """SELECT * FROM queue_observation_receipts
                    WHERE operator_id = ? AND receipt_id = ?""",
                    (record.operator_id, record.receipt_id),
                ).fetchone()
                reservation = connection.execute(
                    """SELECT * FROM queue_observation_receipt_reservations
                    WHERE operator_id = ? AND receipt_id = ?""",
                    (record.operator_id, record.receipt_id),
                ).fetchone()
                if reservation is None:
                    raise QueueObservationReceiptStoreError(
                        "reservation_before_effect_failed"
                    )
                if row is not None:
                    existing = self._decode_record(
                        row, reservation, operator_id=record.operator_id
                    )
                    connection.execute("COMMIT")
                    return existing, False
                connection.execute(
                    """INSERT INTO queue_observation_receipts (
                    operator_id, receipt_id, candidate_record_id,
                    idempotency_key_fingerprint, request_fingerprint,
                    subject_fingerprint, receipt_record_fingerprint, enqueue_id,
                    enqueue_record_fingerprint, enqueue_status_fingerprint,
                    queue_item_fingerprint, lineage_fingerprint, recorded_at,
                    valid_until, record_json, audit_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        record.operator_id,
                        record.receipt_id,
                        record.candidate_record_id,
                        subject_reservation.idempotency_key_fingerprint.value,
                        subject_reservation.request_fingerprint.value,
                        record.subject_fingerprint.value,
                        record.receipt_record_fingerprint.value,
                        record.v042_enqueue.enqueue_id,
                        record.v042_enqueue.record_fingerprint.value,
                        record.v042_enqueue_status.status_fingerprint.value,
                        record.v042_enqueue.queue_item.item_fingerprint.value,
                        record.lineage_fingerprint.value,
                        record.recorded_at,
                        record.valid_until,
                        record.model_dump_json(),
                        audit_json,
                    ),
                )
                connection.execute("COMMIT")
                return record, True
        except QueueObservationReceiptStoreError:
            raise
        except sqlite3.IntegrityError as error:
            raise QueueObservationReceiptStoreError("conflict") from error
        except sqlite3.Error as error:
            raise QueueObservationReceiptStoreError("unavailable") from error

    @staticmethod
    def _is_exact_reservation(
        row: sqlite3.Row,
        record: QueueObservationReceiptV1,
        idempotency_reservation: QueueObservationReceiptIdempotencyReservationV1,
        subject_reservation: QueueObservationReceiptSubjectReservationV1,
        v042_enqueue_valid_until: str,
    ) -> bool:
        return (
            row["operator_id"] == record.operator_id == subject_reservation.operator_id
            and row["operator_id"] == idempotency_reservation.operator_id
            and row["candidate_record_id"]
            == record.candidate_record_id
            == subject_reservation.candidate_record_id
            == idempotency_reservation.candidate_record_id
            and row["receipt_id"]
            == record.receipt_id
            == subject_reservation.receipt_id
            == idempotency_reservation.receipt_id
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
            and row["receipt_record_fingerprint"]
            == record.receipt_record_fingerprint.value
            == idempotency_reservation.receipt_record_fingerprint.value
            == subject_reservation.receipt_record_fingerprint.value
            and row["v042_enqueue_valid_until"] == v042_enqueue_valid_until
            and row["reserved_at"] == record.recorded_at
            and row["idempotency_json"] == idempotency_reservation.model_dump_json()
            and row["reservation_json"] == subject_reservation.model_dump_json()
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
            idempotency = QueueObservationReceiptIdempotencyReservationV1.model_validate_json(
                row["idempotency_json"]
            )
            reservation = QueueObservationReceiptSubjectReservationV1.model_validate_json(
                row["reservation_json"]
            )
            if (
                reservation.reservation_fingerprint
                != reservation_fingerprint(reservation)
                or row["attempt_started"] != "true"
                or not self._is_row_reservation_exact(row, idempotency, reservation)
            ):
                raise ValueError("persisted reservation mismatch")
        except Exception as error:
            raise QueueObservationReceiptStoreError("store_corrupt") from error

    @staticmethod
    def _is_row_reservation_exact(
        row: sqlite3.Row,
        idempotency: QueueObservationReceiptIdempotencyReservationV1,
        reservation: QueueObservationReceiptSubjectReservationV1,
    ) -> bool:
        return (
            row["operator_id"] == idempotency.operator_id == reservation.operator_id
            and row["candidate_record_id"]
            == idempotency.candidate_record_id
            == reservation.candidate_record_id
            and row["receipt_id"] == idempotency.receipt_id == reservation.receipt_id
            and row["idempotency_key_fingerprint"]
            == idempotency.idempotency_key_fingerprint.value
            == reservation.idempotency_key_fingerprint.value
            and row["request_fingerprint"]
            == idempotency.request_fingerprint.value
            == reservation.request_fingerprint.value
            and row["subject_fingerprint"]
            == idempotency.subject_fingerprint.value
            == reservation.subject_fingerprint.value
            and row["receipt_record_fingerprint"]
            == idempotency.receipt_record_fingerprint.value
            == reservation.receipt_record_fingerprint.value
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
    ) -> QueueObservationReceiptV1:
        try:
            self._validate_reservation(reservation_row, operator_id=operator_id)
            if row is None:
                raise ValueError("record missing")
            payloads = (row["record_json"], row["audit_json"])
            if max(len(value.encode()) for value in payloads) > self.max_model_bytes:
                raise ValueError("persisted record exceeds bound")
            record = QueueObservationReceiptV1.model_validate_json(row["record_json"])
            audit = QueueObservationReceiptAuditEvidenceV1.model_validate_json(
                row["audit_json"]
            )
            if (
                operator_id != row["operator_id"]
                or record.receipt_record_fingerprint != receipt_record_fingerprint(record)
                or audit.audit_fingerprint != audit_fingerprint(audit)
                or row["operator_id"] != record.operator_id
                or row["candidate_record_id"] != record.candidate_record_id
                or row["receipt_id"] != record.receipt_id
                or row["idempotency_key_fingerprint"]
                != reservation_row["idempotency_key_fingerprint"]
                or row["request_fingerprint"] != reservation_row["request_fingerprint"]
                or row["subject_fingerprint"] != record.subject_fingerprint.value
                or row["receipt_record_fingerprint"]
                != record.receipt_record_fingerprint.value
                or row["enqueue_id"] != record.v042_enqueue.enqueue_id
                or row["enqueue_record_fingerprint"]
                != record.v042_enqueue.record_fingerprint.value
                or row["enqueue_status_fingerprint"]
                != record.v042_enqueue_status.status_fingerprint.value
                or row["queue_item_fingerprint"]
                != record.v042_enqueue.queue_item.item_fingerprint.value
                or row["lineage_fingerprint"] != record.lineage_fingerprint.value
                or row["recorded_at"] != record.recorded_at
                or row["valid_until"] != record.valid_until
                or audit.event != "queue_observation_receipt_recorded"
                or audit.outcome != "recorded"
                or audit.operator_id != record.operator_id
                or audit.candidate_record_id != record.candidate_record_id
                or audit.receipt_id != record.receipt_id
                or audit.subject_fingerprint != record.subject_fingerprint
                or audit.receipt_record_fingerprint != record.receipt_record_fingerprint
                or audit.occurred_at != record.recorded_at
            ):
                raise ValueError("persisted record mismatch")
            return record
        except QueueObservationReceiptStoreError:
            raise
        except Exception as error:
            raise QueueObservationReceiptStoreError("store_corrupt") from error
