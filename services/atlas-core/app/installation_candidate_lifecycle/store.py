"""Independent bounded SQLite store for inert candidate record envelopes."""

from __future__ import annotations

import hashlib
import json
import sqlite3
import uuid
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path

from pydantic import TypeAdapter, ValidationError

from app.installation_candidate_admission.contract import (
    InstallationCandidateAdmissionV1,
    fingerprint,
)
from app.installation_candidate_lifecycle.contract import (
    InstallationCandidateRecordEnvelopeV1,
    OwnerId,
    candidate_record_state,
    validate_preservable_admission,
)

MAX_RETAINED_RECORDS_PER_OPERATOR = 16
MAX_ENVELOPE_BYTES = 64 * 1024


class CandidateRecordStoreError(RuntimeError):
    """Sanitized store failure."""


class CandidateRecordNotFoundError(CandidateRecordStoreError):
    pass


class CandidateRecordIdempotencyConflictError(CandidateRecordStoreError):
    pass


class CandidateRecordIdempotencyDeletedError(CandidateRecordStoreError):
    pass


class CandidateRecordLimitError(CandidateRecordStoreError):
    pass


class CandidateRecordEnvelopeLimitError(CandidateRecordStoreError):
    pass


def _utc_now() -> datetime:
    return datetime.now(UTC).replace(microsecond=0)


def _instant(clock: Callable[[], datetime]) -> str:
    try:
        value = clock()
    except Exception as error:
        raise CandidateRecordStoreError("candidate record clock unavailable") from error
    if (
        type(value) is not datetime
        or value.tzinfo is None
        or value.utcoffset() != timedelta(0)
        or value.microsecond != 0
    ):
        raise CandidateRecordStoreError("candidate record clock must be whole-second UTC")
    return value.strftime("%Y-%m-%dT%H:%M:%SZ")


def _key(key: str) -> str:
    if (
        type(key) is not str
        or not 1 <= len(key.encode("ascii", errors="ignore")) <= 128
        or not key.isascii()
        or any(not 0x21 <= ord(character) <= 0x7E for character in key)
    ):
        raise ValueError("idempotency key must be 1-128 visible ASCII bytes")
    return key


class InstallationCandidateRecordStore:
    """Atomically preserves, reads, and deletes operator-owned snapshots."""

    def __init__(
        self,
        database_path: str | Path,
        *,
        clock: Callable[[], datetime] = _utc_now,
        id_factory: Callable[[], uuid.UUID] = uuid.uuid4,
    ) -> None:
        self.database_path = str(database_path)
        self._clock = clock
        self._id_factory = id_factory
        if self.database_path != ":memory:":
            Path(self.database_path).parent.mkdir(parents=True, exist_ok=True)
        try:
            with self._connect() as connection:
                connection.execute("""
                    CREATE TABLE IF NOT EXISTS installation_candidate_records (
                        candidate_record_id TEXT PRIMARY KEY,
                        owner_id TEXT NOT NULL,
                        admission_fingerprint TEXT NOT NULL,
                        envelope_json TEXT NOT NULL
                    )
                """)
                connection.execute("""
                    CREATE TABLE IF NOT EXISTS installation_candidate_record_idempotency (
                        owner_id TEXT NOT NULL,
                        key_digest TEXT NOT NULL,
                        admission_fingerprint TEXT NOT NULL,
                        candidate_record_id TEXT,
                        PRIMARY KEY(owner_id, key_digest)
                    )
                """)
        except Exception as error:
            raise CandidateRecordStoreError("candidate record store initialization failed") from error
        if self.database_path != ":memory:":
            Path(self.database_path).chmod(0o600)

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path, timeout=5, check_same_thread=False)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA busy_timeout=5000")
        connection.execute("PRAGMA synchronous=FULL")
        return connection

    @staticmethod
    def _key_digest(key: str) -> str:
        return hashlib.sha256(
            b"atlas:installation-candidate-record-idempotency:v1\0" + _key(key).encode()
        ).hexdigest()

    @staticmethod
    def _encode(envelope: InstallationCandidateRecordEnvelopeV1) -> str:
        encoded = json.dumps(
            envelope.model_dump(mode="json"),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        if len(encoded.encode()) > MAX_ENVELOPE_BYTES:
            raise CandidateRecordEnvelopeLimitError("candidate record envelope limit exceeded")
        return encoded

    @staticmethod
    def _decode(row: sqlite3.Row) -> InstallationCandidateRecordEnvelopeV1:
        try:
            raw = row["envelope_json"]
            if type(raw) is not str or len(raw.encode()) > MAX_ENVELOPE_BYTES:
                raise ValueError("invalid envelope storage")
            envelope = InstallationCandidateRecordEnvelopeV1.model_validate_json(raw)
            if (
                envelope.candidate_record_id != row["candidate_record_id"]
                or envelope.owner_id != row["owner_id"]
                or envelope.admission_fingerprint != row["admission_fingerprint"]
            ):
                raise ValueError("envelope index mismatch")
            return envelope
        except (ValidationError, ValueError, TypeError) as error:
            raise CandidateRecordStoreError("candidate record unavailable") from error

    def preserve(
        self,
        *,
        owner_id: str,
        idempotency_key: str,
        admission: InstallationCandidateAdmissionV1,
    ) -> tuple[InstallationCandidateRecordEnvelopeV1, bool]:
        owner_id = TypeAdapter(OwnerId).validate_python(owner_id, strict=True)
        key_digest = self._key_digest(idempotency_key)
        created_at = _instant(self._clock)
        exact_admission = InstallationCandidateAdmissionV1.model_validate(
            admission.model_dump()
        )
        try:
            with self._connect() as connection:
                connection.execute("BEGIN IMMEDIATE")
                prior = connection.execute(
                    "SELECT * FROM installation_candidate_record_idempotency WHERE owner_id=? AND key_digest=?",
                    (owner_id, key_digest),
                ).fetchone()
                if prior is not None:
                    if prior["admission_fingerprint"] != exact_admission.admission_fingerprint:
                        raise CandidateRecordIdempotencyConflictError("idempotency conflict")
                    if prior["candidate_record_id"] is None:
                        raise CandidateRecordIdempotencyDeletedError("candidate record was deleted")
                    row = connection.execute(
                        "SELECT * FROM installation_candidate_records WHERE candidate_record_id=? AND owner_id=?",
                        (prior["candidate_record_id"], owner_id),
                    ).fetchone()
                    if row is None:
                        raise CandidateRecordStoreError("candidate record unavailable")
                    return self._decode(row), False
                record = validate_preservable_admission(
                    exact_admission, created_at=created_at
                )
                count = connection.execute(
                    "SELECT COUNT(*) FROM installation_candidate_records WHERE owner_id=?",
                    (owner_id,),
                ).fetchone()[0]
                if count >= MAX_RETAINED_RECORDS_PER_OPERATOR:
                    raise CandidateRecordLimitError("candidate record limit reached")
                candidate_id = str(self._id_factory())
                public = {
                    "schema": "installation-candidate-record-envelope-v1",
                    "candidate_record_id": candidate_id,
                    "owner_id": owner_id,
                    "created_at": created_at,
                    "admission_fingerprint": exact_admission.admission_fingerprint,
                    "candidate_record": record.model_dump(mode="json"),
                }
                envelope = InstallationCandidateRecordEnvelopeV1.model_validate({
                    **public,
                    "envelope_fingerprint": fingerprint(
                        "atlas:installation-candidate-record-envelope:v1", public
                    ),
                })
                encoded = self._encode(envelope)
                connection.execute(
                    "INSERT INTO installation_candidate_records VALUES (?, ?, ?, ?)",
                    (candidate_id, owner_id, exact_admission.admission_fingerprint, encoded),
                )
                connection.execute(
                    "INSERT INTO installation_candidate_record_idempotency VALUES (?, ?, ?, ?)",
                    (owner_id, key_digest, exact_admission.admission_fingerprint, candidate_id),
                )
                return envelope, True
        except (CandidateRecordStoreError, ValueError):
            raise
        except Exception as error:
            raise CandidateRecordStoreError("candidate record preservation failed") from error

    def get(self, *, owner_id: str, candidate_record_id: str) -> InstallationCandidateRecordEnvelopeV1:
        try:
            with self._connect() as connection:
                row = connection.execute(
                    "SELECT * FROM installation_candidate_records WHERE candidate_record_id=? AND owner_id=?",
                    (candidate_record_id, owner_id),
                ).fetchone()
            if row is None:
                raise CandidateRecordNotFoundError("candidate record not found")
            return self._decode(row)
        except CandidateRecordStoreError:
            raise
        except Exception as error:
            raise CandidateRecordStoreError("candidate record unavailable") from error

    def list_for_operator(self, owner_id: str) -> tuple[InstallationCandidateRecordEnvelopeV1, ...]:
        try:
            with self._connect() as connection:
                rows = connection.execute(
                    "SELECT * FROM installation_candidate_records WHERE owner_id=? ORDER BY candidate_record_id",
                    (owner_id,),
                ).fetchall()
            return tuple(self._decode(row) for row in rows)
        except CandidateRecordStoreError:
            raise
        except Exception as error:
            raise CandidateRecordStoreError("candidate records unavailable") from error

    def state(self, *, owner_id: str, candidate_record_id: str) -> str:
        return candidate_record_state(
            self.get(owner_id=owner_id, candidate_record_id=candidate_record_id),
            now=_instant(self._clock),
        )

    def delete(self, *, owner_id: str, candidate_record_id: str) -> None:
        try:
            with self._connect() as connection:
                connection.execute("BEGIN IMMEDIATE")
                cursor = connection.execute(
                    "DELETE FROM installation_candidate_records WHERE candidate_record_id=? AND owner_id=?",
                    (candidate_record_id, owner_id),
                )
                if cursor.rowcount != 1:
                    raise CandidateRecordNotFoundError("candidate record not found")
                connection.execute(
                    "UPDATE installation_candidate_record_idempotency SET candidate_record_id=NULL WHERE owner_id=? AND candidate_record_id=?",
                    (owner_id, candidate_record_id),
                )
        except CandidateRecordStoreError:
            raise
        except Exception as error:
            raise CandidateRecordStoreError("candidate record deletion failed") from error
