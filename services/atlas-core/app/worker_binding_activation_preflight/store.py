"""Durable append-only store for v0.47 worker binding activation preflight evidence."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from .contract import (
    MAX_MODEL_BYTES,
    WorkerBindingActivationPreflightAuditEvidenceV1,
    WorkerBindingActivationPreflightIdempotencyReservationV1,
    WorkerBindingActivationPreflightSubjectReservationV1,
    WorkerBindingActivationPreflightV1,
    audit_fingerprint,
    preflight_record_fingerprint,
    reservation_fingerprint,
)

MAX_RECORDS_PER_OPERATOR = 16


class WorkerBindingActivationPreflightStoreError(RuntimeError):
    """Closed storage failure without database or record disclosure."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


class WorkerBindingActivationPreflightStore:
    """SQLite reservations and records; no activation, worker, queue, or effect API."""

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
                    CREATE TABLE IF NOT EXISTS worker_binding_activation_preflight_reservations (
                        operator_id TEXT NOT NULL,
                        candidate_record_id TEXT NOT NULL,
                        preflight_id TEXT NOT NULL,
                        idempotency_key_fingerprint TEXT NOT NULL,
                        request_fingerprint TEXT NOT NULL,
                        subject_fingerprint TEXT NOT NULL,
                        preflight_record_fingerprint TEXT NOT NULL,
                        binding_valid_until TEXT NOT NULL,
                        reserved_at TEXT NOT NULL,
                        idempotency_json TEXT NOT NULL,
                        reservation_json TEXT NOT NULL,
                        attempt_started TEXT NOT NULL,
                        PRIMARY KEY (operator_id, preflight_id),
                        UNIQUE (operator_id, idempotency_key_fingerprint),
                        UNIQUE (operator_id, subject_fingerprint),
                        UNIQUE (operator_id, preflight_record_fingerprint)
                    )
                    """
                )
                connection.execute(
                    """
                    CREATE TABLE IF NOT EXISTS worker_binding_activation_preflight_attempts (
                        operator_id TEXT NOT NULL,
                        preflight_id TEXT NOT NULL,
                        audit_fingerprint TEXT NOT NULL,
                        audit_json TEXT NOT NULL,
                        PRIMARY KEY (operator_id, preflight_id, audit_fingerprint),
                        FOREIGN KEY (operator_id, preflight_id)
                            REFERENCES worker_binding_activation_preflight_reservations(
                                operator_id, preflight_id
                            )
                    )
                    """
                )
                connection.execute(
                    """
                    CREATE TABLE IF NOT EXISTS worker_binding_activation_preflights (
                        operator_id TEXT NOT NULL,
                        preflight_id TEXT NOT NULL,
                        candidate_record_id TEXT NOT NULL,
                        idempotency_key_fingerprint TEXT NOT NULL,
                        request_fingerprint TEXT NOT NULL,
                        subject_fingerprint TEXT NOT NULL,
                        preflight_record_fingerprint TEXT NOT NULL,
                        binding_id TEXT NOT NULL,
                        binding_record_fingerprint TEXT NOT NULL,
                        binding_status_fingerprint TEXT NOT NULL,
                        binding_subject_fingerprint TEXT NOT NULL,
                        worker_subject_fingerprint TEXT NOT NULL,
                        queue_item_reference_fingerprint TEXT NOT NULL,
                        inherited_limits_fingerprint TEXT NOT NULL,
                        recorded_at TEXT NOT NULL,
                        valid_until TEXT NOT NULL,
                        record_json TEXT NOT NULL,
                        audit_json TEXT NOT NULL,
                        PRIMARY KEY (operator_id, preflight_id),
                        UNIQUE (operator_id, idempotency_key_fingerprint),
                        UNIQUE (operator_id, subject_fingerprint),
                        UNIQUE (operator_id, preflight_record_fingerprint),
                        FOREIGN KEY (operator_id, preflight_id)
                            REFERENCES worker_binding_activation_preflight_reservations(
                                operator_id, preflight_id
                            )
                    )
                    """
                )
        except sqlite3.Error as error:
            raise WorkerBindingActivationPreflightStoreError("unavailable") from error

    def resolve_idempotency(
        self,
        *,
        operator_id: str,
        idempotency_key_fingerprint: str,
        request_fingerprint: str,
        binding_valid_until: str,
    ) -> WorkerBindingActivationPreflightV1 | None:
        try:
            with self._connect() as connection:
                reservation = connection.execute(
                    """SELECT * FROM worker_binding_activation_preflight_reservations
                    WHERE operator_id = ? AND idempotency_key_fingerprint = ?""",
                    (operator_id, idempotency_key_fingerprint),
                ).fetchone()
                if reservation is None:
                    return None
                if (
                    reservation["request_fingerprint"] != request_fingerprint
                    or reservation["binding_valid_until"] != binding_valid_until
                ):
                    raise WorkerBindingActivationPreflightStoreError(
                        "idempotency_conflict"
                    )
                row = connection.execute(
                    """SELECT * FROM worker_binding_activation_preflights
                    WHERE operator_id = ? AND preflight_id = ?""",
                    (operator_id, reservation["preflight_id"]),
                ).fetchone()
        except WorkerBindingActivationPreflightStoreError:
            raise
        except sqlite3.Error as error:
            raise WorkerBindingActivationPreflightStoreError("unavailable") from error
        self._validate_reservation(reservation, operator_id=operator_id)
        if row is None:
            raise WorkerBindingActivationPreflightStoreError("append_indeterminate")
        return self._decode_record(row, reservation, operator_id=operator_id)

    def append(
        self,
        *,
        record: WorkerBindingActivationPreflightV1,
        idempotency_reservation: WorkerBindingActivationPreflightIdempotencyReservationV1,
        subject_reservation: WorkerBindingActivationPreflightSubjectReservationV1,
        audit_evidence: WorkerBindingActivationPreflightAuditEvidenceV1,
        binding_valid_until: str,
        force_indeterminate: bool = False,
    ) -> tuple[WorkerBindingActivationPreflightV1, bool]:
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
            raise WorkerBindingActivationPreflightStoreError("record_too_large")
        self._reserve_attempt(
            record=record,
            idempotency_reservation=idempotency_reservation,
            subject_reservation=subject_reservation,
            binding_valid_until=binding_valid_until,
        )
        if force_indeterminate:
            self.mark_indeterminate(
                operator_id=record.operator_id,
                preflight_id=record.preflight_id,
                audit_evidence=audit_evidence,
            )
            raise WorkerBindingActivationPreflightStoreError("append_indeterminate")
        return self._append_record(
            record=record,
            subject_reservation=subject_reservation,
            audit_json=audit_json,
        )

    def mark_indeterminate(
        self,
        *,
        operator_id: str,
        preflight_id: str,
        audit_evidence: WorkerBindingActivationPreflightAuditEvidenceV1,
    ) -> None:
        audit_json = audit_evidence.model_dump_json()
        if len(audit_json.encode()) > self.max_model_bytes:
            raise WorkerBindingActivationPreflightStoreError("record_too_large")
        try:
            with self._connect() as connection:
                connection.execute("BEGIN IMMEDIATE")
                row = connection.execute(
                    """SELECT * FROM worker_binding_activation_preflight_reservations
                    WHERE operator_id = ? AND preflight_id = ?""",
                    (operator_id, preflight_id),
                ).fetchone()
                if row is None:
                    raise WorkerBindingActivationPreflightStoreError("not_found")
                connection.execute(
                    """INSERT OR IGNORE INTO worker_binding_activation_preflight_attempts (
                    operator_id, preflight_id, audit_fingerprint, audit_json
                    ) VALUES (?, ?, ?, ?)""",
                    (
                        operator_id,
                        preflight_id,
                        audit_evidence.audit_fingerprint.value,
                        audit_json,
                    ),
                )
                connection.execute("COMMIT")
        except WorkerBindingActivationPreflightStoreError:
            raise
        except sqlite3.Error as error:
            raise WorkerBindingActivationPreflightStoreError("unavailable") from error

    def get(
        self, *, operator_id: str, preflight_id: str
    ) -> WorkerBindingActivationPreflightV1:
        try:
            with self._connect() as connection:
                row = connection.execute(
                    """SELECT * FROM worker_binding_activation_preflights
                    WHERE operator_id = ? AND preflight_id = ?""",
                    (operator_id, preflight_id),
                ).fetchone()
                reservation = connection.execute(
                    """SELECT * FROM worker_binding_activation_preflight_reservations
                    WHERE operator_id = ? AND preflight_id = ?""",
                    (operator_id, preflight_id),
                ).fetchone()
        except sqlite3.Error as error:
            raise WorkerBindingActivationPreflightStoreError("unavailable") from error
        if row is None or reservation is None:
            raise WorkerBindingActivationPreflightStoreError("not_found")
        return self._decode_record(row, reservation, operator_id=operator_id)

    def list_owned(
        self, *, operator_id: str, candidate_record_id: str
    ) -> tuple[WorkerBindingActivationPreflightV1, ...]:
        try:
            with self._connect() as connection:
                rows = connection.execute(
                    """SELECT * FROM worker_binding_activation_preflights
                    WHERE operator_id = ? AND candidate_record_id = ?
                    ORDER BY recorded_at ASC, preflight_id ASC
                    LIMIT ?""",
                    (
                        operator_id,
                        candidate_record_id,
                        self.max_records_per_operator + 1,
                    ),
                ).fetchall()
                reservations = {
                    row["preflight_id"]: row
                    for row in connection.execute(
                        """SELECT * FROM worker_binding_activation_preflight_reservations
                        WHERE operator_id = ?""",
                        (operator_id,),
                    ).fetchall()
                }
        except sqlite3.Error as error:
            raise WorkerBindingActivationPreflightStoreError("unavailable") from error
        if len(rows) > self.max_records_per_operator:
            raise WorkerBindingActivationPreflightStoreError("quota_exceeded")
        return tuple(
            self._decode_record(
                row, reservations.get(row["preflight_id"]), operator_id=operator_id
            )
            for row in rows
        )

    def _reserve_attempt(
        self,
        *,
        record: WorkerBindingActivationPreflightV1,
        idempotency_reservation: WorkerBindingActivationPreflightIdempotencyReservationV1,
        subject_reservation: WorkerBindingActivationPreflightSubjectReservationV1,
        binding_valid_until: str,
    ) -> None:
        idempotency_json = idempotency_reservation.model_dump_json()
        reservation_json = subject_reservation.model_dump_json()
        try:
            with self._connect() as connection:
                connection.execute("BEGIN IMMEDIATE")
                rows = connection.execute(
                    """SELECT * FROM worker_binding_activation_preflight_reservations
                    WHERE operator_id = ?
                    AND (idempotency_key_fingerprint = ?
                    OR subject_fingerprint = ?
                    OR preflight_id = ?
                    OR preflight_record_fingerprint = ?)""",
                    (
                        record.operator_id,
                        idempotency_reservation.idempotency_key_fingerprint.value,
                        record.subject_fingerprint.value,
                        record.preflight_id,
                        record.preflight_record_fingerprint.value,
                    ),
                ).fetchall()
                if rows:
                    if len(rows) != 1:
                        raise WorkerBindingActivationPreflightStoreError("conflict")
                    row = rows[0]
                    if not self._is_exact_reservation(
                        row,
                        record,
                        idempotency_reservation,
                        subject_reservation,
                        binding_valid_until,
                    ):
                        if (
                            row["idempotency_key_fingerprint"]
                            == idempotency_reservation.idempotency_key_fingerprint.value
                        ):
                            raise WorkerBindingActivationPreflightStoreError(
                                "idempotency_conflict"
                            )
                        raise WorkerBindingActivationPreflightStoreError(
                            "permanent_subject_reserved"
                        )
                    existing = connection.execute(
                        """SELECT 1 FROM worker_binding_activation_preflights
                        WHERE operator_id = ? AND preflight_id = ?""",
                        (record.operator_id, record.preflight_id),
                    ).fetchone()
                    if existing is None:
                        raise WorkerBindingActivationPreflightStoreError(
                            "append_indeterminate"
                        )
                    connection.execute("COMMIT")
                    return
                count = connection.execute(
                    """SELECT COUNT(*) FROM worker_binding_activation_preflight_reservations
                    WHERE operator_id = ?""",
                    (record.operator_id,),
                ).fetchone()[0]
                if count >= self.max_records_per_operator:
                    raise WorkerBindingActivationPreflightStoreError("quota_exceeded")
                connection.execute(
                    """INSERT INTO worker_binding_activation_preflight_reservations (
                    operator_id, candidate_record_id, preflight_id,
                    idempotency_key_fingerprint, request_fingerprint,
                    subject_fingerprint, preflight_record_fingerprint,
                    binding_valid_until, reserved_at, idempotency_json,
                    reservation_json, attempt_started
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        record.operator_id,
                        record.candidate_record_id,
                        record.preflight_id,
                        idempotency_reservation.idempotency_key_fingerprint.value,
                        idempotency_reservation.request_fingerprint.value,
                        record.subject_fingerprint.value,
                        record.preflight_record_fingerprint.value,
                        binding_valid_until,
                        record.recorded_at,
                        idempotency_json,
                        reservation_json,
                        "true",
                    ),
                )
                connection.execute("COMMIT")
        except WorkerBindingActivationPreflightStoreError:
            raise
        except sqlite3.IntegrityError as error:
            raise WorkerBindingActivationPreflightStoreError("conflict") from error
        except sqlite3.Error as error:
            raise WorkerBindingActivationPreflightStoreError("unavailable") from error

    def _append_record(
        self,
        *,
        record: WorkerBindingActivationPreflightV1,
        subject_reservation: WorkerBindingActivationPreflightSubjectReservationV1,
        audit_json: str,
    ) -> tuple[WorkerBindingActivationPreflightV1, bool]:
        try:
            with self._connect() as connection:
                connection.execute("BEGIN IMMEDIATE")
                row = connection.execute(
                    """SELECT * FROM worker_binding_activation_preflights
                    WHERE operator_id = ? AND preflight_id = ?""",
                    (record.operator_id, record.preflight_id),
                ).fetchone()
                reservation = connection.execute(
                    """SELECT * FROM worker_binding_activation_preflight_reservations
                    WHERE operator_id = ? AND preflight_id = ?""",
                    (record.operator_id, record.preflight_id),
                ).fetchone()
                if reservation is None:
                    raise WorkerBindingActivationPreflightStoreError(
                        "reservation_before_effect_failed"
                    )
                if row is not None:
                    existing = self._decode_record(
                        row, reservation, operator_id=record.operator_id
                    )
                    connection.execute("COMMIT")
                    return existing, False
                binding = record.one_shot_dequeue_worker_binding
                status = record.one_shot_dequeue_worker_binding_status
                connection.execute(
                    """INSERT INTO worker_binding_activation_preflights (
                    operator_id, preflight_id, candidate_record_id,
                    idempotency_key_fingerprint, request_fingerprint,
                    subject_fingerprint, preflight_record_fingerprint,
                    binding_id, binding_record_fingerprint,
                    binding_status_fingerprint, binding_subject_fingerprint,
                    worker_subject_fingerprint, queue_item_reference_fingerprint,
                    inherited_limits_fingerprint, recorded_at, valid_until,
                    record_json, audit_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        record.operator_id,
                        record.preflight_id,
                        record.candidate_record_id,
                        subject_reservation.idempotency_key_fingerprint.value,
                        subject_reservation.request_fingerprint.value,
                        record.subject_fingerprint.value,
                        record.preflight_record_fingerprint.value,
                        binding.binding_id,
                        binding.binding_record_fingerprint.value,
                        status.status_fingerprint.value,
                        record.binding_subject_fingerprint.value,
                        record.worker_subject_fingerprint.value,
                        record.queue_item_reference_fingerprint.value,
                        record.inherited_limits_fingerprint.value,
                        record.recorded_at,
                        record.valid_until,
                        record.model_dump_json(),
                        audit_json,
                    ),
                )
                connection.execute("COMMIT")
                return record, True
        except WorkerBindingActivationPreflightStoreError:
            raise
        except sqlite3.IntegrityError as error:
            raise WorkerBindingActivationPreflightStoreError("conflict") from error
        except sqlite3.Error as error:
            raise WorkerBindingActivationPreflightStoreError("unavailable") from error

    @staticmethod
    def _is_exact_reservation(
        row: sqlite3.Row,
        record: WorkerBindingActivationPreflightV1,
        idempotency_reservation: WorkerBindingActivationPreflightIdempotencyReservationV1,
        subject_reservation: WorkerBindingActivationPreflightSubjectReservationV1,
        binding_valid_until: str,
    ) -> bool:
        return (
            row["operator_id"] == record.operator_id == subject_reservation.operator_id
            and row["operator_id"] == idempotency_reservation.operator_id
            and row["candidate_record_id"]
            == record.candidate_record_id
            == subject_reservation.candidate_record_id
            == idempotency_reservation.candidate_record_id
            and row["preflight_id"]
            == record.preflight_id
            == subject_reservation.preflight_id
            == idempotency_reservation.preflight_id
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
            and row["preflight_record_fingerprint"]
            == record.preflight_record_fingerprint.value
            == idempotency_reservation.preflight_record_fingerprint.value
            == subject_reservation.preflight_record_fingerprint.value
            and row["binding_valid_until"] == binding_valid_until
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
                WorkerBindingActivationPreflightIdempotencyReservationV1.model_validate_json(
                    row["idempotency_json"]
                )
            )
            reservation = (
                WorkerBindingActivationPreflightSubjectReservationV1.model_validate_json(
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
            raise WorkerBindingActivationPreflightStoreError("store_corrupt") from error

    @staticmethod
    def _is_row_reservation_exact(
        row: sqlite3.Row,
        idempotency: WorkerBindingActivationPreflightIdempotencyReservationV1,
        reservation: WorkerBindingActivationPreflightSubjectReservationV1,
    ) -> bool:
        return (
            row["operator_id"] == idempotency.operator_id == reservation.operator_id
            and row["candidate_record_id"]
            == idempotency.candidate_record_id
            == reservation.candidate_record_id
            and row["preflight_id"]
            == idempotency.preflight_id
            == reservation.preflight_id
            and row["idempotency_key_fingerprint"]
            == idempotency.idempotency_key_fingerprint.value
            == reservation.idempotency_key_fingerprint.value
            and row["request_fingerprint"]
            == idempotency.request_fingerprint.value
            == reservation.request_fingerprint.value
            and row["subject_fingerprint"]
            == idempotency.subject_fingerprint.value
            == reservation.subject_fingerprint.value
            and row["preflight_record_fingerprint"]
            == idempotency.preflight_record_fingerprint.value
            == reservation.preflight_record_fingerprint.value
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
    ) -> WorkerBindingActivationPreflightV1:
        try:
            self._validate_reservation(reservation_row, operator_id=operator_id)
            payloads = (row["record_json"], row["audit_json"])
            if max(len(value.encode()) for value in payloads) > self.max_model_bytes:
                raise ValueError("persisted record exceeds bound")
            record = WorkerBindingActivationPreflightV1.model_validate_json(
                row["record_json"]
            )
            audit = (
                WorkerBindingActivationPreflightAuditEvidenceV1.model_validate_json(
                    row["audit_json"]
                )
            )
            binding = record.one_shot_dequeue_worker_binding
            status = record.one_shot_dequeue_worker_binding_status
            if (
                operator_id != row["operator_id"]
                or record.preflight_record_fingerprint
                != preflight_record_fingerprint(record)
                or audit.audit_fingerprint != audit_fingerprint(audit)
                or row["operator_id"] != record.operator_id
                or row["candidate_record_id"] != record.candidate_record_id
                or row["preflight_id"] != record.preflight_id
                or row["idempotency_key_fingerprint"]
                != reservation_row["idempotency_key_fingerprint"]
                or row["request_fingerprint"] != reservation_row["request_fingerprint"]
                or row["subject_fingerprint"] != record.subject_fingerprint.value
                or row["preflight_record_fingerprint"]
                != record.preflight_record_fingerprint.value
                or row["binding_id"] != binding.binding_id
                or row["binding_record_fingerprint"]
                != binding.binding_record_fingerprint.value
                or row["binding_status_fingerprint"] != status.status_fingerprint.value
                or row["binding_subject_fingerprint"]
                != record.binding_subject_fingerprint.value
                or row["worker_subject_fingerprint"]
                != record.worker_subject_fingerprint.value
                or row["queue_item_reference_fingerprint"]
                != record.queue_item_reference_fingerprint.value
                or row["inherited_limits_fingerprint"]
                != record.inherited_limits_fingerprint.value
                or row["recorded_at"] != record.recorded_at
                or row["valid_until"] != record.valid_until
                or audit.event != "worker_binding_activation_preflight_recorded"
                or audit.outcome != "recorded"
                or audit.operator_id != record.operator_id
                or audit.candidate_record_id != record.candidate_record_id
                or audit.preflight_id != record.preflight_id
                or audit.subject_fingerprint != record.subject_fingerprint
                or audit.preflight_record_fingerprint
                != record.preflight_record_fingerprint
                or audit.occurred_at != record.recorded_at
            ):
                raise ValueError("persisted record mismatch")
            return record
        except WorkerBindingActivationPreflightStoreError:
            raise
        except Exception as error:
            raise WorkerBindingActivationPreflightStoreError("store_corrupt") from error
