"""Independent bounded append-only store for approval evidence."""

from __future__ import annotations

import hashlib
import json
import sqlite3
import uuid
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Protocol

from pydantic import TypeAdapter, ValidationError

from app.installation_approval_intent.contract import (
    APPROVAL_STATEMENT,
    InstallationApprovalIntentV1,
    InstallationApprovalSubjectV1,
    validate_approval_subject,
)
from app.installation_candidate_admission.contract import fingerprint
from app.installation_candidate_lifecycle.contract import (
    InstallationCandidateRecordEnvelopeV1,
    OwnerId,
)

MAX_RETAINED_INTENTS_PER_OPERATOR = 16
MAX_INTENT_BYTES = 32 * 1024


class CandidateRecordReader(Protocol):
    def get(
        self, *, owner_id: str, candidate_record_id: str
    ) -> InstallationCandidateRecordEnvelopeV1: ...


class ApprovalIntentStoreError(RuntimeError):
    """Sanitized approval-intent store failure."""


class ApprovalIntentNotFoundError(ApprovalIntentStoreError):
    pass


class ApprovalIntentCandidateUnavailableError(ApprovalIntentStoreError):
    pass


class ApprovalIntentIdempotencyConflictError(ApprovalIntentStoreError):
    pass


class ApprovalIntentLimitError(ApprovalIntentStoreError):
    pass


class ApprovalIntentRecordLimitError(ApprovalIntentStoreError):
    pass


def _utc_now() -> datetime:
    return datetime.now(UTC).replace(microsecond=0)


def _instant(clock: Callable[[], datetime]) -> str:
    try:
        value = clock()
    except Exception as error:
        raise ApprovalIntentStoreError("approval intent clock unavailable") from error
    if (
        type(value) is not datetime
        or value.tzinfo is None
        or value.utcoffset() != timedelta(0)
        or value.microsecond != 0
    ):
        raise ApprovalIntentStoreError(
            "approval intent clock must be whole-second UTC"
        )
    return value.strftime("%Y-%m-%dT%H:%M:%SZ")


def _key(value: str) -> str:
    if (
        type(value) is not str
        or not 1 <= len(value.encode("ascii", errors="ignore")) <= 128
        or not value.isascii()
        or any(not 0x21 <= ord(character) <= 0x7E for character in value)
    ):
        raise ValueError("idempotency key must be 1-128 visible ASCII bytes")
    return value


class InstallationApprovalIntentStore:
    """Atomically append and read operator-owned, non-authorizing evidence."""

    def __init__(
        self,
        database_path: str | Path,
        *,
        candidates: CandidateRecordReader,
        clock: Callable[[], datetime] = _utc_now,
        id_factory: Callable[[], uuid.UUID] = uuid.uuid4,
    ) -> None:
        self.database_path = str(database_path)
        self._candidates = candidates
        self._clock = clock
        self._id_factory = id_factory
        if self.database_path != ":memory:":
            Path(self.database_path).parent.mkdir(parents=True, exist_ok=True)
        try:
            with self._connect() as connection:
                connection.execute("""
                    CREATE TABLE IF NOT EXISTS installation_approval_intents (
                        approval_intent_id TEXT PRIMARY KEY,
                        operator_id TEXT NOT NULL,
                        subject_fingerprint TEXT NOT NULL,
                        intent_json TEXT NOT NULL,
                        UNIQUE(operator_id, subject_fingerprint)
                    )
                """)
                connection.execute("""
                    CREATE TABLE IF NOT EXISTS installation_approval_intent_idempotency (
                        operator_id TEXT NOT NULL,
                        key_digest TEXT NOT NULL,
                        subject_fingerprint TEXT NOT NULL,
                        approval_intent_id TEXT NOT NULL,
                        PRIMARY KEY(operator_id, key_digest)
                    )
                """)
        except Exception as error:
            raise ApprovalIntentStoreError(
                "approval intent store initialization failed"
            ) from error
        if self.database_path != ":memory:":
            Path(self.database_path).chmod(0o600)

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(
            self.database_path, timeout=5, check_same_thread=False
        )
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA busy_timeout=5000")
        connection.execute("PRAGMA synchronous=FULL")
        return connection

    @staticmethod
    def _key_digest(key: str) -> str:
        return hashlib.sha256(
            b"atlas:installation-approval-intent-idempotency:v1\0"
            + _key(key).encode()
        ).hexdigest()

    @staticmethod
    def _subject_fingerprint(subject: InstallationApprovalSubjectV1) -> str:
        return fingerprint(
            "atlas:installation-approval-subject:v1",
            subject.model_dump(mode="json"),
        )

    @staticmethod
    def _encode(intent: InstallationApprovalIntentV1) -> str:
        encoded = json.dumps(
            intent.model_dump(mode="json"),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        if len(encoded.encode()) > MAX_INTENT_BYTES:
            raise ApprovalIntentRecordLimitError("approval intent size limit exceeded")
        return encoded

    @staticmethod
    def _decode(row: sqlite3.Row) -> InstallationApprovalIntentV1:
        try:
            raw = row["intent_json"]
            if type(raw) is not str or len(raw.encode()) > MAX_INTENT_BYTES:
                raise ValueError("invalid approval intent storage")
            intent = InstallationApprovalIntentV1.model_validate_json(raw)
            subject_fingerprint = InstallationApprovalIntentStore._subject_fingerprint(
                intent.approved_subject
            )
            if (
                intent.approval_intent_id != row["approval_intent_id"]
                or intent.operator_id != row["operator_id"]
                or subject_fingerprint != row["subject_fingerprint"]
            ):
                raise ValueError("approval intent index mismatch")
            return intent
        except (ValidationError, ValueError, TypeError) as error:
            raise ApprovalIntentStoreError("approval intent unavailable") from error

    def create(
        self,
        *,
        operator_id: str,
        candidate_record_id: str,
        idempotency_key: str,
    ) -> tuple[InstallationApprovalIntentV1, bool]:
        operator = TypeAdapter(OwnerId).validate_python(operator_id, strict=True)
        key_digest = self._key_digest(idempotency_key)
        recorded_at = _instant(self._clock)
        try:
            envelope = self._candidates.get(
                owner_id=operator, candidate_record_id=candidate_record_id
            )
            subject = validate_approval_subject(
                envelope, operator_id=operator, recorded_at=recorded_at
            )
        except (ApprovalIntentStoreError, ValueError):
            raise
        except Exception as error:
            raise ApprovalIntentCandidateUnavailableError(
                "candidate record unavailable"
            ) from error
        subject_fingerprint = self._subject_fingerprint(subject)
        try:
            with self._connect() as connection:
                connection.execute("BEGIN IMMEDIATE")
                prior = connection.execute(
                    "SELECT * FROM installation_approval_intent_idempotency "
                    "WHERE operator_id=? AND key_digest=?",
                    (operator, key_digest),
                ).fetchone()
                if prior is not None:
                    if prior["subject_fingerprint"] != subject_fingerprint:
                        raise ApprovalIntentIdempotencyConflictError(
                            "idempotency conflict"
                        )
                    row = connection.execute(
                        "SELECT * FROM installation_approval_intents "
                        "WHERE approval_intent_id=? AND operator_id=?",
                        (prior["approval_intent_id"], operator),
                    ).fetchone()
                    if row is None:
                        raise ApprovalIntentStoreError("approval intent unavailable")
                    return self._decode(row), False
                existing = connection.execute(
                    "SELECT * FROM installation_approval_intents "
                    "WHERE operator_id=? AND subject_fingerprint=?",
                    (operator, subject_fingerprint),
                ).fetchone()
                if existing is not None:
                    intent = self._decode(existing)
                    connection.execute(
                        "INSERT INTO installation_approval_intent_idempotency "
                        "VALUES (?, ?, ?, ?)",
                        (operator, key_digest, subject_fingerprint, intent.approval_intent_id),
                    )
                    return intent, False
                count = connection.execute(
                    "SELECT COUNT(*) FROM installation_approval_intents WHERE operator_id=?",
                    (operator,),
                ).fetchone()[0]
                if count >= MAX_RETAINED_INTENTS_PER_OPERATOR:
                    raise ApprovalIntentLimitError("approval intent limit reached")
                intent_id = str(self._id_factory())
                public = {
                    "schema": "installation-approval-intent-v1",
                    "approval_intent_id": intent_id,
                    "operator_id": operator,
                    "recorded_at": recorded_at,
                    "approved_subject": subject.model_dump(mode="json"),
                    "statement": APPROVAL_STATEMENT,
                }
                intent = InstallationApprovalIntentV1.model_validate(
                    {
                        **public,
                        "intent_fingerprint": fingerprint(
                            "atlas:installation-approval-intent:v1", public
                        ),
                    }
                )
                encoded = self._encode(intent)
                connection.execute(
                    "INSERT INTO installation_approval_intents VALUES (?, ?, ?, ?)",
                    (intent_id, operator, subject_fingerprint, encoded),
                )
                connection.execute(
                    "INSERT INTO installation_approval_intent_idempotency VALUES (?, ?, ?, ?)",
                    (operator, key_digest, subject_fingerprint, intent_id),
                )
                return intent, True
        except ApprovalIntentStoreError:
            raise
        except Exception as error:
            raise ApprovalIntentStoreError("approval intent creation failed") from error

    def get(
        self, *, operator_id: str, approval_intent_id: str
    ) -> InstallationApprovalIntentV1:
        try:
            with self._connect() as connection:
                row = connection.execute(
                    "SELECT * FROM installation_approval_intents "
                    "WHERE approval_intent_id=? AND operator_id=?",
                    (approval_intent_id, operator_id),
                ).fetchone()
            if row is None:
                raise ApprovalIntentNotFoundError("approval intent not found")
            return self._decode(row)
        except ApprovalIntentStoreError:
            raise
        except Exception as error:
            raise ApprovalIntentStoreError("approval intent unavailable") from error

    def list_for_operator(
        self, operator_id: str
    ) -> tuple[InstallationApprovalIntentV1, ...]:
        try:
            with self._connect() as connection:
                rows = connection.execute(
                    "SELECT * FROM installation_approval_intents WHERE operator_id=? "
                    "ORDER BY approval_intent_id",
                    (operator_id,),
                ).fetchall()
            return tuple(self._decode(row) for row in rows)
        except ApprovalIntentStoreError:
            raise
        except Exception as error:
            raise ApprovalIntentStoreError("approval intents unavailable") from error
