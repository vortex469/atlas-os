"""Durable store for v0.45 one-shot controlled dequeue reservations.

The store can reserve and audit a single-use dequeue subject, but it has no
queue client, dequeue operation, polling, worker, Agent, or execution API.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from .contract import (
    MAX_MODEL_BYTES,
    OneShotControlledDequeueAuditEvidenceV1,
    OneShotControlledDequeueIdempotencyReservationV1,
    OneShotControlledDequeueReceiptV1,
    OneShotControlledDequeueSubjectReservationV1,
    audit_fingerprint,
    dequeue_record_fingerprint,
    reservation_fingerprint,
)

MAX_RECORDS_PER_OPERATOR = 16


class OneShotControlledDequeueStoreError(RuntimeError):
    """Closed storage failure without database or record disclosure."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


class OneShotControlledDequeueStore:
    """SQLite reservations and evidence; no live dequeue effect methods exist."""

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
                    CREATE TABLE IF NOT EXISTS one_shot_controlled_dequeue_reservations (
                        operator_id TEXT NOT NULL,
                        candidate_record_id TEXT NOT NULL,
                        dequeue_id TEXT NOT NULL,
                        idempotency_key_fingerprint TEXT NOT NULL,
                        request_fingerprint TEXT NOT NULL,
                        dequeue_subject_fingerprint TEXT NOT NULL,
                        controlled_dequeue_admission_valid_until TEXT NOT NULL,
                        reserved_at TEXT NOT NULL,
                        idempotency_json TEXT NOT NULL,
                        reservation_json TEXT NOT NULL,
                        reservation_state TEXT NOT NULL,
                        permanent TEXT NOT NULL,
                        PRIMARY KEY (operator_id, dequeue_id),
                        UNIQUE (operator_id, idempotency_key_fingerprint),
                        UNIQUE (operator_id, dequeue_subject_fingerprint)
                    )
                    """
                )
                connection.execute(
                    """
                    CREATE TABLE IF NOT EXISTS one_shot_controlled_dequeue_attempts (
                        operator_id TEXT NOT NULL,
                        dequeue_id TEXT NOT NULL,
                        audit_fingerprint TEXT NOT NULL,
                        audit_json TEXT NOT NULL,
                        PRIMARY KEY (operator_id, dequeue_id, audit_fingerprint),
                        FOREIGN KEY (operator_id, dequeue_id)
                            REFERENCES one_shot_controlled_dequeue_reservations(
                                operator_id, dequeue_id
                            )
                    )
                    """
                )
                connection.execute(
                    """
                    CREATE TABLE IF NOT EXISTS one_shot_controlled_dequeue_records (
                        operator_id TEXT NOT NULL,
                        dequeue_id TEXT NOT NULL,
                        candidate_record_id TEXT NOT NULL,
                        idempotency_key_fingerprint TEXT NOT NULL,
                        request_fingerprint TEXT NOT NULL,
                        dequeue_subject_fingerprint TEXT NOT NULL,
                        dequeue_record_fingerprint TEXT NOT NULL,
                        admission_id TEXT NOT NULL,
                        admission_record_fingerprint TEXT NOT NULL,
                        admission_status_fingerprint TEXT NOT NULL,
                        queue_item_fingerprint TEXT NOT NULL,
                        lineage_fingerprint TEXT NOT NULL,
                        recorded_at TEXT NOT NULL,
                        valid_until TEXT NOT NULL,
                        record_json TEXT NOT NULL,
                        audit_json TEXT NOT NULL,
                        PRIMARY KEY (operator_id, dequeue_id),
                        UNIQUE (operator_id, dequeue_record_fingerprint),
                        FOREIGN KEY (operator_id, dequeue_id)
                            REFERENCES one_shot_controlled_dequeue_reservations(
                                operator_id, dequeue_id
                            )
                    )
                    """
                )
        except sqlite3.Error as error:
            raise OneShotControlledDequeueStoreError("unavailable") from error

    def resolve_idempotency(
        self,
        *,
        operator_id: str,
        idempotency_key_fingerprint: str,
        request_fingerprint: str,
        controlled_dequeue_admission_valid_until: str,
    ) -> OneShotControlledDequeueReceiptV1 | None:
        try:
            with self._connect() as connection:
                reservation = connection.execute(
                    """SELECT * FROM one_shot_controlled_dequeue_reservations
                    WHERE operator_id = ? AND idempotency_key_fingerprint = ?""",
                    (operator_id, idempotency_key_fingerprint),
                ).fetchone()
                if reservation is None:
                    return None
                if (
                    reservation["controlled_dequeue_admission_valid_until"]
                    != controlled_dequeue_admission_valid_until
                    or reservation["request_fingerprint"] != request_fingerprint
                ):
                    raise OneShotControlledDequeueStoreError("idempotency_conflict")
                row = connection.execute(
                    """SELECT * FROM one_shot_controlled_dequeue_records
                    WHERE operator_id = ? AND dequeue_id = ?""",
                    (operator_id, reservation["dequeue_id"]),
                ).fetchone()
        except OneShotControlledDequeueStoreError:
            raise
        except sqlite3.Error as error:
            raise OneShotControlledDequeueStoreError("unavailable") from error
        self._validate_reservation(reservation, operator_id=operator_id)
        if row is None:
            raise OneShotControlledDequeueStoreError("dequeue_adapter_unavailable")
        return self._decode_record(row, reservation, operator_id=operator_id)

    def reserve_attempt(
        self,
        *,
        idempotency_reservation: OneShotControlledDequeueIdempotencyReservationV1,
        subject_reservation: OneShotControlledDequeueSubjectReservationV1,
        audit_evidence: OneShotControlledDequeueAuditEvidenceV1,
        controlled_dequeue_admission_valid_until: str,
    ) -> None:
        idempotency_json = idempotency_reservation.model_dump_json()
        reservation_json = subject_reservation.model_dump_json()
        audit_json = audit_evidence.model_dump_json()
        if (
            max(
                len(value.encode())
                for value in (idempotency_json, reservation_json, audit_json)
            )
            > self.max_model_bytes
        ):
            raise OneShotControlledDequeueStoreError("record_too_large")
        try:
            with self._connect() as connection:
                connection.execute("BEGIN IMMEDIATE")
                rows = connection.execute(
                    """SELECT * FROM one_shot_controlled_dequeue_reservations
                    WHERE operator_id = ?
                    AND (idempotency_key_fingerprint = ?
                    OR dequeue_subject_fingerprint = ?
                    OR dequeue_id = ?)""",
                    (
                        subject_reservation.operator_id,
                        idempotency_reservation.idempotency_key_fingerprint.value,
                        subject_reservation.dequeue_subject_fingerprint.value,
                        subject_reservation.dequeue_id,
                    ),
                ).fetchall()
                if rows:
                    if len(rows) != 1:
                        raise OneShotControlledDequeueStoreError("conflict")
                    row = rows[0]
                    if not self._is_exact_reservation(
                        row,
                        idempotency_reservation,
                        subject_reservation,
                        controlled_dequeue_admission_valid_until,
                    ):
                        if (
                            row["idempotency_key_fingerprint"]
                            == idempotency_reservation.idempotency_key_fingerprint.value
                        ):
                            raise OneShotControlledDequeueStoreError(
                                "idempotency_conflict"
                            )
                        raise OneShotControlledDequeueStoreError(
                            "permanent_subject_reserved"
                        )
                    self._insert_attempt(connection, subject_reservation, audit_json, audit_evidence)
                    connection.execute("COMMIT")
                    return
                count = connection.execute(
                    """SELECT COUNT(*) FROM one_shot_controlled_dequeue_reservations
                    WHERE operator_id = ?""",
                    (subject_reservation.operator_id,),
                ).fetchone()[0]
                if count >= self.max_records_per_operator:
                    raise OneShotControlledDequeueStoreError("quota_exceeded")
                connection.execute(
                    """INSERT INTO one_shot_controlled_dequeue_reservations (
                    operator_id, candidate_record_id, dequeue_id,
                    idempotency_key_fingerprint, request_fingerprint,
                    dequeue_subject_fingerprint,
                    controlled_dequeue_admission_valid_until, reserved_at,
                    idempotency_json, reservation_json, reservation_state, permanent
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        subject_reservation.operator_id,
                        subject_reservation.candidate_record_id,
                        subject_reservation.dequeue_id,
                        idempotency_reservation.idempotency_key_fingerprint.value,
                        idempotency_reservation.request_fingerprint.value,
                        subject_reservation.dequeue_subject_fingerprint.value,
                        controlled_dequeue_admission_valid_until,
                        subject_reservation.reserved_at,
                        idempotency_json,
                        reservation_json,
                        "reserved",
                        "true",
                    ),
                )
                self._insert_attempt(connection, subject_reservation, audit_json, audit_evidence)
                connection.execute("COMMIT")
        except OneShotControlledDequeueStoreError:
            raise
        except sqlite3.IntegrityError as error:
            raise OneShotControlledDequeueStoreError("conflict") from error
        except sqlite3.Error as error:
            raise OneShotControlledDequeueStoreError("unavailable") from error

    def append_receipt(
        self,
        *,
        record: OneShotControlledDequeueReceiptV1,
        audit_evidence: OneShotControlledDequeueAuditEvidenceV1,
    ) -> OneShotControlledDequeueReceiptV1:
        record_json = record.model_dump_json()
        audit_json = audit_evidence.model_dump_json()
        if max(len(value.encode()) for value in (record_json, audit_json)) > self.max_model_bytes:
            raise OneShotControlledDequeueStoreError("record_too_large")
        try:
            with self._connect() as connection:
                connection.execute("BEGIN IMMEDIATE")
                row = connection.execute(
                    """SELECT * FROM one_shot_controlled_dequeue_records
                    WHERE operator_id = ? AND dequeue_id = ?""",
                    (record.operator_id, record.dequeue_id),
                ).fetchone()
                reservation = connection.execute(
                    """SELECT * FROM one_shot_controlled_dequeue_reservations
                    WHERE operator_id = ? AND dequeue_id = ?""",
                    (record.operator_id, record.dequeue_id),
                ).fetchone()
                if reservation is None:
                    raise OneShotControlledDequeueStoreError(
                        "reservation_before_effect_failed"
                    )
                self._validate_reservation(reservation, operator_id=record.operator_id)
                if (
                    reservation["dequeue_subject_fingerprint"]
                    != record.subject_fingerprint.value
                    or reservation["idempotency_key_fingerprint"]
                    != record.idempotency_key_fingerprint.value
                ):
                    raise OneShotControlledDequeueStoreError(
                        "reservation_before_effect_failed"
                    )
                if row is not None:
                    existing = self._decode_record(
                        row, reservation, operator_id=record.operator_id
                    )
                    if existing != record:
                        raise OneShotControlledDequeueStoreError(
                            "permanent_subject_reserved"
                        )
                    connection.execute("COMMIT")
                    return existing
                admission = record.controlled_dequeue_admission
                status = record.controlled_dequeue_admission_status
                item = admission.queue_observation_receipt.v042_enqueue.queue_item
                connection.execute(
                    """INSERT INTO one_shot_controlled_dequeue_records (
                    operator_id, dequeue_id, candidate_record_id,
                    idempotency_key_fingerprint, request_fingerprint,
                    dequeue_subject_fingerprint, dequeue_record_fingerprint,
                    admission_id, admission_record_fingerprint,
                    admission_status_fingerprint, queue_item_fingerprint,
                    lineage_fingerprint, recorded_at, valid_until, record_json,
                    audit_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        record.operator_id,
                        record.dequeue_id,
                        record.candidate_record_id,
                        record.idempotency_key_fingerprint.value,
                        reservation["request_fingerprint"],
                        record.subject_fingerprint.value,
                        record.dequeue_record_fingerprint.value,
                        admission.admission_id,
                        admission.admission_record_fingerprint.value,
                        status.status_fingerprint.value,
                        item.item_fingerprint.value,
                        record.lineage_fingerprint.value,
                        record.recorded_at,
                        record.valid_until,
                        record_json,
                        audit_json,
                    ),
                )
                connection.execute("COMMIT")
                return record
        except OneShotControlledDequeueStoreError:
            raise
        except sqlite3.IntegrityError as error:
            raise OneShotControlledDequeueStoreError("conflict") from error
        except sqlite3.Error as error:
            raise OneShotControlledDequeueStoreError("unavailable") from error

    def get(self, *, operator_id: str, dequeue_id: str) -> OneShotControlledDequeueReceiptV1:
        try:
            with self._connect() as connection:
                row = connection.execute(
                    """SELECT * FROM one_shot_controlled_dequeue_records
                    WHERE operator_id = ? AND dequeue_id = ?""",
                    (operator_id, dequeue_id),
                ).fetchone()
                reservation = connection.execute(
                    """SELECT * FROM one_shot_controlled_dequeue_reservations
                    WHERE operator_id = ? AND dequeue_id = ?""",
                    (operator_id, dequeue_id),
                ).fetchone()
        except sqlite3.Error as error:
            raise OneShotControlledDequeueStoreError("unavailable") from error
        if row is None or reservation is None:
            raise OneShotControlledDequeueStoreError("not_found")
        return self._decode_record(row, reservation, operator_id=operator_id)

    def get_reservation(
        self, *, operator_id: str, dequeue_id: str
    ) -> OneShotControlledDequeueSubjectReservationV1:
        try:
            with self._connect() as connection:
                row = connection.execute(
                    """SELECT * FROM one_shot_controlled_dequeue_reservations
                    WHERE operator_id = ? AND dequeue_id = ?""",
                    (operator_id, dequeue_id),
                ).fetchone()
        except sqlite3.Error as error:
            raise OneShotControlledDequeueStoreError("unavailable") from error
        if row is None:
            raise OneShotControlledDequeueStoreError("not_found")
        self._validate_reservation(row, operator_id=operator_id)
        return OneShotControlledDequeueSubjectReservationV1.model_validate_json(
            row["reservation_json"]
        )

    def list_attempts(
        self, *, operator_id: str, dequeue_id: str
    ) -> tuple[OneShotControlledDequeueAuditEvidenceV1, ...]:
        try:
            with self._connect() as connection:
                reservation = connection.execute(
                    """SELECT * FROM one_shot_controlled_dequeue_reservations
                    WHERE operator_id = ? AND dequeue_id = ?""",
                    (operator_id, dequeue_id),
                ).fetchone()
                rows = connection.execute(
                    """SELECT * FROM one_shot_controlled_dequeue_attempts
                    WHERE operator_id = ? AND dequeue_id = ?
                    ORDER BY audit_fingerprint ASC""",
                    (operator_id, dequeue_id),
                ).fetchall()
        except sqlite3.Error as error:
            raise OneShotControlledDequeueStoreError("unavailable") from error
        if reservation is None:
            raise OneShotControlledDequeueStoreError("not_found")
        self._validate_reservation(reservation, operator_id=operator_id)
        return tuple(self._decode_attempt(row, operator_id=operator_id) for row in rows)

    def list_owned(
        self, *, operator_id: str, candidate_record_id: str
    ) -> tuple[OneShotControlledDequeueReceiptV1, ...]:
        try:
            with self._connect() as connection:
                rows = connection.execute(
                    """SELECT * FROM one_shot_controlled_dequeue_records
                    WHERE operator_id = ? AND candidate_record_id = ?
                    ORDER BY recorded_at ASC, dequeue_id ASC
                    LIMIT ?""",
                    (
                        operator_id,
                        candidate_record_id,
                        self.max_records_per_operator + 1,
                    ),
                ).fetchall()
                reservations = {
                    row["dequeue_id"]: row
                    for row in connection.execute(
                        """SELECT * FROM one_shot_controlled_dequeue_reservations
                        WHERE operator_id = ?""",
                        (operator_id,),
                    ).fetchall()
                }
        except sqlite3.Error as error:
            raise OneShotControlledDequeueStoreError("unavailable") from error
        if len(rows) > self.max_records_per_operator:
            raise OneShotControlledDequeueStoreError("quota_exceeded")
        return tuple(
            self._decode_record(
                row, reservations.get(row["dequeue_id"]), operator_id=operator_id
            )
            for row in rows
        )

    @staticmethod
    def _insert_attempt(
        connection: sqlite3.Connection,
        subject_reservation: OneShotControlledDequeueSubjectReservationV1,
        audit_json: str,
        audit_evidence: OneShotControlledDequeueAuditEvidenceV1,
    ) -> None:
        connection.execute(
            """INSERT OR IGNORE INTO one_shot_controlled_dequeue_attempts (
            operator_id, dequeue_id, audit_fingerprint, audit_json
            ) VALUES (?, ?, ?, ?)""",
            (
                subject_reservation.operator_id,
                subject_reservation.dequeue_id,
                audit_evidence.audit_fingerprint.value,
                audit_json,
            ),
        )

    @staticmethod
    def _is_exact_reservation(
        row: sqlite3.Row,
        idempotency: OneShotControlledDequeueIdempotencyReservationV1,
        reservation: OneShotControlledDequeueSubjectReservationV1,
        controlled_dequeue_admission_valid_until: str,
    ) -> bool:
        return (
            row["operator_id"] == idempotency.operator_id == reservation.operator_id
            and row["candidate_record_id"]
            == idempotency.candidate_record_id
            == reservation.candidate_record_id
            and row["dequeue_id"] == idempotency.dequeue_id == reservation.dequeue_id
            and row["idempotency_key_fingerprint"]
            == idempotency.idempotency_key_fingerprint.value
            == reservation.idempotency_key_fingerprint.value
            and row["request_fingerprint"]
            == idempotency.request_fingerprint.value
            == reservation.request_fingerprint.value
            and row["dequeue_subject_fingerprint"]
            == idempotency.dequeue_subject_fingerprint.value
            == reservation.dequeue_subject_fingerprint.value
            and row["controlled_dequeue_admission_valid_until"]
            == controlled_dequeue_admission_valid_until
            and row["reserved_at"] == idempotency.reserved_at == reservation.reserved_at
            and row["idempotency_json"] == idempotency.model_dump_json()
            and row["reservation_json"] == reservation.model_dump_json()
            and row["reservation_state"] == "reserved"
            and row["permanent"] == "true"
        )

    def _validate_reservation(
        self, row: sqlite3.Row | None, *, operator_id: str
    ) -> None:
        try:
            if row is None or row["operator_id"] != operator_id:
                raise ValueError("reservation missing")
            payloads = (row["idempotency_json"], row["reservation_json"])
            if max(len(value.encode()) for value in payloads) > self.max_model_bytes:
                raise ValueError("persisted reservation exceeds bound")
            idempotency = (
                OneShotControlledDequeueIdempotencyReservationV1.model_validate_json(
                    row["idempotency_json"]
                )
            )
            reservation = (
                OneShotControlledDequeueSubjectReservationV1.model_validate_json(
                    row["reservation_json"]
                )
            )
            if (
                reservation.reservation_fingerprint
                != reservation_fingerprint(reservation)
                or not self._is_row_reservation_exact(row, idempotency, reservation)
            ):
                raise ValueError("persisted reservation mismatch")
        except Exception as error:
            raise OneShotControlledDequeueStoreError("store_corrupt") from error

    @staticmethod
    def _is_row_reservation_exact(
        row: sqlite3.Row,
        idempotency: OneShotControlledDequeueIdempotencyReservationV1,
        reservation: OneShotControlledDequeueSubjectReservationV1,
    ) -> bool:
        return (
            row["operator_id"] == idempotency.operator_id == reservation.operator_id
            and row["candidate_record_id"]
            == idempotency.candidate_record_id
            == reservation.candidate_record_id
            and row["dequeue_id"] == idempotency.dequeue_id == reservation.dequeue_id
            and row["idempotency_key_fingerprint"]
            == idempotency.idempotency_key_fingerprint.value
            == reservation.idempotency_key_fingerprint.value
            and row["request_fingerprint"]
            == idempotency.request_fingerprint.value
            == reservation.request_fingerprint.value
            and row["dequeue_subject_fingerprint"]
            == idempotency.dequeue_subject_fingerprint.value
            == reservation.dequeue_subject_fingerprint.value
            and row["reserved_at"] == idempotency.reserved_at == reservation.reserved_at
            and row["idempotency_json"] == idempotency.model_dump_json()
            and row["reservation_json"] == reservation.model_dump_json()
            and row["reservation_state"] == "reserved"
            and row["permanent"] == "true"
        )

    def _decode_attempt(
        self, row: sqlite3.Row, *, operator_id: str
    ) -> OneShotControlledDequeueAuditEvidenceV1:
        try:
            if row["operator_id"] != operator_id:
                raise ValueError("foreign attempt")
            if len(row["audit_json"].encode()) > self.max_model_bytes:
                raise ValueError("persisted attempt exceeds bound")
            audit = OneShotControlledDequeueAuditEvidenceV1.model_validate_json(
                row["audit_json"]
            )
            if (
                audit.audit_fingerprint != audit_fingerprint(audit)
                or audit.operator_id != operator_id
                or audit.dequeue_id != row["dequeue_id"]
                or audit.audit_fingerprint.value != row["audit_fingerprint"]
            ):
                raise ValueError("persisted attempt mismatch")
            return audit
        except Exception as error:
            raise OneShotControlledDequeueStoreError("store_corrupt") from error

    def _decode_record(
        self,
        row: sqlite3.Row,
        reservation_row: sqlite3.Row | None,
        *,
        operator_id: str,
    ) -> OneShotControlledDequeueReceiptV1:
        try:
            self._validate_reservation(reservation_row, operator_id=operator_id)
            payloads = (row["record_json"], row["audit_json"])
            if max(len(value.encode()) for value in payloads) > self.max_model_bytes:
                raise ValueError("persisted record exceeds bound")
            record = OneShotControlledDequeueReceiptV1.model_validate_json(
                row["record_json"]
            )
            audit = OneShotControlledDequeueAuditEvidenceV1.model_validate_json(
                row["audit_json"]
            )
            admission = record.controlled_dequeue_admission
            status = record.controlled_dequeue_admission_status
            item = admission.queue_observation_receipt.v042_enqueue.queue_item
            if (
                operator_id != row["operator_id"]
                or record.dequeue_record_fingerprint
                != dequeue_record_fingerprint(record)
                or audit.audit_fingerprint != audit_fingerprint(audit)
                or row["operator_id"] != record.operator_id
                or row["candidate_record_id"] != record.candidate_record_id
                or row["dequeue_id"] != record.dequeue_id
                or row["idempotency_key_fingerprint"]
                != reservation_row["idempotency_key_fingerprint"]
                or row["request_fingerprint"] != reservation_row["request_fingerprint"]
                or row["dequeue_subject_fingerprint"]
                != reservation_row["dequeue_subject_fingerprint"]
                or row["dequeue_record_fingerprint"]
                != record.dequeue_record_fingerprint.value
                or row["admission_id"] != admission.admission_id
                or row["admission_record_fingerprint"]
                != admission.admission_record_fingerprint.value
                or row["admission_status_fingerprint"] != status.status_fingerprint.value
                or row["queue_item_fingerprint"] != item.item_fingerprint.value
                or row["lineage_fingerprint"] != record.lineage_fingerprint.value
                or row["recorded_at"] != record.recorded_at
                or row["valid_until"] != record.valid_until
                or audit.event != "one_shot_controlled_dequeue_recorded"
                or audit.outcome != "recorded"
                or audit.operator_id != record.operator_id
                or audit.candidate_record_id != record.candidate_record_id
                or audit.dequeue_id != record.dequeue_id
                or audit.dequeue_record_fingerprint
                != record.dequeue_record_fingerprint
                or audit.occurred_at != record.recorded_at
            ):
                raise ValueError("persisted record mismatch")
            return record
        except OneShotControlledDequeueStoreError:
            raise
        except Exception as error:
            raise OneShotControlledDequeueStoreError("store_corrupt") from error
