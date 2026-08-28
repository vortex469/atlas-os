"""Bounded append-only storage for inert installation dispatch handoffs."""

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

from app.installation_approval_intent.contract import InstallationApprovalIntentV1
from app.installation_candidate_lifecycle.contract import (
    InstallationCandidateRecordEnvelopeV1,
    OwnerId,
)
from app.installation_dispatch_handoff.contract import (
    MAX_ENVELOPE_BYTES,
    InstallationDispatchEnvelopeV1,
    InstallationDispatchHandoffCreateV1,
    build_dispatch_envelope,
    create_fingerprint,
    dispatch_envelope_fingerprint,
    dispatch_envelope_state,
)
from app.installation_execution_request.contract import InstallationExecutionRequestV1

MAX_RETAINED_ENVELOPES_PER_OPERATOR = 16


class ExecutionRequestReader(Protocol):
    def get(
        self, *, owner_id: str, execution_request_id: str
    ) -> InstallationExecutionRequestV1: ...


class CandidateRecordReader(Protocol):
    def get(
        self, *, owner_id: str, candidate_record_id: str
    ) -> InstallationCandidateRecordEnvelopeV1: ...


class ApprovalIntentReader(Protocol):
    def get(
        self, *, operator_id: str, approval_intent_id: str
    ) -> InstallationApprovalIntentV1: ...


class InstallationDispatchStoreError(RuntimeError):
    """A closed, redacted handoff-store failure."""

    code = "unavailable"

    def __init__(self) -> None:
        super().__init__(self.code)


class InstallationDispatchMalformedError(InstallationDispatchStoreError):
    code = "malformed"


class InstallationDispatchNotFoundError(InstallationDispatchStoreError):
    code = "not_found"


class InstallationDispatchNotCurrentError(InstallationDispatchStoreError):
    code = "not_current"


class InstallationDispatchOwnershipError(InstallationDispatchStoreError):
    code = "ownership_mismatch"


class InstallationDispatchProofMismatchError(InstallationDispatchStoreError):
    code = "proof_mismatch"


class InstallationDispatchEvidenceUnavailableError(InstallationDispatchStoreError):
    code = "evidence_unavailable"


class InstallationDispatchReplayConflictError(InstallationDispatchStoreError):
    code = "replay_conflict"


class InstallationDispatchQuotaError(InstallationDispatchStoreError):
    code = "quota_exceeded"


class InstallationDispatchRecordLimitError(InstallationDispatchQuotaError):
    pass


class InstallationDispatchUnavailableError(InstallationDispatchStoreError):
    pass


def _utc_now() -> datetime:
    return datetime.now(UTC).replace(microsecond=0)


def _clock_instant(clock: Callable[[], datetime]) -> str:
    try:
        value = clock()
    except Exception as error:
        raise InstallationDispatchUnavailableError() from error
    if (
        type(value) is not datetime
        or value.tzinfo is None
        or value.utcoffset() != timedelta(0)
        or value.microsecond != 0
    ):
        raise InstallationDispatchUnavailableError()
    return value.strftime("%Y-%m-%dT%H:%M:%SZ")


def _key(value: str) -> str:
    if (
        type(value) is not str
        or not value.isascii()
        or not 1 <= len(value.encode()) <= 128
        or any(not 0x21 <= ord(character) <= 0x7E for character in value)
    ):
        raise ValueError("malformed")
    return value


class InstallationDispatchHandoffStore:
    """Atomically reserve and append operator-owned preparation evidence."""

    def __init__(
        self,
        database_path: str | Path,
        *,
        execution_requests: ExecutionRequestReader,
        candidates: CandidateRecordReader,
        approvals: ApprovalIntentReader,
        clock: Callable[[], datetime] = _utc_now,
        id_factory: Callable[[], uuid.UUID] = uuid.uuid4,
    ) -> None:
        self.database_path = str(database_path)
        self._execution_requests = execution_requests
        self._candidates = candidates
        self._approvals = approvals
        self._clock = clock
        self._id_factory = id_factory
        if self.database_path != ":memory:":
            Path(self.database_path).parent.mkdir(parents=True, exist_ok=True)
        try:
            with self._connect() as connection:
                connection.execute("""
                    CREATE TABLE IF NOT EXISTS installation_dispatch_handoffs (
                        dispatch_envelope_id TEXT PRIMARY KEY,
                        owner_id TEXT NOT NULL,
                        create_fingerprint TEXT NOT NULL,
                        execution_request_id TEXT NOT NULL,
                        dispatch_envelope_fingerprint TEXT NOT NULL,
                        envelope_json TEXT NOT NULL,
                        UNIQUE(owner_id, execution_request_id),
                        UNIQUE(owner_id, dispatch_envelope_fingerprint)
                    )
                """)
                connection.execute("""
                    CREATE TABLE IF NOT EXISTS installation_dispatch_idempotency (
                        owner_id TEXT NOT NULL,
                        key_digest TEXT NOT NULL,
                        create_fingerprint TEXT NOT NULL,
                        execution_request_id TEXT NOT NULL,
                        dispatch_envelope_id TEXT NOT NULL,
                        PRIMARY KEY(owner_id, key_digest)
                    )
                """)
        except Exception as error:
            raise InstallationDispatchUnavailableError() from error
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
    def _key_digest(value: str) -> str:
        return hashlib.sha256(
            b"atlas:installation-dispatch-idempotency:v1\0" + _key(value).encode()
        ).hexdigest()

    @staticmethod
    def _encode(envelope: InstallationDispatchEnvelopeV1) -> str:
        encoded = json.dumps(
            envelope.model_dump(mode="json"),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        if len(encoded.encode()) > MAX_ENVELOPE_BYTES:
            raise InstallationDispatchRecordLimitError()
        return encoded

    @staticmethod
    def _decode(row: sqlite3.Row) -> InstallationDispatchEnvelopeV1:
        try:
            raw = row["envelope_json"]
            if type(raw) is not str or len(raw.encode()) > MAX_ENVELOPE_BYTES:
                raise ValueError
            envelope = InstallationDispatchEnvelopeV1.model_validate_json(raw)
            stored_create = InstallationDispatchHandoffCreateV1(
                execution_request_id=envelope.linkage.execution_request_id
            )
            if (
                envelope.dispatch_envelope_id != row["dispatch_envelope_id"]
                or envelope.linkage.execution_request_id
                != row["execution_request_id"]
                or create_fingerprint(stored_create).value
                != row["create_fingerprint"]
                or envelope.dispatch_envelope_fingerprint.value
                != row["dispatch_envelope_fingerprint"]
                or dispatch_envelope_fingerprint(
                    owner_id=row["owner_id"], envelope=envelope
                )
                != envelope.dispatch_envelope_fingerprint
            ):
                raise ValueError
            return envelope
        except (ValidationError, ValueError, TypeError, KeyError) as error:
            raise InstallationDispatchUnavailableError() from error

    @staticmethod
    def _map_validation(error: Exception) -> InstallationDispatchStoreError:
        detail = str(error)
        if "ownership" in detail:
            return InstallationDispatchOwnershipError()
        if "current" in detail or "window" in detail or "future" in detail:
            return InstallationDispatchNotCurrentError()
        if "evidence" in detail or "status" in detail:
            return InstallationDispatchEvidenceUnavailableError()
        return InstallationDispatchProofMismatchError()

    def create(
        self,
        *,
        owner_id: str,
        idempotency_key: str,
        create: InstallationDispatchHandoffCreateV1,
    ) -> tuple[InstallationDispatchEnvelopeV1, bool]:
        try:
            owner = TypeAdapter(OwnerId).validate_python(owner_id, strict=True)
            exact_create = InstallationDispatchHandoffCreateV1.model_validate(
                create.model_dump(mode="python")
            )
            key_digest = self._key_digest(idempotency_key)
            create_digest = create_fingerprint(exact_create).value
        except Exception as error:
            raise InstallationDispatchMalformedError() from error

        prior = self._read_replay(owner, key_digest, create_digest)
        if prior is not None:
            return prior, False

        prepared_at = _clock_instant(self._clock)
        try:
            request = self._execution_requests.get(
                owner_id=owner,
                execution_request_id=exact_create.execution_request_id,
            )
            candidate = self._candidates.get(
                owner_id=owner,
                candidate_record_id=request.linkage.candidate_record_id,
            )
            intent = self._approvals.get(
                operator_id=owner,
                approval_intent_id=request.linkage.approval_intent_id,
            )
        except Exception as error:
            raise InstallationDispatchNotFoundError() from error
        try:
            dispatch_envelope_id = str(self._id_factory())
        except Exception as error:
            raise InstallationDispatchUnavailableError() from error
        try:
            envelope = build_dispatch_envelope(
                owner_id=owner,
                dispatch_envelope_id=dispatch_envelope_id,
                prepared_at=prepared_at,
                create=exact_create,
                candidate_envelope=candidate,
                approval_intent=intent,
                execution_request=request,
            )
            encoded = self._encode(envelope)
        except InstallationDispatchStoreError:
            raise
        except Exception as error:
            raise self._map_validation(error) from error

        try:
            with self._connect() as connection:
                connection.execute("BEGIN IMMEDIATE")
                prior = self._replay_in_transaction(
                    connection, owner, key_digest, create_digest
                )
                if prior is not None:
                    return prior, False
                count = connection.execute(
                    "SELECT COUNT(*) FROM installation_dispatch_handoffs "
                    "WHERE owner_id=?",
                    (owner,),
                ).fetchone()[0]
                if count >= MAX_RETAINED_ENVELOPES_PER_OPERATOR:
                    raise InstallationDispatchQuotaError()
                connection.execute(
                    "INSERT INTO installation_dispatch_handoffs VALUES "
                    "(?, ?, ?, ?, ?, ?)",
                    (
                        envelope.dispatch_envelope_id,
                        owner,
                        create_digest,
                        exact_create.execution_request_id,
                        envelope.dispatch_envelope_fingerprint.value,
                        encoded,
                    ),
                )
                connection.execute(
                    "INSERT INTO installation_dispatch_idempotency VALUES "
                    "(?, ?, ?, ?, ?)",
                    (
                        owner,
                        key_digest,
                        create_digest,
                        exact_create.execution_request_id,
                        envelope.dispatch_envelope_id,
                    ),
                )
                return envelope, True
        except InstallationDispatchStoreError:
            raise
        except sqlite3.IntegrityError as error:
            raise InstallationDispatchReplayConflictError() from error
        except Exception as error:
            raise InstallationDispatchUnavailableError() from error

    def _read_replay(
        self, owner: str, key_digest: str, create_digest: str
    ) -> InstallationDispatchEnvelopeV1 | None:
        try:
            with self._connect() as connection:
                return self._replay_in_transaction(
                    connection, owner, key_digest, create_digest
                )
        except InstallationDispatchStoreError:
            raise
        except Exception as error:
            raise InstallationDispatchUnavailableError() from error

    def _replay_in_transaction(
        self,
        connection: sqlite3.Connection,
        owner: str,
        key_digest: str,
        create_digest: str,
    ) -> InstallationDispatchEnvelopeV1 | None:
        prior = connection.execute(
            "SELECT * FROM installation_dispatch_idempotency "
            "WHERE owner_id=? AND key_digest=?",
            (owner, key_digest),
        ).fetchone()
        if prior is None:
            return None
        if prior["create_fingerprint"] != create_digest:
            raise InstallationDispatchReplayConflictError()
        row = connection.execute(
            "SELECT * FROM installation_dispatch_handoffs "
            "WHERE owner_id=? AND dispatch_envelope_id=?",
            (owner, prior["dispatch_envelope_id"]),
        ).fetchone()
        if (
            row is None
            or row["execution_request_id"] != prior["execution_request_id"]
            or row["create_fingerprint"] != prior["create_fingerprint"]
        ):
            raise InstallationDispatchUnavailableError()
        return self._decode(row)

    def get(
        self, *, owner_id: str, dispatch_envelope_id: str
    ) -> InstallationDispatchEnvelopeV1:
        try:
            with self._connect() as connection:
                row = connection.execute(
                    "SELECT * FROM installation_dispatch_handoffs "
                    "WHERE owner_id=? AND dispatch_envelope_id=?",
                    (owner_id, dispatch_envelope_id),
                ).fetchone()
            if row is None:
                raise InstallationDispatchNotFoundError()
            return self._decode(row)
        except InstallationDispatchStoreError:
            raise
        except Exception as error:
            raise InstallationDispatchUnavailableError() from error

    def list_for_operator(
        self, owner_id: str
    ) -> tuple[InstallationDispatchEnvelopeV1, ...]:
        try:
            with self._connect() as connection:
                rows = connection.execute(
                    "SELECT * FROM installation_dispatch_handoffs WHERE owner_id=? "
                    "ORDER BY dispatch_envelope_id",
                    (owner_id,),
                ).fetchall()
            return tuple(self._decode(row) for row in rows)
        except InstallationDispatchStoreError:
            raise
        except Exception as error:
            raise InstallationDispatchUnavailableError() from error

    def state(self, *, owner_id: str, dispatch_envelope_id: str) -> str:
        envelope = self.get(
            owner_id=owner_id, dispatch_envelope_id=dispatch_envelope_id
        )
        try:
            return dispatch_envelope_state(
                envelope,
                now=_clock_instant(self._clock),
            )
        except InstallationDispatchStoreError:
            raise
        except Exception as error:
            raise InstallationDispatchUnavailableError() from error
