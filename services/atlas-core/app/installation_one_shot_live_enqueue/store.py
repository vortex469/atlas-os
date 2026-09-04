"""Durable append-only store for v0.42 one-shot live enqueue evidence."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from .contract import (
    MAX_MODEL_BYTES,
    OneShotLiveEnqueueAuditEvidenceV1,
    OneShotLiveEnqueueIdempotencyReservationV1,
    OneShotLiveEnqueueSubjectReservationV1,
    OneShotLiveEnqueueV1,
    audit_fingerprint,
    record_fingerprint,
    reservation_fingerprint,
)

MAX_RECORDS_PER_OPERATOR = 16


class OneShotLiveEnqueueStoreError(RuntimeError):
    """Closed storage failure without database or record disclosure."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


class OneShotLiveEnqueueStore:
    """SQLite reservations and records; no queue, dequeue, worker, or effect API."""

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
                    CREATE TABLE IF NOT EXISTS one_shot_live_enqueue_reservations (
                        operator_id TEXT NOT NULL,
                        candidate_record_id TEXT NOT NULL,
                        enqueue_id TEXT NOT NULL,
                        idempotency_key_fingerprint TEXT NOT NULL,
                        request_fingerprint TEXT NOT NULL,
                        item_subject_fingerprint TEXT NOT NULL,
                        record_fingerprint TEXT NOT NULL,
                        live_enqueue_admission_valid_until TEXT NOT NULL,
                        reserved_at TEXT NOT NULL,
                        idempotency_json TEXT NOT NULL,
                        reservation_json TEXT NOT NULL,
                        attempt_started TEXT NOT NULL,
                        PRIMARY KEY (operator_id, enqueue_id),
                        UNIQUE (operator_id, idempotency_key_fingerprint),
                        UNIQUE (operator_id, item_subject_fingerprint),
                        UNIQUE (operator_id, record_fingerprint)
                    )
                    """
                )
                connection.execute(
                    """
                    CREATE TABLE IF NOT EXISTS one_shot_live_enqueue_attempts (
                        operator_id TEXT NOT NULL,
                        enqueue_id TEXT NOT NULL,
                        audit_fingerprint TEXT NOT NULL,
                        audit_json TEXT NOT NULL,
                        PRIMARY KEY (operator_id, enqueue_id, audit_fingerprint),
                        FOREIGN KEY (operator_id, enqueue_id)
                            REFERENCES one_shot_live_enqueue_reservations(
                                operator_id, enqueue_id
                            )
                    )
                    """
                )
                connection.execute(
                    """
                    CREATE TABLE IF NOT EXISTS one_shot_live_enqueue_records (
                        operator_id TEXT NOT NULL,
                        enqueue_id TEXT NOT NULL,
                        candidate_record_id TEXT NOT NULL,
                        idempotency_key_fingerprint TEXT NOT NULL,
                        request_fingerprint TEXT NOT NULL,
                        item_subject_fingerprint TEXT NOT NULL,
                        record_fingerprint TEXT NOT NULL,
                        live_enqueue_admission_fingerprint TEXT NOT NULL,
                        live_enqueue_admission_status_fingerprint TEXT NOT NULL,
                        worker_queue_reservation_fingerprint TEXT NOT NULL,
                        worker_intake_admission_fingerprint TEXT NOT NULL,
                        worker_identity_fingerprint TEXT NOT NULL,
                        worker_intake_reference_fingerprint TEXT NOT NULL,
                        queue_intake_reference_fingerprint TEXT NOT NULL,
                        queue_item_reference_fingerprint TEXT NOT NULL,
                        inherited_limits_fingerprint TEXT NOT NULL,
                        recorded_at TEXT NOT NULL,
                        valid_until TEXT NOT NULL,
                        record_json TEXT NOT NULL,
                        audit_json TEXT NOT NULL,
                        PRIMARY KEY (operator_id, enqueue_id),
                        UNIQUE (operator_id, idempotency_key_fingerprint),
                        UNIQUE (operator_id, item_subject_fingerprint),
                        UNIQUE (operator_id, record_fingerprint),
                        FOREIGN KEY (operator_id, enqueue_id)
                            REFERENCES one_shot_live_enqueue_reservations(
                                operator_id, enqueue_id
                            )
                    )
                    """
                )
        except sqlite3.Error as error:
            raise OneShotLiveEnqueueStoreError("unavailable") from error

    def resolve_idempotency(
        self,
        *,
        operator_id: str,
        idempotency_key_fingerprint: str,
        live_enqueue_admission_valid_until: str,
    ) -> OneShotLiveEnqueueV1 | None:
        try:
            with self._connect() as connection:
                reservation = connection.execute(
                    """SELECT * FROM one_shot_live_enqueue_reservations
                    WHERE operator_id = ? AND idempotency_key_fingerprint = ?""",
                    (operator_id, idempotency_key_fingerprint),
                ).fetchone()
                if reservation is None:
                    return None
                if (
                    reservation["live_enqueue_admission_valid_until"]
                    != live_enqueue_admission_valid_until
                ):
                    raise OneShotLiveEnqueueStoreError("conflict")
                row = connection.execute(
                    """SELECT * FROM one_shot_live_enqueue_records
                    WHERE operator_id = ? AND enqueue_id = ?""",
                    (operator_id, reservation["enqueue_id"]),
                ).fetchone()
        except OneShotLiveEnqueueStoreError:
            raise
        except sqlite3.Error as error:
            raise OneShotLiveEnqueueStoreError("unavailable") from error
        self._validate_reservation(reservation, operator_id=operator_id)
        if row is None:
            raise OneShotLiveEnqueueStoreError("append_indeterminate")
        return self._decode_record(row, reservation, operator_id=operator_id)

    def append(
        self,
        *,
        record: OneShotLiveEnqueueV1,
        idempotency_reservation: OneShotLiveEnqueueIdempotencyReservationV1,
        subject_reservation: OneShotLiveEnqueueSubjectReservationV1,
        audit_evidence: OneShotLiveEnqueueAuditEvidenceV1,
        live_enqueue_admission_valid_until: str,
        force_indeterminate: bool = False,
    ) -> tuple[OneShotLiveEnqueueV1, bool]:
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
            raise OneShotLiveEnqueueStoreError("record_too_large")
        self._reserve_attempt(
            record=record,
            idempotency_reservation=idempotency_reservation,
            subject_reservation=subject_reservation,
            live_enqueue_admission_valid_until=live_enqueue_admission_valid_until,
        )
        if force_indeterminate:
            self.mark_indeterminate(
                operator_id=record.operator_id,
                enqueue_id=record.enqueue_id,
                audit_evidence=audit_evidence,
            )
            raise OneShotLiveEnqueueStoreError("append_indeterminate")
        return self._append_record(
            record=record,
            subject_reservation=subject_reservation,
            audit_json=audit_json,
        )

    def mark_indeterminate(
        self,
        *,
        operator_id: str,
        enqueue_id: str,
        audit_evidence: OneShotLiveEnqueueAuditEvidenceV1,
    ) -> None:
        audit_json = audit_evidence.model_dump_json()
        if len(audit_json.encode()) > self.max_model_bytes:
            raise OneShotLiveEnqueueStoreError("record_too_large")
        try:
            with self._connect() as connection:
                connection.execute("BEGIN IMMEDIATE")
                row = connection.execute(
                    """SELECT * FROM one_shot_live_enqueue_reservations
                    WHERE operator_id = ? AND enqueue_id = ?""",
                    (operator_id, enqueue_id),
                ).fetchone()
                if row is None:
                    raise OneShotLiveEnqueueStoreError("not_found")
                connection.execute(
                    """INSERT INTO one_shot_live_enqueue_attempts (
                    operator_id, enqueue_id, audit_fingerprint, audit_json
                    ) VALUES (?, ?, ?, ?)""",
                    (
                        operator_id,
                        enqueue_id,
                        audit_evidence.audit_fingerprint.value,
                        audit_json,
                    ),
                )
                connection.execute("COMMIT")
        except OneShotLiveEnqueueStoreError:
            raise
        except sqlite3.Error as error:
            raise OneShotLiveEnqueueStoreError("unavailable") from error

    def get(self, *, operator_id: str, enqueue_id: str) -> OneShotLiveEnqueueV1:
        try:
            with self._connect() as connection:
                row = connection.execute(
                    """SELECT * FROM one_shot_live_enqueue_records
                    WHERE operator_id = ? AND enqueue_id = ?""",
                    (operator_id, enqueue_id),
                ).fetchone()
                reservation = connection.execute(
                    """SELECT * FROM one_shot_live_enqueue_reservations
                    WHERE operator_id = ? AND enqueue_id = ?""",
                    (operator_id, enqueue_id),
                ).fetchone()
        except sqlite3.Error as error:
            raise OneShotLiveEnqueueStoreError("unavailable") from error
        if row is None or reservation is None:
            raise OneShotLiveEnqueueStoreError("not_found")
        return self._decode_record(row, reservation, operator_id=operator_id)

    def list_owned(
        self, *, operator_id: str, candidate_record_id: str
    ) -> tuple[OneShotLiveEnqueueV1, ...]:
        try:
            with self._connect() as connection:
                rows = connection.execute(
                    """SELECT * FROM one_shot_live_enqueue_records
                    WHERE operator_id = ? AND candidate_record_id = ?
                    ORDER BY recorded_at ASC, enqueue_id ASC
                    LIMIT ?""",
                    (
                        operator_id,
                        candidate_record_id,
                        self.max_records_per_operator + 1,
                    ),
                ).fetchall()
                reservations = {
                    row["enqueue_id"]: row
                    for row in connection.execute(
                        """SELECT * FROM one_shot_live_enqueue_reservations
                        WHERE operator_id = ?""",
                        (operator_id,),
                    ).fetchall()
                }
        except sqlite3.Error as error:
            raise OneShotLiveEnqueueStoreError("unavailable") from error
        if len(rows) > self.max_records_per_operator:
            raise OneShotLiveEnqueueStoreError("quota_exceeded")
        return tuple(
            self._decode_record(row, reservations.get(row["enqueue_id"]), operator_id=operator_id)
            for row in rows
        )

    def _reserve_attempt(
        self,
        *,
        record: OneShotLiveEnqueueV1,
        idempotency_reservation: OneShotLiveEnqueueIdempotencyReservationV1,
        subject_reservation: OneShotLiveEnqueueSubjectReservationV1,
        live_enqueue_admission_valid_until: str,
    ) -> None:
        idempotency_json = idempotency_reservation.model_dump_json()
        reservation_json = subject_reservation.model_dump_json()
        try:
            with self._connect() as connection:
                connection.execute("BEGIN IMMEDIATE")
                rows = connection.execute(
                    """SELECT * FROM one_shot_live_enqueue_reservations
                    WHERE operator_id = ?
                    AND (idempotency_key_fingerprint = ?
                    OR item_subject_fingerprint = ?
                    OR enqueue_id = ?
                    OR record_fingerprint = ?)""",
                    (
                        record.operator_id,
                        record.idempotency_key_fingerprint.value,
                        record.item_subject_fingerprint.value,
                        record.enqueue_id,
                        record.record_fingerprint.value,
                    ),
                ).fetchall()
                if rows:
                    if len(rows) != 1 or not self._is_exact_reservation(
                        rows[0],
                        record,
                        idempotency_reservation,
                        subject_reservation,
                        live_enqueue_admission_valid_until,
                    ):
                        raise OneShotLiveEnqueueStoreError("conflict")
                    existing = connection.execute(
                        """SELECT 1 FROM one_shot_live_enqueue_records
                        WHERE operator_id = ? AND enqueue_id = ?""",
                        (record.operator_id, record.enqueue_id),
                    ).fetchone()
                    if existing is None:
                        raise OneShotLiveEnqueueStoreError("append_indeterminate")
                    connection.execute("COMMIT")
                    return
                count = connection.execute(
                    """SELECT COUNT(*) FROM one_shot_live_enqueue_reservations
                    WHERE operator_id = ?""",
                    (record.operator_id,),
                ).fetchone()[0]
                if count >= self.max_records_per_operator:
                    raise OneShotLiveEnqueueStoreError("quota_exceeded")
                connection.execute(
                    """INSERT INTO one_shot_live_enqueue_reservations (
                    operator_id, candidate_record_id, enqueue_id,
                    idempotency_key_fingerprint, request_fingerprint,
                    item_subject_fingerprint, record_fingerprint,
                    live_enqueue_admission_valid_until, reserved_at,
                    idempotency_json, reservation_json, attempt_started
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        record.operator_id,
                        record.candidate_record_id,
                        record.enqueue_id,
                        record.idempotency_key_fingerprint.value,
                        record.request_fingerprint.value,
                        record.item_subject_fingerprint.value,
                        record.record_fingerprint.value,
                        live_enqueue_admission_valid_until,
                        record.recorded_at,
                        idempotency_json,
                        reservation_json,
                        "true",
                    ),
                )
                connection.execute("COMMIT")
        except OneShotLiveEnqueueStoreError:
            raise
        except sqlite3.IntegrityError as error:
            raise OneShotLiveEnqueueStoreError("conflict") from error
        except sqlite3.Error as error:
            raise OneShotLiveEnqueueStoreError("unavailable") from error

    def _append_record(
        self,
        *,
        record: OneShotLiveEnqueueV1,
        subject_reservation: OneShotLiveEnqueueSubjectReservationV1,
        audit_json: str,
    ) -> tuple[OneShotLiveEnqueueV1, bool]:
        try:
            with self._connect() as connection:
                connection.execute("BEGIN IMMEDIATE")
                row = connection.execute(
                    """SELECT * FROM one_shot_live_enqueue_records
                    WHERE operator_id = ? AND enqueue_id = ?""",
                    (record.operator_id, record.enqueue_id),
                ).fetchone()
                reservation = connection.execute(
                    """SELECT * FROM one_shot_live_enqueue_reservations
                    WHERE operator_id = ? AND enqueue_id = ?""",
                    (record.operator_id, record.enqueue_id),
                ).fetchone()
                if reservation is None:
                    raise OneShotLiveEnqueueStoreError("reservation_before_effect_failed")
                if row is not None:
                    existing = self._decode_record(
                        row, reservation, operator_id=record.operator_id
                    )
                    connection.execute("COMMIT")
                    return existing, False
                link = record.lineage
                connection.execute(
                    """INSERT INTO one_shot_live_enqueue_records (
                    operator_id, enqueue_id, candidate_record_id,
                    idempotency_key_fingerprint, request_fingerprint,
                    item_subject_fingerprint, record_fingerprint,
                    live_enqueue_admission_fingerprint,
                    live_enqueue_admission_status_fingerprint,
                    worker_queue_reservation_fingerprint,
                    worker_intake_admission_fingerprint,
                    worker_identity_fingerprint,
                    worker_intake_reference_fingerprint,
                    queue_intake_reference_fingerprint,
                    queue_item_reference_fingerprint,
                    inherited_limits_fingerprint, recorded_at, valid_until,
                    record_json, audit_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        record.operator_id,
                        record.enqueue_id,
                        record.candidate_record_id,
                        record.idempotency_key_fingerprint.value,
                        record.request_fingerprint.value,
                        record.item_subject_fingerprint.value,
                        record.record_fingerprint.value,
                        link.live_enqueue_admission_fingerprint.value,
                        link.live_enqueue_admission_status_fingerprint.value,
                        link.queue_reservation_fingerprint.value,
                        link.worker_intake_admission_fingerprint.value,
                        link.worker_identity_fingerprint.value,
                        link.worker_intake_reference_fingerprint.value,
                        link.queue_intake_reference_fingerprint.value,
                        link.queue_item_reference_fingerprint.value,
                        link.inherited_limits_fingerprint.value,
                        record.recorded_at,
                        record.valid_until,
                        record.model_dump_json(),
                        audit_json,
                    ),
                )
                connection.execute("COMMIT")
                return record, True
        except OneShotLiveEnqueueStoreError:
            raise
        except sqlite3.IntegrityError as error:
            raise OneShotLiveEnqueueStoreError("conflict") from error
        except sqlite3.Error as error:
            raise OneShotLiveEnqueueStoreError("unavailable") from error

    @staticmethod
    def _is_exact_reservation(
        row: sqlite3.Row,
        record: OneShotLiveEnqueueV1,
        idempotency_reservation: OneShotLiveEnqueueIdempotencyReservationV1,
        subject_reservation: OneShotLiveEnqueueSubjectReservationV1,
        live_enqueue_admission_valid_until: str,
    ) -> bool:
        return (
            row["operator_id"] == record.operator_id == subject_reservation.operator_id
            and row["operator_id"] == idempotency_reservation.operator_id
            and row["candidate_record_id"]
            == record.candidate_record_id
            == subject_reservation.candidate_record_id
            == idempotency_reservation.candidate_record_id
            and row["enqueue_id"]
            == record.enqueue_id
            == subject_reservation.enqueue_id
            == idempotency_reservation.enqueue_id
            and row["idempotency_key_fingerprint"]
            == record.idempotency_key_fingerprint.value
            == subject_reservation.idempotency_key_fingerprint.value
            == idempotency_reservation.idempotency_key_fingerprint.value
            and row["request_fingerprint"]
            == record.request_fingerprint.value
            == subject_reservation.request_fingerprint.value
            == idempotency_reservation.request_fingerprint.value
            and row["item_subject_fingerprint"]
            == record.item_subject_fingerprint.value
            == subject_reservation.item_subject_fingerprint.value
            == idempotency_reservation.item_subject_fingerprint.value
            and row["record_fingerprint"]
            == record.record_fingerprint.value
            == subject_reservation.record_fingerprint.value
            == idempotency_reservation.record_fingerprint.value
            and row["live_enqueue_admission_valid_until"]
            == live_enqueue_admission_valid_until
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
            idempotency = OneShotLiveEnqueueIdempotencyReservationV1.model_validate_json(
                row["idempotency_json"]
            )
            reservation = OneShotLiveEnqueueSubjectReservationV1.model_validate_json(
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
            raise OneShotLiveEnqueueStoreError("store_corrupt") from error

    @staticmethod
    def _is_row_reservation_exact(
        row: sqlite3.Row,
        idempotency: OneShotLiveEnqueueIdempotencyReservationV1,
        reservation: OneShotLiveEnqueueSubjectReservationV1,
    ) -> bool:
        return (
            row["operator_id"] == idempotency.operator_id == reservation.operator_id
            and row["candidate_record_id"]
            == idempotency.candidate_record_id
            == reservation.candidate_record_id
            and row["enqueue_id"] == idempotency.enqueue_id == reservation.enqueue_id
            and row["idempotency_key_fingerprint"]
            == idempotency.idempotency_key_fingerprint.value
            == reservation.idempotency_key_fingerprint.value
            and row["request_fingerprint"]
            == idempotency.request_fingerprint.value
            == reservation.request_fingerprint.value
            and row["item_subject_fingerprint"]
            == idempotency.item_subject_fingerprint.value
            == reservation.item_subject_fingerprint.value
            and row["record_fingerprint"]
            == idempotency.record_fingerprint.value
            == reservation.record_fingerprint.value
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
    ) -> OneShotLiveEnqueueV1:
        try:
            self._validate_reservation(reservation_row, operator_id=operator_id)
            if row is None:
                raise ValueError("record missing")
            payloads = (row["record_json"], row["audit_json"])
            if max(len(value.encode()) for value in payloads) > self.max_model_bytes:
                raise ValueError("persisted record exceeds bound")
            record = OneShotLiveEnqueueV1.model_validate_json(row["record_json"])
            audit = OneShotLiveEnqueueAuditEvidenceV1.model_validate_json(
                row["audit_json"]
            )
            link = record.lineage
            if (
                operator_id != row["operator_id"]
                or record.record_fingerprint != record_fingerprint(record)
                or audit.audit_fingerprint != audit_fingerprint(audit)
                or row["operator_id"] != record.operator_id
                or row["candidate_record_id"] != record.candidate_record_id
                or row["enqueue_id"] != record.enqueue_id
                or row["idempotency_key_fingerprint"]
                != record.idempotency_key_fingerprint.value
                or row["request_fingerprint"] != record.request_fingerprint.value
                or row["item_subject_fingerprint"]
                != record.item_subject_fingerprint.value
                or row["record_fingerprint"] != record.record_fingerprint.value
                or row["live_enqueue_admission_fingerprint"]
                != link.live_enqueue_admission_fingerprint.value
                or row["live_enqueue_admission_status_fingerprint"]
                != link.live_enqueue_admission_status_fingerprint.value
                or row["worker_queue_reservation_fingerprint"]
                != link.queue_reservation_fingerprint.value
                or row["worker_intake_admission_fingerprint"]
                != link.worker_intake_admission_fingerprint.value
                or row["worker_identity_fingerprint"]
                != link.worker_identity_fingerprint.value
                or row["worker_intake_reference_fingerprint"]
                != link.worker_intake_reference_fingerprint.value
                or row["queue_intake_reference_fingerprint"]
                != link.queue_intake_reference_fingerprint.value
                or row["queue_item_reference_fingerprint"]
                != link.queue_item_reference_fingerprint.value
                or row["inherited_limits_fingerprint"]
                != link.inherited_limits_fingerprint.value
                or row["recorded_at"] != record.recorded_at
                or row["valid_until"] != record.valid_until
                or audit.event != "one_shot_live_enqueue_recorded"
                or audit.outcome != "recorded"
                or audit.operator_id != record.operator_id
                or audit.candidate_record_id != record.candidate_record_id
                or audit.enqueue_id != record.enqueue_id
                or audit.item_subject_fingerprint != record.item_subject_fingerprint
                or audit.record_fingerprint != record.record_fingerprint
                or audit.occurred_at != record.recorded_at
            ):
                raise ValueError("persisted record mismatch")
            return record
        except OneShotLiveEnqueueStoreError:
            raise
        except Exception as error:
            raise OneShotLiveEnqueueStoreError("store_corrupt") from error
