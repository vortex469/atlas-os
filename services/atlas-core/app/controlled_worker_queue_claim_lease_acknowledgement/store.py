"""Durable append-only store for v0.52 queue claim/lease/ack receipt evidence."""

from __future__ import annotations

import sqlite3
from collections.abc import Callable, Iterator
from contextlib import closing, contextmanager
from pathlib import Path

from pydantic import TypeAdapter

from .contract import (
    MAX_MODEL_BYTES,
    ControlledWorkerQueueClaimLeaseAcknowledgementAuditEvidenceV1,
    ControlledWorkerQueueClaimLeaseAcknowledgementIdempotencyReservationV1,
    ControlledWorkerQueueClaimLeaseAcknowledgementSubjectReservationV1,
    ControlledWorkerQueueClaimLeaseAcknowledgementV1,
    UtcSecond,
    audit_fingerprint,
    build_create,
    receipt_record_fingerprint,
    request_fingerprint,
    reservation_fingerprint,
)

_SCHEMA = (
    """CREATE TABLE IF NOT EXISTS cwqcla_receipt_reservations (
                        operator_id TEXT NOT NULL,
                        candidate_record_id TEXT NOT NULL,
                        admission_id TEXT NOT NULL,
                        idempotency_key_fingerprint TEXT NOT NULL,
                        request_fingerprint TEXT NOT NULL,
                        subject_fingerprint TEXT NOT NULL,
                        receipt_record_fingerprint TEXT NOT NULL,
                        admission_valid_until TEXT NOT NULL,
                        reserved_at TEXT NOT NULL,
                        idempotency_json TEXT NOT NULL,
                        reservation_json TEXT NOT NULL,
                        attempt_started TEXT NOT NULL,
                        PRIMARY KEY (operator_id, admission_id),
                        UNIQUE (operator_id, idempotency_key_fingerprint),
                        UNIQUE (operator_id, subject_fingerprint),
                        UNIQUE (operator_id, receipt_record_fingerprint)
                    )""",
    """CREATE TABLE IF NOT EXISTS cwqcla_receipt_attempts (
                        operator_id TEXT NOT NULL,
                        admission_id TEXT NOT NULL,
                        audit_fingerprint TEXT NOT NULL,
                        audit_json TEXT NOT NULL,
                        PRIMARY KEY (operator_id, admission_id, audit_fingerprint),
                        FOREIGN KEY (operator_id, admission_id)
                            REFERENCES cwqcla_receipt_reservations(
                                operator_id, admission_id
                            )
                    )""",
    """CREATE TABLE IF NOT EXISTS cwqcla_receipts (
                        operator_id TEXT NOT NULL,
                        admission_id TEXT NOT NULL,
                        candidate_record_id TEXT NOT NULL,
                        idempotency_key_fingerprint TEXT NOT NULL,
                        request_fingerprint TEXT NOT NULL,
                        subject_fingerprint TEXT NOT NULL,
                        receipt_record_fingerprint TEXT NOT NULL,
                        v051_admission_record_fingerprint TEXT NOT NULL,
                        v051_admission_status_fingerprint TEXT NOT NULL,
                        v050_prerequisite_record_fingerprint TEXT NOT NULL,
                        v050_prerequisite_status_fingerprint TEXT NOT NULL,
                        v049_admission_record_fingerprint TEXT NOT NULL,
                        v049_admission_status_fingerprint TEXT NOT NULL,
                        binding_subject_fingerprint TEXT NOT NULL,
                        worker_subject_fingerprint TEXT NOT NULL,
                        queue_item_reference_fingerprint TEXT NOT NULL,
                        inherited_limits_fingerprint TEXT NOT NULL,
                        adapter_identity_fingerprint TEXT NOT NULL,
                        queue_subject_fingerprint TEXT NOT NULL,
                        claim_receipt_fingerprint TEXT NOT NULL,
                        lease_receipt_fingerprint TEXT NOT NULL,
                        acknowledgement_receipt_fingerprint TEXT NOT NULL,
                        recorded_at TEXT NOT NULL,
                        valid_until TEXT NOT NULL,
                        record_json TEXT NOT NULL,
                        audit_json TEXT NOT NULL,
                        PRIMARY KEY (operator_id, admission_id),
                        UNIQUE (operator_id, idempotency_key_fingerprint),
                        UNIQUE (operator_id, subject_fingerprint),
                        UNIQUE (operator_id, receipt_record_fingerprint),
                        FOREIGN KEY (operator_id, admission_id)
                            REFERENCES cwqcla_receipt_reservations(
                                operator_id, admission_id
                            )
                    )""",
)

MAX_RECORDS_PER_OPERATOR = 16
MAX_TOTAL_RECORDS = 256
MAX_DATABASE_BYTES = 256 * 1024 * 1024


class ControlledWorkerQueueClaimLeaseAcknowledgementStoreError(RuntimeError):
    """Closed storage failure without database or record disclosure."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


class ControlledWorkerQueueClaimLeaseAcknowledgementStore:
    """SQLite reservations and records; no queue, claim, lease, ack, or effect API."""

    def __init__(
        self,
        database_path: str | Path,
        *,
        max_records_per_operator: int = MAX_RECORDS_PER_OPERATOR,
        max_model_bytes: int = MAX_MODEL_BYTES,
        max_total_records: int = MAX_TOTAL_RECORDS,
    ) -> None:
        for value, maximum in (
            (max_records_per_operator, MAX_RECORDS_PER_OPERATOR),
            (max_model_bytes, MAX_MODEL_BYTES),
            (max_total_records, MAX_TOTAL_RECORDS),
        ):
            if type(value) is not int or not 0 <= value <= maximum:
                raise ControlledWorkerQueueClaimLeaseAcknowledgementStoreError(
                    "invalid_request"
                )
        self.max_total_records = max_total_records
        self._initialized = False
        self.database_path = Path(database_path)
        self.max_records_per_operator = max_records_per_operator
        self.max_model_bytes = max_model_bytes
        self._initialize()
        self._initialized = True
        with self._connect():
            pass

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        connection = None
        try:
            connection = sqlite3.connect(
                self.database_path, timeout=5, isolation_level=None
            )
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA foreign_keys=ON")
            connection.execute("PRAGMA synchronous=FULL")
            page_size = connection.execute("PRAGMA page_size").fetchone()[0]
            connection.execute(
                f"PRAGMA max_page_count={MAX_DATABASE_BYTES // page_size}"
            )
            connection.execute("BEGIN IMMEDIATE")
            if self._initialized:
                self._check_integrity(connection)
            yield connection
            connection.execute("COMMIT")
        except sqlite3.DatabaseError as error:
            code = (
                "unavailable"
                if isinstance(error, sqlite3.OperationalError)
                else "store_corrupt"
            )
            raise ControlledWorkerQueueClaimLeaseAcknowledgementStoreError(
                code
            ) from None
        finally:
            if connection is not None:
                if connection.in_transaction:
                    connection.rollback()
                connection.close()

    def _check_integrity(self, connection: sqlite3.Connection) -> None:
        """Validate the whole bounded journal before trusting lookup indexes.

        A corrupt owner/index must not hide a permanent reservation. Reads use
        the same transaction as this check, including across store instances.
        """
        try:
            if {
                tuple(row)
                for row in connection.execute("SELECT name, sql FROM sqlite_master")
            } != self._schema:
                raise ValueError("schema mismatch")
            if (
                connection.execute("PRAGMA page_count").fetchone()[0]
                * connection.execute("PRAGMA page_size").fetchone()[0]
                > MAX_DATABASE_BYTES
            ):
                raise ValueError("database bound")
            if connection.execute("PRAGMA application_id").fetchone()[0] != 52:
                raise ValueError("schema marker")
            if connection.execute("PRAGMA quick_check").fetchone()[0] != "ok":
                raise ValueError("integrity")
            if connection.execute("PRAGMA foreign_key_check").fetchone() is not None:
                raise ValueError("orphan")
            tables = {
                "cwqcla_receipt_reservations": ("idempotency_json", "reservation_json"),
                "cwqcla_receipts": ("record_json", "audit_json"),
                "cwqcla_receipt_attempts": ("audit_json",),
            }
            for table, columns in tables.items():
                count = connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[
                    0
                ]
                if count > self.max_total_records:
                    raise ValueError("bound")
                for column in columns:
                    if (
                        connection.execute(
                            f"SELECT 1 FROM {table} WHERE typeof({column}) != 'text' "
                            f"OR length(CAST({column} AS BLOB)) > ? LIMIT 1",
                            (self.max_model_bytes,),
                        ).fetchone()
                        is not None
                    ):
                        raise ValueError("payload bound")
            reservations = {}
            owners = {}
            for row in connection.execute("SELECT * FROM cwqcla_receipt_reservations"):
                self._validate_reservation(row, operator_id=row["operator_id"])
                key = (row["operator_id"], row["admission_id"])
                reservations[key] = row
                owners[key[0]] = owners.get(key[0], 0) + 1
                if owners[key[0]] > self.max_records_per_operator:
                    raise ValueError("owner bound")
            receipts = set()
            for row in connection.execute("SELECT * FROM cwqcla_receipts"):
                key = (row["operator_id"], row["admission_id"])
                self._decode_record(row, reservations.get(key), operator_id=key[0])
                receipts.add(key)
            attempts = set()
            for row in connection.execute("SELECT * FROM cwqcla_receipt_attempts"):
                key = (row["operator_id"], row["admission_id"])
                if key in attempts or key in receipts or key not in reservations:
                    raise ValueError("terminal attempt mismatch")
                audit = ControlledWorkerQueueClaimLeaseAcknowledgementAuditEvidenceV1.model_validate_json(
                    row["audit_json"]
                )
                self._validate_terminal_audit(audit, reservations[key])
                if row["audit_fingerprint"] != audit.audit_fingerprint.value:
                    raise ValueError("audit index mismatch")
                attempts.add(key)
        except Exception:  # noqa: BLE001 - fail closed without exposing persisted data
            raise ControlledWorkerQueueClaimLeaseAcknowledgementStoreError(
                "store_corrupt"
            ) from None

    @staticmethod
    def _validate_terminal_audit(audit, reservation) -> None:
        if (
            audit.event
            != "controlled_worker_queue_claim_lease_acknowledgement_indeterminate"
            or audit.outcome != "indeterminate"
            or audit.controlled_worker_queue_claim_lease_acknowledgement_recorded
            or audit.operator_id != reservation["operator_id"]
            or audit.candidate_record_id != reservation["candidate_record_id"]
            or audit.admission_id != reservation["admission_id"]
            or audit.subject_fingerprint is None
            or audit.subject_fingerprint.value != reservation["subject_fingerprint"]
            or audit.receipt_record_fingerprint is None
            or audit.receipt_record_fingerprint.value
            != reservation["receipt_record_fingerprint"]
            or audit.occurred_at < reservation["reserved_at"]
        ):
            raise ControlledWorkerQueueClaimLeaseAcknowledgementStoreError(
                "store_corrupt"
            )

    def _initialize(self) -> None:
        # Compare exact schema before opening an existing journal. Never repair
        # missing tables or constraints, since that could erase no-replay state.
        with closing(sqlite3.connect(":memory:")) as reference:
            for statement in _SCHEMA:
                reference.execute(statement)
            self._schema = set(reference.execute("SELECT name, sql FROM sqlite_master"))
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            actual = {
                tuple(row)
                for row in connection.execute("SELECT name, sql FROM sqlite_master")
            }
            if actual:
                if (
                    actual != self._schema
                    or connection.execute("PRAGMA application_id").fetchone()[0] != 52
                ):
                    raise ControlledWorkerQueueClaimLeaseAcknowledgementStoreError(
                        "store_corrupt"
                    )
            else:
                if connection.execute("PRAGMA application_id").fetchone()[0] != 0:
                    raise ControlledWorkerQueueClaimLeaseAcknowledgementStoreError(
                        "store_corrupt"
                    )
                for statement in _SCHEMA:
                    connection.execute(statement)
                connection.execute("PRAGMA application_id=52")

    def resolve_idempotency(
        self,
        *,
        operator_id: str,
        idempotency_key_fingerprint: str,
        request_fingerprint: str,
        admission_valid_until: str,
    ) -> ControlledWorkerQueueClaimLeaseAcknowledgementV1 | None:
        try:
            with self._connect() as connection:
                reservation = connection.execute(
                    """SELECT * FROM cwqcla_receipt_reservations
                    WHERE operator_id = ? AND idempotency_key_fingerprint = ?""",
                    (operator_id, idempotency_key_fingerprint),
                ).fetchone()
                if reservation is None:
                    return None
                if (
                    reservation["request_fingerprint"] != request_fingerprint
                    or reservation["admission_valid_until"] != admission_valid_until
                ):
                    raise ControlledWorkerQueueClaimLeaseAcknowledgementStoreError(
                        "idempotency_conflict"
                    )
                row = connection.execute(
                    """SELECT * FROM cwqcla_receipts
                    WHERE operator_id = ? AND admission_id = ?""",
                    (operator_id, reservation["admission_id"]),
                ).fetchone()
        except ControlledWorkerQueueClaimLeaseAcknowledgementStoreError:
            raise
        except sqlite3.Error as error:
            raise ControlledWorkerQueueClaimLeaseAcknowledgementStoreError(
                "unavailable"
            ) from error
        self._validate_reservation(reservation, operator_id=operator_id)
        if row is None:
            raise ControlledWorkerQueueClaimLeaseAcknowledgementStoreError(
                "append_indeterminate"
            )
        return self._decode_record(row, reservation, operator_id=operator_id)

    def append(
        self,
        *,
        record: ControlledWorkerQueueClaimLeaseAcknowledgementV1,
        idempotency_reservation: ControlledWorkerQueueClaimLeaseAcknowledgementIdempotencyReservationV1,
        subject_reservation: ControlledWorkerQueueClaimLeaseAcknowledgementSubjectReservationV1,
        audit_evidence: ControlledWorkerQueueClaimLeaseAcknowledgementAuditEvidenceV1,
        admission_valid_until: str,
        force_indeterminate: bool = False,
        revalidate: Callable[[], None] | None = None,
    ) -> tuple[ControlledWorkerQueueClaimLeaseAcknowledgementV1, bool]:
        try:
            return self._append(
                record=record,
                idempotency_reservation=idempotency_reservation,
                subject_reservation=subject_reservation,
                audit_evidence=audit_evidence,
                admission_valid_until=admission_valid_until,
                force_indeterminate=force_indeterminate,
                revalidate=revalidate,
            )
        except ControlledWorkerQueueClaimLeaseAcknowledgementStoreError:
            raise
        except Exception:  # noqa: BLE001 - model validation details are internal
            raise ControlledWorkerQueueClaimLeaseAcknowledgementStoreError(
                "store_corrupt"
            ) from None

    def _append(
        self,
        *,
        record: ControlledWorkerQueueClaimLeaseAcknowledgementV1,
        idempotency_reservation: ControlledWorkerQueueClaimLeaseAcknowledgementIdempotencyReservationV1,
        subject_reservation: ControlledWorkerQueueClaimLeaseAcknowledgementSubjectReservationV1,
        audit_evidence: ControlledWorkerQueueClaimLeaseAcknowledgementAuditEvidenceV1,
        admission_valid_until: str,
        force_indeterminate: bool = False,
        revalidate: Callable[[], None] | None = None,
    ) -> tuple[ControlledWorkerQueueClaimLeaseAcknowledgementV1, bool]:
        values = (
            record.model_dump_json(),
            idempotency_reservation.model_dump_json(),
            subject_reservation.model_dump_json(),
            audit_evidence.model_dump_json(),
        )
        if max(len(value.encode()) for value in values) > self.max_model_bytes:
            raise ControlledWorkerQueueClaimLeaseAcknowledgementStoreError(
                "record_too_large"
            )
        # Reparse even frozen models: model_construct/model_copy bypass validation.
        record = ControlledWorkerQueueClaimLeaseAcknowledgementV1.model_validate_json(
            values[0]
        )
        idempotency_reservation = ControlledWorkerQueueClaimLeaseAcknowledgementIdempotencyReservationV1.model_validate_json(
            values[1]
        )
        subject_reservation = ControlledWorkerQueueClaimLeaseAcknowledgementSubjectReservationV1.model_validate_json(
            values[2]
        )
        audit_evidence = ControlledWorkerQueueClaimLeaseAcknowledgementAuditEvidenceV1.model_validate_json(
            values[3]
        )
        proposed = {
            "operator_id": record.operator_id,
            "candidate_record_id": record.candidate_record_id,
            "admission_id": record.admission_id,
            "idempotency_key_fingerprint": record.idempotency_key_fingerprint.value,
            "request_fingerprint": idempotency_reservation.request_fingerprint.value,
            "subject_fingerprint": record.subject_fingerprint.value,
            "receipt_record_fingerprint": record.receipt_record_fingerprint.value,
            "admission_valid_until": admission_valid_until,
            "reserved_at": record.recorded_at,
            "idempotency_json": values[1],
            "reservation_json": values[2],
            "attempt_started": "true",
        }
        if not self._is_exact_reservation(
            proposed,
            record,
            idempotency_reservation,
            subject_reservation,
            admission_valid_until,
        ):
            raise ControlledWorkerQueueClaimLeaseAcknowledgementStoreError(
                "store_corrupt"
            )
        self._validate_request(record, proposed)
        if (
            admission_valid_until
            != record.controlled_worker_queue_claim_lease_acknowledgement_admission.valid_until
        ):
            raise ControlledWorkerQueueClaimLeaseAcknowledgementStoreError(
                "store_corrupt"
            )
        if force_indeterminate:
            self._validate_terminal_audit(audit_evidence, proposed)
        else:
            self._validate_record_audit(record, audit_evidence)
        existing = self._reserve_attempt(
            record=record,
            idempotency_reservation=idempotency_reservation,
            subject_reservation=subject_reservation,
            admission_valid_until=admission_valid_until,
            revalidate=revalidate,
        )
        if existing is not None:
            return existing, False
        if force_indeterminate:
            self.mark_indeterminate(
                operator_id=record.operator_id,
                admission_id=record.admission_id,
                audit_evidence=audit_evidence,
            )
            raise ControlledWorkerQueueClaimLeaseAcknowledgementStoreError(
                "append_indeterminate"
            )
        try:
            return self._append_record(
                record=record,
                subject_reservation=subject_reservation,
                audit_json=audit_evidence.model_dump_json(),
                revalidate=revalidate,
            )
        except Exception:  # noqa: BLE001 - fail closed without exposing persisted data
            # The durable reservation is never released, even if commit outcome
            # cannot be determined. An exact readback may still prove success.
            raise ControlledWorkerQueueClaimLeaseAcknowledgementStoreError(
                "append_indeterminate"
            ) from None

    def mark_indeterminate(
        self,
        *,
        operator_id: str,
        admission_id: str,
        audit_evidence: ControlledWorkerQueueClaimLeaseAcknowledgementAuditEvidenceV1,
    ) -> None:
        audit_json = audit_evidence.model_dump_json()
        if len(audit_json.encode()) > self.max_model_bytes:
            raise ControlledWorkerQueueClaimLeaseAcknowledgementStoreError(
                "record_too_large"
            )
        try:
            with self._connect() as connection:
                row = connection.execute(
                    """SELECT * FROM cwqcla_receipt_reservations
                    WHERE operator_id = ? AND admission_id = ?""",
                    (operator_id, admission_id),
                ).fetchone()
                if row is None:
                    raise ControlledWorkerQueueClaimLeaseAcknowledgementStoreError(
                        "not_found"
                    )
                self._validate_reservation(row, operator_id=operator_id)
                audit_evidence = ControlledWorkerQueueClaimLeaseAcknowledgementAuditEvidenceV1.model_validate_json(
                    audit_json
                )
                self._validate_terminal_audit(audit_evidence, row)
                if connection.execute(
                    "SELECT 1 FROM cwqcla_receipts WHERE operator_id = ? AND admission_id = ?",
                    (operator_id, admission_id),
                ).fetchone():
                    raise ControlledWorkerQueueClaimLeaseAcknowledgementStoreError(
                        "conflict"
                    )
                if connection.execute(
                    "SELECT 1 FROM cwqcla_receipt_attempts WHERE operator_id = ? AND admission_id = ?",
                    (operator_id, admission_id),
                ).fetchone():
                    return
                connection.execute(
                    """INSERT OR IGNORE INTO cwqcla_receipt_attempts (
                    operator_id, admission_id, audit_fingerprint, audit_json
                    ) VALUES (?, ?, ?, ?)""",
                    (
                        operator_id,
                        admission_id,
                        audit_evidence.audit_fingerprint.value,
                        audit_json,
                    ),
                )
        except ControlledWorkerQueueClaimLeaseAcknowledgementStoreError:
            raise
        except sqlite3.Error as error:
            raise ControlledWorkerQueueClaimLeaseAcknowledgementStoreError(
                "unavailable"
            ) from error

    def get(
        self, *, operator_id: str, admission_id: str
    ) -> ControlledWorkerQueueClaimLeaseAcknowledgementV1:
        try:
            with self._connect() as connection:
                row = connection.execute(
                    """SELECT * FROM cwqcla_receipts
                    WHERE operator_id = ? AND admission_id = ?""",
                    (operator_id, admission_id),
                ).fetchone()
                reservation = connection.execute(
                    """SELECT * FROM cwqcla_receipt_reservations
                    WHERE operator_id = ? AND admission_id = ?""",
                    (operator_id, admission_id),
                ).fetchone()
        except sqlite3.Error as error:
            raise ControlledWorkerQueueClaimLeaseAcknowledgementStoreError(
                "unavailable"
            ) from error
        if row is None or reservation is None:
            raise ControlledWorkerQueueClaimLeaseAcknowledgementStoreError("not_found")
        return self._decode_record(row, reservation, operator_id=operator_id)

    def list_owned(
        self, *, operator_id: str, candidate_record_id: str
    ) -> tuple[ControlledWorkerQueueClaimLeaseAcknowledgementV1, ...]:
        try:
            with self._connect() as connection:
                rows = connection.execute(
                    """SELECT * FROM cwqcla_receipts
                    WHERE operator_id = ? AND candidate_record_id = ?
                    ORDER BY recorded_at ASC, admission_id ASC
                    LIMIT ?""",
                    (
                        operator_id,
                        candidate_record_id,
                        self.max_records_per_operator + 1,
                    ),
                ).fetchall()
                reservations = {
                    row["admission_id"]: row
                    for row in connection.execute(
                        """SELECT * FROM cwqcla_receipt_reservations
                        WHERE operator_id = ?""",
                        (operator_id,),
                    ).fetchall()
                }
        except sqlite3.Error as error:
            raise ControlledWorkerQueueClaimLeaseAcknowledgementStoreError(
                "unavailable"
            ) from error
        if len(rows) > self.max_records_per_operator:
            raise ControlledWorkerQueueClaimLeaseAcknowledgementStoreError(
                "quota_exceeded"
            )
        return tuple(
            self._decode_record(
                row, reservations.get(row["admission_id"]), operator_id=operator_id
            )
            for row in rows
        )

    def _reserve_attempt(
        self,
        *,
        record: ControlledWorkerQueueClaimLeaseAcknowledgementV1,
        idempotency_reservation: ControlledWorkerQueueClaimLeaseAcknowledgementIdempotencyReservationV1,
        subject_reservation: ControlledWorkerQueueClaimLeaseAcknowledgementSubjectReservationV1,
        admission_valid_until: str,
        revalidate: Callable[[], None] | None = None,
    ) -> ControlledWorkerQueueClaimLeaseAcknowledgementV1 | None:
        idempotency_json = idempotency_reservation.model_dump_json()
        reservation_json = subject_reservation.model_dump_json()
        try:
            with self._connect() as connection:
                rows = connection.execute(
                    """SELECT * FROM cwqcla_receipt_reservations
                    WHERE operator_id = ?
                    AND (idempotency_key_fingerprint = ?
                    OR subject_fingerprint = ?
                    OR admission_id = ?
                    OR receipt_record_fingerprint = ?)""",
                    (
                        record.operator_id,
                        idempotency_reservation.idempotency_key_fingerprint.value,
                        record.subject_fingerprint.value,
                        record.admission_id,
                        record.receipt_record_fingerprint.value,
                    ),
                ).fetchall()
                if rows:
                    if len(rows) != 1:
                        raise ControlledWorkerQueueClaimLeaseAcknowledgementStoreError(
                            "conflict"
                        )
                    row = rows[0]
                    if (
                        row["idempotency_key_fingerprint"]
                        != idempotency_reservation.idempotency_key_fingerprint.value
                    ):
                        raise ControlledWorkerQueueClaimLeaseAcknowledgementStoreError(
                            "permanent_subject_reserved"
                        )
                    if (
                        row["request_fingerprint"]
                        != idempotency_reservation.request_fingerprint.value
                        or row["admission_valid_until"] != admission_valid_until
                    ):
                        raise ControlledWorkerQueueClaimLeaseAcknowledgementStoreError(
                            "idempotency_conflict"
                        )
                    existing = connection.execute(
                        "SELECT * FROM cwqcla_receipts WHERE operator_id = ? AND admission_id = ?",
                        (record.operator_id, row["admission_id"]),
                    ).fetchone()
                    if existing is None:
                        raise ControlledWorkerQueueClaimLeaseAcknowledgementStoreError(
                            "append_indeterminate"
                        )
                    return self._decode_record(
                        existing, row, operator_id=record.operator_id
                    )
                if revalidate is not None:
                    revalidate()
                if (
                    connection.execute(
                        "SELECT COUNT(*) FROM cwqcla_receipt_reservations"
                    ).fetchone()[0]
                    >= self.max_total_records
                ):
                    raise ControlledWorkerQueueClaimLeaseAcknowledgementStoreError(
                        "quota_exceeded"
                    )
                count = connection.execute(
                    """SELECT COUNT(*) FROM cwqcla_receipt_reservations
                    WHERE operator_id = ?""",
                    (record.operator_id,),
                ).fetchone()[0]
                if count >= self.max_records_per_operator:
                    raise ControlledWorkerQueueClaimLeaseAcknowledgementStoreError(
                        "quota_exceeded"
                    )
                connection.execute(
                    """INSERT INTO cwqcla_receipt_reservations (
                    operator_id, candidate_record_id, admission_id,
                    idempotency_key_fingerprint, request_fingerprint,
                    subject_fingerprint, receipt_record_fingerprint,
                    admission_valid_until, reserved_at, idempotency_json,
                    reservation_json, attempt_started
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        record.operator_id,
                        record.candidate_record_id,
                        record.admission_id,
                        idempotency_reservation.idempotency_key_fingerprint.value,
                        idempotency_reservation.request_fingerprint.value,
                        record.subject_fingerprint.value,
                        record.receipt_record_fingerprint.value,
                        admission_valid_until,
                        record.recorded_at,
                        idempotency_json,
                        reservation_json,
                        "true",
                    ),
                )
        except ControlledWorkerQueueClaimLeaseAcknowledgementStoreError:
            raise
        except sqlite3.IntegrityError as error:
            raise ControlledWorkerQueueClaimLeaseAcknowledgementStoreError(
                "conflict"
            ) from error
        except sqlite3.Error as error:
            raise ControlledWorkerQueueClaimLeaseAcknowledgementStoreError(
                "unavailable"
            ) from error

    def _append_record(
        self,
        *,
        record: ControlledWorkerQueueClaimLeaseAcknowledgementV1,
        subject_reservation: ControlledWorkerQueueClaimLeaseAcknowledgementSubjectReservationV1,
        audit_json: str,
        revalidate: Callable[[], None] | None = None,
    ) -> tuple[ControlledWorkerQueueClaimLeaseAcknowledgementV1, bool]:
        try:
            with self._connect() as connection:
                row = connection.execute(
                    """SELECT * FROM cwqcla_receipts
                    WHERE operator_id = ? AND admission_id = ?""",
                    (record.operator_id, record.admission_id),
                ).fetchone()
                reservation = connection.execute(
                    """SELECT * FROM cwqcla_receipt_reservations
                    WHERE operator_id = ? AND admission_id = ?""",
                    (record.operator_id, record.admission_id),
                ).fetchone()
                if reservation is None:
                    raise ControlledWorkerQueueClaimLeaseAcknowledgementStoreError(
                        "reservation_before_effect_failed"
                    )
                if connection.execute(
                    "SELECT 1 FROM cwqcla_receipt_attempts WHERE operator_id = ? AND admission_id = ?",
                    (record.operator_id, record.admission_id),
                ).fetchone():
                    raise ControlledWorkerQueueClaimLeaseAcknowledgementStoreError(
                        "append_indeterminate"
                    )
                if row is not None:
                    existing = self._decode_record(
                        row, reservation, operator_id=record.operator_id
                    )
                    return existing, False
                if revalidate is not None:
                    revalidate()
                connection.execute(
                    """INSERT INTO cwqcla_receipts (
                    operator_id, admission_id, candidate_record_id,
                    idempotency_key_fingerprint, request_fingerprint,
                    subject_fingerprint, receipt_record_fingerprint,
                    v051_admission_record_fingerprint,
                    v051_admission_status_fingerprint,
                    v050_prerequisite_record_fingerprint,
                    v050_prerequisite_status_fingerprint,
                    v049_admission_record_fingerprint,
                    v049_admission_status_fingerprint,
                    binding_subject_fingerprint, worker_subject_fingerprint,
                    queue_item_reference_fingerprint, inherited_limits_fingerprint,
                    adapter_identity_fingerprint, queue_subject_fingerprint,
                    claim_receipt_fingerprint, lease_receipt_fingerprint,
                    acknowledgement_receipt_fingerprint, recorded_at, valid_until,
                    record_json, audit_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        record.operator_id,
                        record.admission_id,
                        record.candidate_record_id,
                        subject_reservation.idempotency_key_fingerprint.value,
                        subject_reservation.request_fingerprint.value,
                        record.subject_fingerprint.value,
                        record.receipt_record_fingerprint.value,
                        record.v051_admission_record_fingerprint.value,
                        record.v051_admission_status_fingerprint.value,
                        record.v050_prerequisite_record_fingerprint.value,
                        record.v050_prerequisite_status_fingerprint.value,
                        record.v049_admission_record_fingerprint.value,
                        record.v049_admission_status_fingerprint.value,
                        record.binding_subject_fingerprint.value,
                        record.worker_subject_fingerprint.value,
                        record.queue_item_reference_fingerprint.value,
                        record.inherited_limits_fingerprint.value,
                        record.adapter_identity_fingerprint.value,
                        record.queue_subject_fingerprint.value,
                        record.claim_receipt_fingerprint.value,
                        record.lease_receipt_fingerprint.value,
                        record.acknowledgement_receipt_fingerprint.value,
                        record.recorded_at,
                        record.valid_until,
                        record.model_dump_json(),
                        audit_json,
                    ),
                )
                return record, True
        except ControlledWorkerQueueClaimLeaseAcknowledgementStoreError:
            raise
        except sqlite3.IntegrityError as error:
            raise ControlledWorkerQueueClaimLeaseAcknowledgementStoreError(
                "conflict"
            ) from error
        except sqlite3.Error as error:
            raise ControlledWorkerQueueClaimLeaseAcknowledgementStoreError(
                "unavailable"
            ) from error

    @staticmethod
    def _is_exact_reservation(
        row: sqlite3.Row,
        record: ControlledWorkerQueueClaimLeaseAcknowledgementV1,
        idempotency_reservation: ControlledWorkerQueueClaimLeaseAcknowledgementIdempotencyReservationV1,
        subject_reservation: ControlledWorkerQueueClaimLeaseAcknowledgementSubjectReservationV1,
        admission_valid_until: str,
    ) -> bool:
        return (
            row["operator_id"] == record.operator_id == subject_reservation.operator_id
            and row["operator_id"] == idempotency_reservation.operator_id
            and row["candidate_record_id"]
            == record.candidate_record_id
            == subject_reservation.candidate_record_id
            == idempotency_reservation.candidate_record_id
            and row["admission_id"]
            == record.admission_id
            == subject_reservation.admission_id
            == idempotency_reservation.admission_id
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
            and row["admission_valid_until"] == admission_valid_until
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
            TypeAdapter(UtcSecond).validate_python(
                row["admission_valid_until"], strict=True
            )
            payloads = (row["idempotency_json"], row["reservation_json"])
            if max(len(value.encode()) for value in payloads) > self.max_model_bytes:
                raise ValueError("persisted reservation exceeds bound")
            idempotency = ControlledWorkerQueueClaimLeaseAcknowledgementIdempotencyReservationV1.model_validate_json(
                row["idempotency_json"]
            )
            reservation = ControlledWorkerQueueClaimLeaseAcknowledgementSubjectReservationV1.model_validate_json(
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
            raise ControlledWorkerQueueClaimLeaseAcknowledgementStoreError(
                "store_corrupt"
            ) from error

    @staticmethod
    def _is_row_reservation_exact(
        row: sqlite3.Row,
        idempotency: ControlledWorkerQueueClaimLeaseAcknowledgementIdempotencyReservationV1,
        reservation: ControlledWorkerQueueClaimLeaseAcknowledgementSubjectReservationV1,
    ) -> bool:
        return (
            row["operator_id"] == idempotency.operator_id == reservation.operator_id
            and row["candidate_record_id"]
            == idempotency.candidate_record_id
            == reservation.candidate_record_id
            and row["admission_id"]
            == idempotency.admission_id
            == reservation.admission_id
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
            and row["reserved_at"] < row["admission_valid_until"]
            and row["idempotency_json"] == idempotency.model_dump_json()
            and row["reservation_json"] == reservation.model_dump_json()
        )

    def _decode_record(
        self,
        row: sqlite3.Row,
        reservation_row: sqlite3.Row | None,
        *,
        operator_id: str,
    ) -> ControlledWorkerQueueClaimLeaseAcknowledgementV1:
        try:
            self._validate_reservation(reservation_row, operator_id=operator_id)
            payloads = (row["record_json"], row["audit_json"])
            if max(len(value.encode()) for value in payloads) > self.max_model_bytes:
                raise ValueError("persisted record exceeds bound")
            record = (
                ControlledWorkerQueueClaimLeaseAcknowledgementV1.model_validate_json(
                    row["record_json"]
                )
            )
            audit = ControlledWorkerQueueClaimLeaseAcknowledgementAuditEvidenceV1.model_validate_json(
                row["audit_json"]
            )
            if (
                operator_id != row["operator_id"]
                or record.receipt_record_fingerprint
                != receipt_record_fingerprint(record)
                or audit.audit_fingerprint != audit_fingerprint(audit)
                or row["operator_id"] != record.operator_id
                or row["candidate_record_id"] != record.candidate_record_id
                or row["admission_id"] != record.admission_id
                or row["idempotency_key_fingerprint"]
                != reservation_row["idempotency_key_fingerprint"]
                or row["request_fingerprint"] != reservation_row["request_fingerprint"]
                or row["subject_fingerprint"] != reservation_row["subject_fingerprint"]
                or row["receipt_record_fingerprint"]
                != reservation_row["receipt_record_fingerprint"]
                or row["recorded_at"] != reservation_row["reserved_at"]
                or row["idempotency_key_fingerprint"]
                != record.idempotency_key_fingerprint.value
                or row["subject_fingerprint"] != record.subject_fingerprint.value
                or row["receipt_record_fingerprint"]
                != record.receipt_record_fingerprint.value
                or row["v051_admission_record_fingerprint"]
                != record.v051_admission_record_fingerprint.value
                or row["v051_admission_status_fingerprint"]
                != record.v051_admission_status_fingerprint.value
                or reservation_row["admission_valid_until"]
                != record.controlled_worker_queue_claim_lease_acknowledgement_admission.valid_until
                or row["v050_prerequisite_record_fingerprint"]
                != record.v050_prerequisite_record_fingerprint.value
                or row["v050_prerequisite_status_fingerprint"]
                != record.v050_prerequisite_status_fingerprint.value
                or row["v049_admission_record_fingerprint"]
                != record.v049_admission_record_fingerprint.value
                or row["v049_admission_status_fingerprint"]
                != record.v049_admission_status_fingerprint.value
                or row["binding_subject_fingerprint"]
                != record.binding_subject_fingerprint.value
                or row["worker_subject_fingerprint"]
                != record.worker_subject_fingerprint.value
                or row["queue_item_reference_fingerprint"]
                != record.queue_item_reference_fingerprint.value
                or row["inherited_limits_fingerprint"]
                != record.inherited_limits_fingerprint.value
                or row["adapter_identity_fingerprint"]
                != record.adapter_identity_fingerprint.value
                or row["queue_subject_fingerprint"]
                != record.queue_subject_fingerprint.value
                or row["claim_receipt_fingerprint"]
                != record.claim_receipt_fingerprint.value
                or row["lease_receipt_fingerprint"]
                != record.lease_receipt_fingerprint.value
                or row["acknowledgement_receipt_fingerprint"]
                != record.acknowledgement_receipt_fingerprint.value
                or row["recorded_at"] != record.recorded_at
                or row["valid_until"] != record.valid_until
            ):
                raise ValueError("persisted record mismatch")
            self._validate_record_audit(record, audit)
            self._validate_request(record, reservation_row)
            return record
        except ControlledWorkerQueueClaimLeaseAcknowledgementStoreError:
            raise
        except Exception as error:
            raise ControlledWorkerQueueClaimLeaseAcknowledgementStoreError(
                "store_corrupt"
            ) from error

    @staticmethod
    def _validate_record_audit(record, audit) -> None:
        if (
            audit.event
            != "controlled_worker_queue_claim_lease_acknowledgement_recorded"
            or audit.outcome != "recorded"
            or not audit.controlled_worker_queue_claim_lease_acknowledgement_recorded
            or audit.operator_id != record.operator_id
            or audit.candidate_record_id != record.candidate_record_id
            or audit.admission_id != record.admission_id
            or audit.subject_fingerprint != record.subject_fingerprint
            or audit.receipt_record_fingerprint != record.receipt_record_fingerprint
            or audit.occurred_at != record.recorded_at
        ):
            raise ControlledWorkerQueueClaimLeaseAcknowledgementStoreError(
                "store_corrupt"
            )

    @staticmethod
    def _validate_request(record, reservation) -> None:
        create = build_create(
            admission=record.controlled_worker_queue_claim_lease_acknowledgement_admission,
            admission_status=record.controlled_worker_queue_claim_lease_acknowledgement_admission_status,
            adapter_receipt=record.adapter_receipt,
        )
        expected = request_fingerprint(
            operator_id=record.operator_id,
            candidate_record_id=record.candidate_record_id,
            create=create,
            request_received_at=record.recorded_at,
            idempotency_fingerprint=record.idempotency_key_fingerprint,
        )
        if reservation["request_fingerprint"] != expected.value:
            raise ControlledWorkerQueueClaimLeaseAcknowledgementStoreError(
                "store_corrupt"
            )
