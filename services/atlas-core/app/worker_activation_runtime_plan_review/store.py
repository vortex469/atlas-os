"""Explicit bounded SQLite evidence journal; permanent reservations, no effects."""

from __future__ import annotations

import sqlite3
from collections import Counter
from collections.abc import Callable, Iterator
from contextlib import closing, contextmanager
from pathlib import Path

from . import contract as c

MAX_RECORDS_PER_OPERATOR = 16
MAX_TOTAL_RECORDS = 256
MAX_DATABASE_BYTES = 256 * 1024 * 1024
_SCHEMA = (
    """CREATE TABLE reservations (
        subject TEXT PRIMARY KEY NOT NULL,
        operator_id TEXT NOT NULL,
        candidate_record_id TEXT NOT NULL,
        runtime_plan_id TEXT NOT NULL,
        idem TEXT NOT NULL,
        request TEXT NOT NULL,
        reservation_json TEXT NOT NULL,
        UNIQUE (operator_id, idem),
        UNIQUE (operator_id, candidate_record_id, runtime_plan_id))""",
    """CREATE TABLE evidence (
        subject TEXT PRIMARY KEY NOT NULL REFERENCES reservations(subject),
        record_json TEXT NOT NULL,
        audit_json TEXT NOT NULL)""",
    """CREATE TABLE failures (
        subject TEXT PRIMARY KEY NOT NULL REFERENCES reservations(subject),
        audit_json TEXT NOT NULL)""",
)


class WorkerActivationRuntimePlanReviewStoreError(RuntimeError):
    """Only closed codes may cross the storage boundary."""

    def __init__(self, code: str) -> None:
        allowed = {
            "unauthenticated",
            "forbidden",
            "installation_capability_unsupported",
            "ambiguous_state",
            "fingerprint_mismatch",
            "linkage_mismatch",
            "evidence_stale",
            "evidence_expired",
            "v055_plan_not_active",
            "store_corrupt",
            "unavailable",
            "invalid_request",
            "quota_exceeded",
            "record_too_large",
            "idempotency_conflict",
            "permanent_subject_reserved",
            "append_indeterminate",
            "evidence_not_found",
        }
        self.code = code if code in allowed else "invalid_request"
        super().__init__(self.code)


class WorkerActivationRuntimePlanReviewStore:
    def __init__(
        self,
        database_path: str | Path,
        *,
        max_records_per_operator: int = MAX_RECORDS_PER_OPERATOR,
        max_total_records: int = MAX_TOTAL_RECORDS,
        max_model_bytes: int = c.MAX_MODEL_BYTES,
        max_database_bytes: int = MAX_DATABASE_BYTES,
    ) -> None:
        for value, maximum in (
            (max_records_per_operator, MAX_RECORDS_PER_OPERATOR),
            (max_total_records, MAX_TOTAL_RECORDS),
            (max_model_bytes, c.MAX_MODEL_BYTES),
            (max_database_bytes, MAX_DATABASE_BYTES),
        ):
            if type(value) is not int or not 0 <= value <= maximum:
                raise WorkerActivationRuntimePlanReviewStoreError("invalid_request")
        self.database_path = Path(database_path)
        self.max_records_per_operator = max_records_per_operator
        self.max_total_records = max_total_records
        self.max_model_bytes = max_model_bytes
        self.max_database_bytes = max_database_bytes
        with closing(sqlite3.connect(":memory:")) as reference:
            for statement in _SCHEMA:
                reference.execute(statement)
            self._schema = set(reference.execute("SELECT name, sql FROM sqlite_master"))
        self._initialized = False
        with self._connect() as connection:
            actual = set(connection.execute("SELECT name, sql FROM sqlite_master"))
            marker = connection.execute("PRAGMA application_id").fetchone()[0]
            if actual:
                if actual != self._schema or marker != 56:
                    raise WorkerActivationRuntimePlanReviewStoreError("store_corrupt")
            else:
                if marker != 0:
                    raise WorkerActivationRuntimePlanReviewStoreError("store_corrupt")
                for statement in _SCHEMA:
                    connection.execute(statement)
                connection.execute("PRAGMA application_id=56")
            self._check_integrity(connection)
        self._initialized = True

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        connection = None
        try:
            connection = sqlite3.connect(
                self.database_path, timeout=5, isolation_level=None
            )
            connection.execute("PRAGMA foreign_keys=ON")
            connection.execute("PRAGMA synchronous=FULL")
            size = connection.execute("PRAGMA page_size").fetchone()[0]
            if self.max_database_bytes < size:
                raise WorkerActivationRuntimePlanReviewStoreError("quota_exceeded")
            connection.execute(
                f"PRAGMA max_page_count={self.max_database_bytes // size}"
            )
            connection.execute("BEGIN IMMEDIATE")
            if self._initialized:
                self._check_integrity(connection)
            yield connection
            connection.execute("COMMIT")
        except sqlite3.Error as error:
            code = (
                "unavailable"
                if isinstance(error, sqlite3.OperationalError)
                else "store_corrupt"
            )
            raise WorkerActivationRuntimePlanReviewStoreError(code) from None
        finally:
            if connection is not None:
                try:
                    if connection.in_transaction:
                        connection.rollback()
                finally:
                    connection.close()

    def _decode(self, model, payload):
        if type(payload) is not str or len(payload.encode()) > self.max_model_bytes:
            raise ValueError("payload bound")
        value = model.model_validate_json(payload)
        if payload != value.model_dump_json():
            raise ValueError("noncanonical persisted model")
        return value

    def _check_integrity(self, connection):
        try:
            if (
                set(connection.execute("SELECT name, sql FROM sqlite_master"))
                != self._schema
                or connection.execute("PRAGMA application_id").fetchone()[0] != 56
                or connection.execute("PRAGMA integrity_check").fetchall() != [("ok",)]
                or connection.execute("PRAGMA foreign_key_check").fetchone() is not None
                or connection.execute("PRAGMA page_count").fetchone()[0]
                * connection.execute("PRAGMA page_size").fetchone()[0]
                > self.max_database_bytes
            ):
                raise ValueError("schema or integrity")
            for table in ("reservations", "evidence", "failures"):
                if (
                    connection.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
                    > self.max_total_records
                ):
                    raise ValueError("bound")
                columns = (
                    ("record_json", "audit_json")
                    if table == "evidence"
                    else (
                        "reservation_json" if table == "reservations" else "audit_json",
                    )
                )
                for column in columns:
                    if connection.execute(
                        f"SELECT 1 FROM {table} WHERE typeof({column}) != 'text' "
                        f"OR length(CAST({column} AS BLOB)) > ? LIMIT 1",
                        (self.max_model_bytes,),
                    ).fetchone():
                        raise ValueError("payload bound")
            reservations = {}
            owners = Counter()
            for row in connection.execute("SELECT * FROM reservations"):
                reservation = self._decode(
                    c.WorkerActivationRuntimePlanReviewSubjectReservationV1, row[6]
                )
                if row[:6] != (
                    reservation.subject_fingerprint.value,
                    reservation.operator_id,
                    reservation.candidate_record_id,
                    reservation.runtime_plan_id,
                    reservation.idempotency_key_fingerprint.value,
                    reservation.request_fingerprint.value,
                ):
                    raise ValueError("reservation index mismatch")
                reservations[row[0]] = reservation
                owners[reservation.operator_id] += 1
            if any(count > self.max_records_per_operator for count in owners.values()):
                raise ValueError("owner bound")
            completed = set()
            for subject, record_json, audit_json in connection.execute(
                "SELECT * FROM evidence"
            ):
                reservation = reservations[subject]
                record = self._decode(
                    c.WorkerActivationRuntimePlanReviewV1, record_json
                )
                audit = self._decode(
                    c.WorkerActivationRuntimePlanReviewAuditEvidenceV1, audit_json
                )
                self._validate_record(record, reservation)
                self._validate_audit(audit, reservation, record)
                completed.add(subject)
            for subject, audit_json in connection.execute("SELECT * FROM failures"):
                if subject in completed:
                    raise ValueError("multiple terminal outcomes")
                audit = self._decode(
                    c.WorkerActivationRuntimePlanReviewAuditEvidenceV1, audit_json
                )
                self._validate_audit(audit, reservations[subject], None)
        except Exception:  # noqa: BLE001 - dependency and persisted details stay redacted
            raise WorkerActivationRuntimePlanReviewStoreError("store_corrupt") from None

    @staticmethod
    def _validate_record(record, reservation):
        create = c.build_create(
            receipt=record.worker_activation_runtime_plan,
            receipt_status=record.worker_activation_runtime_plan_status,
        )
        if (
            record.operator_id != reservation.operator_id
            or record.candidate_record_id != reservation.candidate_record_id
            or record.runtime_plan_id != reservation.runtime_plan_id
            or record.subject_fingerprint != reservation.subject_fingerprint
            or record.idempotency_key_fingerprint
            != reservation.idempotency_key_fingerprint
            or record.recorded_at != reservation.reserved_at
            or c.request_fingerprint(
                operator_id=record.operator_id,
                candidate_record_id=record.candidate_record_id,
                create=create,
            )
            != reservation.request_fingerprint
        ):
            raise ValueError("record linkage")

    @staticmethod
    def _validate_audit(audit, reservation, record):
        if (
            audit.operator_id != reservation.operator_id
            or audit.candidate_record_id != reservation.candidate_record_id
            or audit.subject_fingerprint != reservation.subject_fingerprint
            or audit.occurred_at != reservation.reserved_at
            or audit.outcome != ("recorded" if record is not None else "indeterminate")
            or audit.runtime_plan_review_record_fingerprint
            != (
                record.runtime_plan_review_record_fingerprint
                if record is not None
                else None
            )
        ):
            raise ValueError("audit linkage")

    def _resolve(self, connection, operator_id, idem, request):
        row = connection.execute(
            "SELECT subject, request FROM reservations WHERE operator_id=? AND idem=?",
            (operator_id, idem),
        ).fetchone()
        if row is None:
            return None
        if row[1] != request:
            raise WorkerActivationRuntimePlanReviewStoreError("idempotency_conflict")
        evidence = connection.execute(
            "SELECT record_json FROM evidence WHERE subject=?", (row[0],)
        ).fetchone()
        if evidence is None:
            raise WorkerActivationRuntimePlanReviewStoreError("append_indeterminate")
        return self._decode(c.WorkerActivationRuntimePlanReviewV1, evidence[0])

    def resolve_idempotency(
        self, *, operator_id, idempotency_key_fingerprint, request_fingerprint
    ):
        with self._connect() as connection:
            return self._resolve(
                connection,
                operator_id,
                idempotency_key_fingerprint,
                request_fingerprint,
            )

    def append(
        self,
        *,
        reservation,
        prepare: Callable,
        revalidate: Callable,
        correlation_fingerprint,
    ):
        """Commit reservation first; only this call can attempt its terminal append.

        prepare and revalidate run under separate SQLite write locks. A crash
        between them leaves a permanent incomplete reservation, never resumable.
        """
        reservation_attempted = False
        try:
            reservation = (
                c.WorkerActivationRuntimePlanReviewSubjectReservationV1.model_validate(
                    reservation
                )
            )
            self._bounded(reservation)
            with self._connect() as connection:
                existing = self._resolve(
                    connection,
                    reservation.operator_id,
                    reservation.idempotency_key_fingerprint.value,
                    reservation.request_fingerprint.value,
                )
                if existing is not None:
                    return existing, False
                if connection.execute(
                    "SELECT 1 FROM reservations WHERE subject=?",
                    (reservation.subject_fingerprint.value,),
                ).fetchone():
                    raise WorkerActivationRuntimePlanReviewStoreError(
                        "permanent_subject_reserved"
                    )
                if (
                    connection.execute("SELECT count(*) FROM reservations").fetchone()[
                        0
                    ]
                    >= self.max_total_records
                    or connection.execute(
                        "SELECT count(*) FROM reservations WHERE operator_id=?",
                        (reservation.operator_id,),
                    ).fetchone()[0]
                    >= self.max_records_per_operator
                ):
                    raise WorkerActivationRuntimePlanReviewStoreError("quota_exceeded")
                record = c.WorkerActivationRuntimePlanReviewV1.model_validate(prepare())
                self._validate_record(record, reservation)
                audit = self._audit(reservation, correlation_fingerprint, record)
                for model in (record, audit):
                    self._bounded(model)
                reservation_attempted = True
                connection.execute(
                    "INSERT INTO reservations VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (
                        reservation.subject_fingerprint.value,
                        reservation.operator_id,
                        reservation.candidate_record_id,
                        reservation.runtime_plan_id,
                        reservation.idempotency_key_fingerprint.value,
                        reservation.request_fingerprint.value,
                        reservation.model_dump_json(),
                    ),
                )
        except WorkerActivationRuntimePlanReviewStoreError:
            if reservation_attempted:
                raise WorkerActivationRuntimePlanReviewStoreError(
                    "append_indeterminate"
                ) from None
            raise
        except Exception:  # noqa: BLE001 - dependency and persisted details stay redacted
            raise WorkerActivationRuntimePlanReviewStoreError(
                "append_indeterminate" if reservation_attempted else "invalid_request"
            ) from None
        try:
            self._append_record(record, reservation, audit, revalidate)
            return record, True
        except Exception:  # noqa: BLE001 - dependency and persisted details stay redacted
            # Best effort terminal audit; failure cannot undo the committed reservation.
            try:
                self._append_failure(reservation, correlation_fingerprint)
            except Exception:  # noqa: BLE001, S110 - audit failure cannot undo reservation; never log secrets
                pass
            raise WorkerActivationRuntimePlanReviewStoreError(
                "append_indeterminate"
            ) from None

    def _append_record(self, record, reservation, audit, revalidate):
        with self._connect() as connection:
            subject = reservation.subject_fingerprint.value
            row = connection.execute(
                "SELECT reservation_json FROM reservations WHERE subject=?", (subject,)
            ).fetchone()
            if (
                row != (reservation.model_dump_json(),)
                or connection.execute(
                    "SELECT 1 FROM failures WHERE subject=?", (subject,)
                ).fetchone()
            ):
                raise WorkerActivationRuntimePlanReviewStoreError(
                    "append_indeterminate"
                )
            revalidate(record)
            connection.execute(
                "INSERT INTO evidence VALUES (?, ?, ?)",
                (subject, record.model_dump_json(), audit.model_dump_json()),
            )

    def _append_failure(self, reservation, correlation):
        audit = self._audit(reservation, correlation, None)
        self._bounded(audit)
        with self._connect() as connection:
            subject = reservation.subject_fingerprint.value
            if connection.execute(
                "SELECT 1 FROM evidence WHERE subject=?", (subject,)
            ).fetchone():
                return
            connection.execute(
                "INSERT INTO failures VALUES (?, ?)", (subject, audit.model_dump_json())
            )

    @staticmethod
    def _audit(reservation, correlation, record):
        raw = {
            "operator_id": reservation.operator_id,
            "candidate_record_id": reservation.candidate_record_id,
            "occurred_at": reservation.reserved_at,
            "outcome": "recorded" if record is not None else "indeterminate",
            "subject_fingerprint": reservation.subject_fingerprint,
            "correlation_fingerprint": correlation,
            "runtime_plan_review_record_fingerprint": record.runtime_plan_review_record_fingerprint
            if record is not None
            else None,
            "worker_activation_runtime_plan_review_recorded": record is not None,
            "worker_activation_runtime_plan_recorded": record is not None,
        }
        return c._signed(
            c.WorkerActivationRuntimePlanReviewAuditEvidenceV1,
            raw,
            "audit_fingerprint",
            c.audit_fingerprint,
        )

    def _bounded(self, model):
        if len(model.model_dump_json().encode()) > self.max_model_bytes:
            raise WorkerActivationRuntimePlanReviewStoreError("record_too_large")

    def get(self, *, operator_id, candidate_record_id, runtime_plan_review_id):
        with self._connect() as connection:
            for (payload,) in connection.execute(
                "SELECT record_json FROM evidence JOIN reservations USING(subject) "
                "WHERE operator_id=? AND candidate_record_id=?",
                (operator_id, candidate_record_id),
            ):
                record = self._decode(c.WorkerActivationRuntimePlanReviewV1, payload)
                if record.runtime_plan_review_id == runtime_plan_review_id:
                    return record
        raise WorkerActivationRuntimePlanReviewStoreError("evidence_not_found")

    def list_owned(self, *, operator_id, candidate_record_id):
        with self._connect() as connection:
            return tuple(
                self._decode(c.WorkerActivationRuntimePlanReviewV1, row[0])
                for row in connection.execute(
                    "SELECT record_json FROM evidence JOIN reservations USING(subject) "
                    "WHERE operator_id=? AND candidate_record_id=? ORDER BY subject",
                    (operator_id, candidate_record_id),
                )
            )
