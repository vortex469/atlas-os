"""Bounded durable storage for inert control-plane evidence."""

from __future__ import annotations

import logging
import sqlite3
import time
from collections.abc import Callable
from pathlib import Path
from typing import ClassVar

from . import contract as c

LOGGER = logging.getLogger(__name__)

MAX_RECORDS_PER_OWNER = 16
MAX_TOTAL_RECORDS = 256
MAX_DATABASE_BYTES = 8 * 1024 * 1024


class ControlPlaneStoreError(RuntimeError):
    CODES: ClassVar[set[str]] = {
        "unauthenticated", "forbidden", "disabled", "invalid_request", "expired",
        "foreign_lineage", "policy_widening", "fingerprint_mismatch", "ambiguous_state",
        "authority_payload",
        "store_corrupt", "unavailable", "quota_exceeded", "idempotency_conflict",
        "permanent_subject_reserved", "append_indeterminate", "evidence_not_found",
    }

    def __init__(self, code: str):
        self.code = code if code in self.CODES else "unavailable"
        super().__init__(self.code)


class ControlPlaneEvidenceStore:
    def __init__(self, database_path: str | Path, *, max_records_per_owner=MAX_RECORDS_PER_OWNER,
                 max_total_records=MAX_TOTAL_RECORDS, max_database_bytes=MAX_DATABASE_BYTES):
        if (type(max_records_per_owner) is not int or not 1 <= max_records_per_owner <= MAX_RECORDS_PER_OWNER
                or type(max_total_records) is not int or not 1 <= max_total_records <= MAX_TOTAL_RECORDS
                or type(max_database_bytes) is not int or not 1 <= max_database_bytes <= MAX_DATABASE_BYTES):
            raise ControlPlaneStoreError("unavailable")
        self.database_path = Path(database_path).resolve()
        self.max_records_per_owner = max_records_per_owner
        self.max_total_records = max_total_records
        self.max_database_bytes = max_database_bytes
        try:
            with self._connect(create=True) as db:
                marker = db.execute("PRAGMA application_id").fetchone()[0]
                tables = {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
                expected = {"reservations", "evidence", "failures"}
                if tables - expected or (tables and marker != 65):
                    raise ControlPlaneStoreError("store_corrupt")
                if not tables:
                    db.executescript(
                        "CREATE TABLE reservations(subject TEXT PRIMARY KEY, owner TEXT NOT NULL, idem TEXT NOT NULL, request TEXT NOT NULL, reservation_json TEXT NOT NULL, UNIQUE(owner, idem));"
                        "CREATE TABLE evidence(subject TEXT PRIMARY KEY REFERENCES reservations(subject), owner TEXT NOT NULL, record_json TEXT NOT NULL);"
                        "CREATE TABLE failures(subject TEXT PRIMARY KEY REFERENCES reservations(subject), audit TEXT NOT NULL);"
                    )
                    db.execute("PRAGMA application_id=65")
                self._check(db)
        except ControlPlaneStoreError:
            raise
        except (sqlite3.Error, OSError) as error:
            raise ControlPlaneStoreError("unavailable") from error

    def _connect(self, *, create=False):
        try:
            connection = sqlite3.connect(self.database_path, timeout=5, isolation_level=None)
            connection.execute("PRAGMA foreign_keys=ON")
            connection.execute("PRAGMA busy_timeout=5000")
            return connection
        except sqlite3.Error as error:
            raise ControlPlaneStoreError("unavailable") from error

    def _check(self, db):
        try:
            if db.execute("PRAGMA integrity_check").fetchone() != ("ok",):
                raise ValueError
            if db.execute("PRAGMA application_id").fetchone()[0] != 65:
                raise ValueError
            size = db.execute("PRAGMA page_count").fetchone()[0] * db.execute("PRAGMA page_size").fetchone()[0]
            if size > self.max_database_bytes:
                raise ValueError
            for table in ("reservations", "evidence", "failures"):
                if db.execute(f"SELECT count(*) FROM {table}").fetchone()[0] > self.max_total_records:
                    raise ValueError
            for subject, owner, idem, request, payload in db.execute("SELECT subject, owner, idem, request, reservation_json FROM reservations"):
                reservation = self._decode(payload)
                expected_subject = c.evidence_subject_fingerprint({"owner_id": owner, "subject_id": reservation.input.subject_id})
                expected_idem = c.idempotency_fingerprint(owner, reservation.idempotency_key)
                expected_request = c.fingerprint("control-plane-evidence-request", reservation)
                if (expected_subject, expected_idem, expected_request) != (subject, idem, request):
                    raise ValueError
            for subject, owner, payload in db.execute("SELECT subject, owner, record_json FROM evidence"):
                record = self._decode(payload, c.ControlPlaneEvidenceRecordV1)
                if record.subject_fingerprint != subject or record.owner_id != owner:
                    raise ValueError
            for subject, audit in db.execute("SELECT subject, audit FROM failures"):
                if type(subject) is not str or type(audit) is not str or len(audit.encode()) > c.MAX_RECORD_BYTES:
                    raise ValueError
        except Exception as error:
            if isinstance(error, ControlPlaneStoreError):
                raise
            raise ControlPlaneStoreError("store_corrupt") from error

    @staticmethod
    def _decode(payload, model=c.ControlPlaneEvidenceCreateV1):
        if type(payload) is not str or len(payload.encode()) > c.MAX_RECORD_BYTES:
            raise ValueError
        result = model.model_validate_json(payload)
        if result.model_dump_json() != payload:
            raise ValueError
        return result

    def resolve(self, owner: str, idem: str, request: str):
        try:
            with self._connect() as db:
                row = db.execute("SELECT subject, request FROM reservations WHERE owner=? AND idem=?", (owner, idem)).fetchone()
                if row is None:
                    return None
                if row[1] != request:
                    raise ControlPlaneStoreError("idempotency_conflict")
                record = db.execute("SELECT record_json FROM evidence WHERE subject=?", (row[0],)).fetchone()
                if record is None:
                    raise ControlPlaneStoreError("append_indeterminate")
                return self._decode(record[0], c.ControlPlaneEvidenceRecordV1)
        except ControlPlaneStoreError:
            raise
        except sqlite3.Error as error:
            raise ControlPlaneStoreError("unavailable") from error

    def append(self, reservation: c.ControlPlaneEvidenceCreateV1, prepare: Callable[[], c.ControlPlaneEvidenceRecordV1]):
        subject = c.evidence_subject_fingerprint({"owner_id": reservation.owner_id, "subject_id": reservation.input.subject_id})
        idem = c.idempotency_fingerprint(reservation.owner_id, reservation.idempotency_key)
        request = c.fingerprint("control-plane-evidence-request", reservation)
        attempted = False
        try:
            with self._connect() as db:
                db.execute("BEGIN IMMEDIATE")
                row = db.execute("SELECT subject, request FROM reservations WHERE owner=? AND idem=?", (reservation.owner_id, idem)).fetchone()
                if row:
                    db.execute("ROLLBACK")
                    if row[1] != request:
                        raise ControlPlaneStoreError("idempotency_conflict")
                    for _ in range(50):
                        try:
                            return self.resolve(reservation.owner_id, idem, request), False
                        except ControlPlaneStoreError as error:
                            if error.code != "append_indeterminate":
                                raise
                            time.sleep(0.01)
                    raise ControlPlaneStoreError("append_indeterminate")
                if db.execute("SELECT 1 FROM reservations WHERE subject=?", (subject,)).fetchone():
                    db.execute("ROLLBACK")
                    raise ControlPlaneStoreError("permanent_subject_reserved")
                if (db.execute("SELECT count(*) FROM reservations").fetchone()[0] >= self.max_total_records
                        or db.execute("SELECT count(*) FROM reservations WHERE owner=?", (reservation.owner_id,)).fetchone()[0] >= self.max_records_per_owner):
                    db.execute("ROLLBACK")
                    raise ControlPlaneStoreError("quota_exceeded")
                reservation_json = reservation.model_dump_json()
                if len(reservation_json.encode()) > c.MAX_RECORD_BYTES:
                    db.execute("ROLLBACK")
                    raise ControlPlaneStoreError("quota_exceeded")
                db.execute("INSERT INTO reservations VALUES (?,?,?,?,?)", (subject, reservation.owner_id, idem, request, reservation_json))
                db.execute("COMMIT")
                attempted = True
            record = c.ControlPlaneEvidenceRecordV1.model_validate(prepare())
            payload = record.model_dump_json()
            if len(payload.encode()) > c.MAX_RECORD_BYTES:
                raise ControlPlaneStoreError("quota_exceeded")
            with self._connect() as db:
                db.execute("BEGIN IMMEDIATE")
                db.execute("INSERT INTO evidence VALUES (?,?,?)", (subject, reservation.owner_id, payload))
                db.execute("COMMIT")
            return record, True
        except sqlite3.IntegrityError:
            try:
                existing = self.resolve(reservation.owner_id, idem, request)
            except ControlPlaneStoreError:
                raise ControlPlaneStoreError("permanent_subject_reserved") from None
            if existing is None:
                raise ControlPlaneStoreError("append_indeterminate") from None
            return existing, False
        except ControlPlaneStoreError:
            if attempted:
                self._failure(subject)
            raise
        except Exception as error:
            if attempted:
                self._failure(subject)
            raise ControlPlaneStoreError("append_indeterminate" if attempted else "unavailable") from error

    def _failure(self, subject):
        try:
            with self._connect() as db:
                db.execute("INSERT OR IGNORE INTO failures VALUES (?,?)", (subject, "indeterminate"))
        except Exception as error:
            LOGGER.debug("unable to journal indeterminate control-plane append", exc_info=error)

    def get(self, owner: str, subject_id: str):
        try:
            with self._connect() as db:
                row = db.execute("SELECT record_json FROM evidence WHERE owner=?", (owner,)).fetchall()
                for payload, in row:
                    record = self._decode(payload, c.ControlPlaneEvidenceRecordV1)
                    if record.subject_id == subject_id:
                        return record
        except ControlPlaneStoreError:
            raise
        except sqlite3.Error as error:
            raise ControlPlaneStoreError("unavailable") from error
        raise ControlPlaneStoreError("evidence_not_found")

    def list(self, owner: str):
        try:
            with self._connect() as db:
                rows = db.execute("SELECT record_json FROM evidence WHERE owner=? ORDER BY rowid LIMIT ?", (owner, self.max_records_per_owner)).fetchall()
                return tuple(self._decode(payload, c.ControlPlaneEvidenceRecordV1) for payload, in rows)
        except ControlPlaneStoreError:
            raise
        except sqlite3.Error as error:
            raise ControlPlaneStoreError("unavailable") from error
