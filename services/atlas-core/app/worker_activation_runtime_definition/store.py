"""Bounded, append-only persistence for reference-only runtime definitions."""
from __future__ import annotations

import sqlite3
from contextlib import closing
from pathlib import Path
from . import contract as c

MAX_RECORDS_PER_OPERATOR = 16
MAX_TOTAL_RECORDS = 256
MAX_DATABASE_BYTES = 256 * 1024 * 1024

class WorkerActivationRuntimeDefinitionStoreError(RuntimeError):
    def __init__(self, code: str):
        allowed = {"unauthenticated", "forbidden", "invalid_request", "store_corrupt", "unavailable", "quota_exceeded", "record_too_large", "idempotency_conflict", "permanent_subject_reserved", "append_indeterminate", "definition_not_found"}
        self.code = code if code in allowed else "invalid_request"
        super().__init__(self.code)

class WorkerActivationRuntimeDefinitionStore:
    def __init__(self, database_path: str | Path, *, max_records_per_operator=MAX_RECORDS_PER_OPERATOR, max_total_records=MAX_TOTAL_RECORDS, max_model_bytes=c.MAX_MODEL_BYTES, max_database_bytes=MAX_DATABASE_BYTES):
        if any(type(v) is not int or v < 0 or v > limit for v, limit in ((max_records_per_operator, MAX_RECORDS_PER_OPERATOR), (max_total_records, MAX_TOTAL_RECORDS), (max_model_bytes, c.MAX_MODEL_BYTES), (max_database_bytes, MAX_DATABASE_BYTES))):
            raise WorkerActivationRuntimeDefinitionStoreError("invalid_request")
        self.database_path = Path(database_path).resolve()
        self.max_records_per_operator, self.max_total_records = max_records_per_operator, max_total_records
        self.max_model_bytes, self.max_database_bytes = max_model_bytes, max_database_bytes
        self._initialized = False
        with self._connect(create=True) as db:
            marker = db.execute("PRAGMA application_id").fetchone()[0]
            tables = set(db.execute("SELECT name FROM sqlite_master WHERE type='table'"))
            expected = {("reservations",), ("evidence",), ("failures",)}
            if tables - expected or (tables and marker != 64):
                raise WorkerActivationRuntimeDefinitionStoreError("store_corrupt")
            if not tables:
                db.executescript("CREATE TABLE reservations(subject TEXT PRIMARY KEY, operator_id TEXT NOT NULL, candidate_record_id TEXT NOT NULL, definition_id TEXT NOT NULL, idem TEXT NOT NULL, request TEXT NOT NULL, reservation_json TEXT NOT NULL, UNIQUE(operator_id, idem), UNIQUE(operator_id, candidate_record_id, definition_id)); CREATE TABLE evidence(subject TEXT PRIMARY KEY REFERENCES reservations(subject), record_json TEXT NOT NULL, audit_json TEXT NOT NULL); CREATE TABLE failures(subject TEXT PRIMARY KEY REFERENCES reservations(subject), audit_json TEXT NOT NULL);")
                db.execute("PRAGMA application_id=64")
            self._check(db)
        self._initialized = True

    def _connect(self, *, create=False):
        try:
            mode = "rwc" if create and not self._initialized else "rw"
            return _Connection(self.database_path, mode, self)
        except sqlite3.Error as e:
            raise WorkerActivationRuntimeDefinitionStoreError("unavailable") from e

    def _check(self, db):
        try:
            if db.execute("PRAGMA integrity_check").fetchone() != ("ok",) or db.execute("PRAGMA application_id").fetchone()[0] != 64 or db.execute("PRAGMA page_count").fetchone()[0] * db.execute("PRAGMA page_size").fetchone()[0] > self.max_database_bytes:
                raise ValueError
            for table in ("reservations", "evidence", "failures"):
                if db.execute(f"SELECT count(*) FROM {table}").fetchone()[0] > self.max_total_records:
                    raise ValueError
            for row in db.execute("SELECT subject, operator_id, candidate_record_id, definition_id, idem, request, reservation_json FROM reservations"):
                reservation = self._decode(c.WorkerActivationRuntimeDefinitionSubjectReservationV1, row[6])
                if row[:6] != (reservation.subject_fingerprint.value, reservation.operator_id, reservation.candidate_record_id, reservation.definition_id, reservation.idempotency_key_fingerprint.value, reservation.request_fingerprint.value): raise ValueError
            for subject, payload, audit in db.execute("SELECT subject, record_json, audit_json FROM evidence"):
                record = self._decode(c.WorkerActivationRuntimeDefinitionV1Record, payload); self._decode(c.WorkerActivationRuntimeDefinitionAuditV1, audit)
                if record.subject_fingerprint.value != subject: raise ValueError
            for subject, audit in db.execute("SELECT subject, audit_json FROM failures"):
                self._decode(c.WorkerActivationRuntimeDefinitionAuditV1, audit)
        except Exception as e:
            raise WorkerActivationRuntimeDefinitionStoreError("store_corrupt") from e

    def _decode(self, model, payload):
        if type(payload) is not str or len(payload.encode()) > self.max_model_bytes: raise ValueError
        result = model.model_validate_json(payload)
        if result.model_dump_json() != payload: raise ValueError
        return result

    def resolve(self, operator_id, idem, request):
        with self._connect() as db:
            row = db.execute("SELECT subject, request FROM reservations WHERE operator_id=? AND idem=?", (operator_id, idem)).fetchone()
            if row is None: return None
            if row[1] != request: raise WorkerActivationRuntimeDefinitionStoreError("idempotency_conflict")
            result = db.execute("SELECT record_json FROM evidence WHERE subject=?", (row[0],)).fetchone()
            if result is None: raise WorkerActivationRuntimeDefinitionStoreError("append_indeterminate")
            return self._decode(c.WorkerActivationRuntimeDefinitionV1Record, result[0])

    def append(self, reservation, prepare, revalidate, correlation):
        attempted = False
        try:
            with self._connect() as db:
                row = db.execute("SELECT subject, request FROM reservations WHERE operator_id=? AND idem=?", (reservation.operator_id, reservation.idempotency_key_fingerprint.value)).fetchone()
                if row is not None:
                    if row[1] != reservation.request_fingerprint.value: raise WorkerActivationRuntimeDefinitionStoreError("idempotency_conflict")
                    existing_row = db.execute("SELECT record_json FROM evidence WHERE subject=?", (row[0],)).fetchone()
                    if existing_row is None: raise WorkerActivationRuntimeDefinitionStoreError("append_indeterminate")
                    return self._decode(c.WorkerActivationRuntimeDefinitionV1Record, existing_row[0]), False
                if db.execute("SELECT 1 FROM reservations WHERE subject=?", (reservation.subject_fingerprint.value,)).fetchone(): raise WorkerActivationRuntimeDefinitionStoreError("permanent_subject_reserved")
                if db.execute("SELECT count(*) FROM reservations").fetchone()[0] >= self.max_total_records or db.execute("SELECT count(*) FROM reservations WHERE operator_id=?", (reservation.operator_id,)).fetchone()[0] >= self.max_records_per_operator: raise WorkerActivationRuntimeDefinitionStoreError("quota_exceeded")
                record = c.WorkerActivationRuntimeDefinitionV1Record.model_validate(prepare()); audit = _audit(reservation, correlation, record)
                for model in (record, audit):
                    if len(model.model_dump_json().encode()) > self.max_model_bytes: raise WorkerActivationRuntimeDefinitionStoreError("record_too_large")
                attempted = True
                db.execute("INSERT INTO reservations VALUES (?,?,?,?,?,?,?)", (reservation.subject_fingerprint.value, reservation.operator_id, reservation.candidate_record_id, reservation.definition_id, reservation.idempotency_key_fingerprint.value, reservation.request_fingerprint.value, reservation.model_dump_json()))
            with self._connect() as db:
                revalidate(record)
                db.execute("INSERT INTO evidence VALUES (?,?,?)", (reservation.subject_fingerprint.value, record.model_dump_json(), audit.model_dump_json()))
            return record, True
        except WorkerActivationRuntimeDefinitionStoreError:
            if attempted: self._failure(reservation, correlation)
            raise
        except Exception:
            if attempted: self._failure(reservation, correlation)
            raise WorkerActivationRuntimeDefinitionStoreError("append_indeterminate" if attempted else "invalid_request") from None

    def _failure(self, reservation, correlation):
        try:
            with self._connect() as db:
                if not db.execute("SELECT 1 FROM evidence WHERE subject=?", (reservation.subject_fingerprint.value,)).fetchone(): db.execute("INSERT OR IGNORE INTO failures VALUES (?,?)", (reservation.subject_fingerprint.value, _audit(reservation, correlation, None).model_dump_json()))
        except Exception: pass

    def get(self, operator_id, candidate_record_id, definition_id):
        with self._connect() as db:
            row = db.execute("SELECT record_json FROM evidence WHERE subject IN (SELECT subject FROM reservations WHERE operator_id=? AND candidate_record_id=? AND definition_id=?)", (operator_id, candidate_record_id, definition_id)).fetchone()
            if row: return self._decode(c.WorkerActivationRuntimeDefinitionV1Record, row[0])
        raise WorkerActivationRuntimeDefinitionStoreError("definition_not_found")

    def list_owned(self, operator_id, candidate_record_id):
        with self._connect() as db:
            return tuple(self._decode(c.WorkerActivationRuntimeDefinitionV1Record, row[0]) for row in db.execute("SELECT record_json FROM evidence JOIN reservations USING(subject) WHERE operator_id=? AND candidate_record_id=? ORDER BY subject", (operator_id, candidate_record_id)))

class _Connection:
    def __init__(self, path, mode, store):
        self.db = sqlite3.connect(f"file:{path}?mode={mode}", uri=True, timeout=5, isolation_level=None)
        self.store = store
        self.db.execute("PRAGMA foreign_keys=ON")
        self.db.execute("PRAGMA synchronous=FULL")
        size = self.db.execute("PRAGMA page_size").fetchone()[0]
        if self.store.max_database_bytes < size: raise WorkerActivationRuntimeDefinitionStoreError("quota_exceeded")
        self.db.execute(f"PRAGMA max_page_count={self.store.max_database_bytes // size}")
        self.db.execute("BEGIN IMMEDIATE")
    def __enter__(self): return self.db
    def __exit__(self, typ, value, tb):
        if typ: self.db.rollback()
        else: self.db.commit()
        self.db.close()

def _audit(reservation, correlation, record):
    raw = {"operator_id": reservation.operator_id, "candidate_record_id": reservation.candidate_record_id, "occurred_at": reservation.reserved_at, "outcome": "recorded" if record else "indeterminate", "subject_fingerprint": reservation.subject_fingerprint, "correlation_fingerprint": correlation, "record_fingerprint": record.record_fingerprint if record else None}
    return c.WorkerActivationRuntimeDefinitionAuditV1.model_validate({**raw, "audit_fingerprint": c.audit_fingerprint(raw)})
