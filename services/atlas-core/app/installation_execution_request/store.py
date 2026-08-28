"""Bounded append-only storage for inert installation execution requests."""

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
from app.installation_execution_request.contract import (
    MAX_RECORD_BYTES,
    InstallationExecutionRequestCreateV1,
    InstallationExecutionRequestV1,
    build_execution_request,
    create_fingerprint,
    execution_request_fingerprint,
    execution_request_state,
)

MAX_RETAINED_REQUESTS_PER_OPERATOR = 16


class CandidateRecordReader(Protocol):
    def get(
        self, *, owner_id: str, candidate_record_id: str
    ) -> InstallationCandidateRecordEnvelopeV1: ...


class ApprovalIntentReader(Protocol):
    def get(
        self, *, operator_id: str, approval_intent_id: str
    ) -> InstallationApprovalIntentV1: ...


class InstallationExecutionRequestStoreError(RuntimeError):
    """A closed, redacted request-store failure."""

    code = "unavailable"

    def __init__(self) -> None:
        super().__init__(self.code)


class ExecutionRequestMalformedError(InstallationExecutionRequestStoreError):
    code = "malformed"


class ExecutionRequestNotFoundError(InstallationExecutionRequestStoreError):
    code = "not_found"


class ExecutionRequestNotCurrentError(InstallationExecutionRequestStoreError):
    code = "not_current"


class ExecutionRequestOwnershipError(InstallationExecutionRequestStoreError):
    code = "ownership_mismatch"


class ExecutionRequestProofMismatchError(InstallationExecutionRequestStoreError):
    code = "proof_mismatch"


class ExecutionRequestEvidenceRejectedError(InstallationExecutionRequestStoreError):
    code = "evidence_rejected"


class ExecutionRequestReplayConflictError(InstallationExecutionRequestStoreError):
    code = "replay_conflict"


class ExecutionRequestQuotaError(InstallationExecutionRequestStoreError):
    code = "quota_exceeded"


class ExecutionRequestRecordLimitError(InstallationExecutionRequestStoreError):
    code = "quota_exceeded"


class ExecutionRequestUnavailableError(InstallationExecutionRequestStoreError):
    pass


def _utc_now() -> datetime:
    return datetime.now(UTC).replace(microsecond=0)


def _instant(clock: Callable[[], datetime]) -> str:
    try:
        value = clock()
    except Exception as error:
        raise ExecutionRequestUnavailableError() from error
    if (
        type(value) is not datetime
        or value.tzinfo is None
        or value.utcoffset() != timedelta(0)
        or value.microsecond != 0
    ):
        raise ExecutionRequestUnavailableError()
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


class InstallationExecutionRequestStore:
    """Atomically reserve and append closed, operator-owned request evidence."""

    def __init__(
        self,
        database_path: str | Path,
        *,
        candidates: CandidateRecordReader,
        approvals: ApprovalIntentReader,
        clock: Callable[[], datetime] = _utc_now,
        id_factory: Callable[[], uuid.UUID] = uuid.uuid4,
    ) -> None:
        self.database_path = str(database_path)
        self._candidates = candidates
        self._approvals = approvals
        self._clock = clock
        self._id_factory = id_factory
        if self.database_path != ":memory:":
            Path(self.database_path).parent.mkdir(parents=True, exist_ok=True)
        try:
            with self._connect() as connection:
                connection.execute("""
                    CREATE TABLE IF NOT EXISTS installation_execution_requests (
                        execution_request_id TEXT PRIMARY KEY,
                        owner_id TEXT NOT NULL,
                        create_fingerprint TEXT NOT NULL,
                        approval_intent_id TEXT NOT NULL,
                        agent_request_id TEXT NOT NULL,
                        agent_request_fingerprint TEXT NOT NULL,
                        agent_validation_fingerprint TEXT NOT NULL,
                        execution_request_fingerprint TEXT NOT NULL,
                        request_json TEXT NOT NULL,
                        UNIQUE(owner_id, approval_intent_id),
                        UNIQUE(owner_id, agent_request_id),
                        UNIQUE(owner_id, agent_request_fingerprint),
                        UNIQUE(owner_id, agent_validation_fingerprint),
                        UNIQUE(owner_id, execution_request_fingerprint)
                    )
                """)
                connection.execute("""
                    CREATE TABLE IF NOT EXISTS installation_execution_request_idempotency (
                        owner_id TEXT NOT NULL,
                        key_digest TEXT NOT NULL,
                        create_fingerprint TEXT NOT NULL,
                        execution_request_id TEXT NOT NULL,
                        PRIMARY KEY(owner_id, key_digest)
                    )
                """)
        except Exception as error:
            raise ExecutionRequestUnavailableError() from error
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
            b"atlas:installation-execution-request-idempotency:v1\0"
            + _key(value).encode()
        ).hexdigest()

    @staticmethod
    def _encode(request: InstallationExecutionRequestV1) -> str:
        encoded = json.dumps(
            request.model_dump(mode="json"),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        if len(encoded.encode()) > MAX_RECORD_BYTES:
            raise ExecutionRequestRecordLimitError()
        return encoded

    @staticmethod
    def _decode(row: sqlite3.Row) -> InstallationExecutionRequestV1:
        try:
            raw = row["request_json"]
            if type(raw) is not str or len(raw.encode()) > MAX_RECORD_BYTES:
                raise ValueError
            request = InstallationExecutionRequestV1.model_validate_json(raw)
            if (
                request.execution_request_id != row["execution_request_id"]
                or request.linkage.approval_intent_id != row["approval_intent_id"]
                or request.linkage.agent_request_id != row["agent_request_id"]
                or request.linkage.agent_request_fingerprint.value
                != row["agent_request_fingerprint"]
                or request.linkage.agent_validation_fingerprint.value
                != row["agent_validation_fingerprint"]
                or request.execution_request_fingerprint.value
                != row["execution_request_fingerprint"]
                or execution_request_fingerprint(
                    owner_id=row["owner_id"], record=request
                )
                != request.execution_request_fingerprint
            ):
                raise ValueError
            return request
        except (ValidationError, ValueError, TypeError, KeyError) as error:
            raise ExecutionRequestUnavailableError() from error

    @staticmethod
    def _map_validation(error: Exception) -> InstallationExecutionRequestStoreError:
        detail = str(error)
        if "ownership" in detail:
            return ExecutionRequestOwnershipError()
        if "current" in detail or "fresh" in detail or "window" in detail:
            return ExecutionRequestNotCurrentError()
        if "rejected" in detail or "status" in detail or "policy" in detail:
            return ExecutionRequestEvidenceRejectedError()
        return ExecutionRequestProofMismatchError()

    def create(
        self,
        *,
        owner_id: str,
        idempotency_key: str,
        create: InstallationExecutionRequestCreateV1,
    ) -> tuple[InstallationExecutionRequestV1, bool]:
        try:
            owner = TypeAdapter(OwnerId).validate_python(owner_id, strict=True)
            exact_create = InstallationExecutionRequestCreateV1.model_validate(
                create.model_dump(mode="python")
            )
            key_digest = self._key_digest(idempotency_key)
            create_digest = create_fingerprint(exact_create).value
        except Exception as error:
            raise ExecutionRequestMalformedError() from error

        # Replay is deliberately resolved before clock or dependency access.
        try:
            with self._connect() as connection:
                connection.execute("BEGIN IMMEDIATE")
                prior = connection.execute(
                    "SELECT * FROM installation_execution_request_idempotency "
                    "WHERE owner_id=? AND key_digest=?",
                    (owner, key_digest),
                ).fetchone()
                if prior is not None:
                    if prior["create_fingerprint"] != create_digest:
                        raise ExecutionRequestReplayConflictError()
                    row = connection.execute(
                        "SELECT * FROM installation_execution_requests "
                        "WHERE owner_id=? AND execution_request_id=?",
                        (owner, prior["execution_request_id"]),
                    ).fetchone()
                    if row is None:
                        raise ExecutionRequestUnavailableError()
                    return self._decode(row), False
        except InstallationExecutionRequestStoreError:
            raise
        except Exception as error:
            raise ExecutionRequestUnavailableError() from error

        recorded_at = _instant(self._clock)
        try:
            envelope = self._candidates.get(
                owner_id=owner, candidate_record_id=exact_create.candidate_record_id
            )
            intent = self._approvals.get(
                operator_id=owner, approval_intent_id=exact_create.approval_intent_id
            )
        except Exception as error:
            # Owned-reader boundaries intentionally make foreign and absent identical.
            raise ExecutionRequestNotFoundError() from error
        try:
            execution_request_id = str(self._id_factory())
        except Exception as error:
            raise ExecutionRequestUnavailableError() from error
        try:
            request = build_execution_request(
                owner_id=owner,
                execution_request_id=execution_request_id,
                recorded_at=recorded_at,
                envelope=envelope,
                approval_intent=intent,
                create=exact_create,
            )
            encoded = self._encode(request)
        except InstallationExecutionRequestStoreError:
            raise
        except Exception as error:
            raise self._map_validation(error) from error

        try:
            with self._connect() as connection:
                connection.execute("BEGIN IMMEDIATE")
                # Close the race with a second replay check under the append lock.
                prior = connection.execute(
                    "SELECT * FROM installation_execution_request_idempotency "
                    "WHERE owner_id=? AND key_digest=?",
                    (owner, key_digest),
                ).fetchone()
                if prior is not None:
                    if prior["create_fingerprint"] != create_digest:
                        raise ExecutionRequestReplayConflictError()
                    row = connection.execute(
                        "SELECT * FROM installation_execution_requests "
                        "WHERE owner_id=? AND execution_request_id=?",
                        (owner, prior["execution_request_id"]),
                    ).fetchone()
                    if row is None:
                        raise ExecutionRequestUnavailableError()
                    return self._decode(row), False
                count = connection.execute(
                    "SELECT COUNT(*) FROM installation_execution_requests "
                    "WHERE owner_id=?",
                    (owner,),
                ).fetchone()[0]
                if count >= MAX_RETAINED_REQUESTS_PER_OPERATOR:
                    raise ExecutionRequestQuotaError()
                linkage = request.linkage
                connection.execute(
                    "INSERT INTO installation_execution_requests VALUES "
                    "(?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        request.execution_request_id,
                        owner,
                        create_digest,
                        linkage.approval_intent_id,
                        linkage.agent_request_id,
                        linkage.agent_request_fingerprint.value,
                        linkage.agent_validation_fingerprint.value,
                        request.execution_request_fingerprint.value,
                        encoded,
                    ),
                )
                connection.execute(
                    "INSERT INTO installation_execution_request_idempotency "
                    "VALUES (?, ?, ?, ?)",
                    (owner, key_digest, create_digest, request.execution_request_id),
                )
                return request, True
        except InstallationExecutionRequestStoreError:
            raise
        except sqlite3.IntegrityError as error:
            raise ExecutionRequestReplayConflictError() from error
        except Exception as error:
            raise ExecutionRequestUnavailableError() from error

    def get(
        self, *, owner_id: str, execution_request_id: str
    ) -> InstallationExecutionRequestV1:
        try:
            with self._connect() as connection:
                row = connection.execute(
                    "SELECT * FROM installation_execution_requests "
                    "WHERE owner_id=? AND execution_request_id=?",
                    (owner_id, execution_request_id),
                ).fetchone()
            if row is None:
                raise ExecutionRequestNotFoundError()
            return self._decode(row)
        except InstallationExecutionRequestStoreError:
            raise
        except Exception as error:
            raise ExecutionRequestUnavailableError() from error

    def list_for_operator(
        self, owner_id: str
    ) -> tuple[InstallationExecutionRequestV1, ...]:
        try:
            with self._connect() as connection:
                rows = connection.execute(
                    "SELECT * FROM installation_execution_requests WHERE owner_id=? "
                    "ORDER BY execution_request_id",
                    (owner_id,),
                ).fetchall()
            return tuple(self._decode(row) for row in rows)
        except InstallationExecutionRequestStoreError:
            raise
        except Exception as error:
            raise ExecutionRequestUnavailableError() from error

    def state(self, *, owner_id: str, execution_request_id: str) -> str:
        return execution_request_state(
            self.get(owner_id=owner_id, execution_request_id=execution_request_id),
            now=_instant(self._clock),
        )
