"""Durable SQLite ledger for operational dispatch claims and recovery."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from threading import Lock
from uuid import uuid4

from app.operational_dispatch.models import (
    OperationalDispatchAuditEvent,
    OperationalDispatchAuditStatus,
    OperationalDispatchRequest,
    OperationalDispatchResult,
    OperationalVerificationResult,
)


class OperationalLedgerState(StrEnum):
    CLAIMED = "claimed"
    REVALIDATED = "revalidated"
    DISPATCHING = "dispatching"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    OUTCOME_UNKNOWN = "outcome_unknown"
    VERIFYING = "verifying"
    VERIFIED = "verified"
    VERIFICATION_FAILED = "verification_failed"
    TARGET_REPLACED = "target_replaced"


DISPATCH_RESULT_STATES = frozenset(
    {
        OperationalLedgerState.SUCCEEDED,
        OperationalLedgerState.FAILED,
        OperationalLedgerState.OUTCOME_UNKNOWN,
        OperationalLedgerState.TARGET_REPLACED,
    }
)
FINAL_STATES = frozenset(
    {
        OperationalLedgerState.VERIFIED,
        OperationalLedgerState.VERIFICATION_FAILED,
        OperationalLedgerState.TARGET_REPLACED,
    }
)


class OperationalLedgerError(RuntimeError):
    """Base durable operational ledger error."""


class OperationalLedgerConflictError(OperationalLedgerError):
    """A request ID was reused with a different digest."""


class OperationalLedgerCorruptionError(OperationalLedgerError):
    """Stored operational data cannot be decoded safely."""


@dataclass(frozen=True, slots=True)
class OperationalLedgerEntry:
    request_id: str
    request_digest: str
    state: OperationalLedgerState
    request: OperationalDispatchRequest
    created_at: datetime
    updated_at: datetime
    dispatch_started_at: datetime | None = None
    dispatch_result: OperationalDispatchResult | None = None
    verification_result: OperationalVerificationResult | None = None


@dataclass(frozen=True, slots=True)
class OperationalLedgerTransition:
    sequence: int
    request_id: str
    request_digest: str
    previous_state: OperationalLedgerState | None
    state: OperationalLedgerState
    occurred_at: datetime


class OperationalDispatchLedger:
    """Single-owner operational ledger with an explicit dispatch barrier."""

    def __init__(self, database_path: str | Path) -> None:
        self.database_path = str(database_path)
        if self.database_path != ":memory:":
            Path(self.database_path).parent.mkdir(parents=True, exist_ok=True)
        self._lock = Lock()
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(
            self.database_path,
            timeout=5.0,
            isolation_level=None,
            check_same_thread=False,
        )
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA busy_timeout=5000")
        connection.execute("PRAGMA foreign_keys=ON")
        if self.database_path != ":memory:":
            connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA synchronous=FULL")
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS operational_dispatch (
                    request_id TEXT PRIMARY KEY,
                    request_digest TEXT NOT NULL,
                    state TEXT NOT NULL,
                    request_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    dispatch_started_at TEXT,
                    dispatch_result_json TEXT,
                    verification_result_json TEXT
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS operational_dispatch_events (
                    event_id TEXT PRIMARY KEY,
                    status TEXT NOT NULL,
                    occurred_at TEXT NOT NULL,
                    event_json TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """CREATE INDEX IF NOT EXISTS idx_operational_dispatch_events_time
                   ON operational_dispatch_events (occurred_at DESC)"""
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS operational_dispatch_transitions (
                    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                    request_id TEXT NOT NULL,
                    request_digest TEXT NOT NULL,
                    previous_state TEXT,
                    state TEXT NOT NULL,
                    occurred_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """CREATE INDEX IF NOT EXISTS idx_operational_dispatch_transitions_request
                   ON operational_dispatch_transitions (request_id, sequence)"""
            )

    @staticmethod
    def _now() -> datetime:
        return datetime.now(UTC)

    def claim(self, request: OperationalDispatchRequest) -> OperationalLedgerEntry:
        request = OperationalDispatchRequest.model_validate(request.model_dump())
        now = self._now().isoformat()
        encoded = request.model_dump_json()
        with self._lock, self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT * FROM operational_dispatch WHERE request_id=?",
                (request.request_id,),
            ).fetchone()
            if row is None:
                connection.execute(
                    """
                    INSERT INTO operational_dispatch
                    (request_id, request_digest, state, request_json, created_at, updated_at)
                    VALUES (?, ?, 'claimed', ?, ?, ?)
                    """,
                    (request.request_id, request.request_digest, encoded, now, now),
                )
                self._record_transition(
                    connection,
                    request,
                    previous_state=None,
                    state=OperationalLedgerState.CLAIMED,
                    occurred_at=now,
                )
                row = self._row_for(connection, request.request_id)
            elif row["request_digest"] != request.request_digest:
                connection.rollback()
                raise OperationalLedgerConflictError(
                    "operational request ID has a different digest"
                )
            connection.commit()
            return self._entry(row)

    def mark_revalidated(self, request: OperationalDispatchRequest) -> OperationalLedgerEntry:
        return self._transition(
            request,
            expected=OperationalLedgerState.CLAIMED,
            target=OperationalLedgerState.REVALIDATED,
        )[0]

    def mark_dispatching(
        self, request: OperationalDispatchRequest
    ) -> tuple[OperationalLedgerEntry, bool]:
        """Cross the at-most-once dispatch barrier for one claimant."""

        return self._transition(
            request,
            expected=OperationalLedgerState.REVALIDATED,
            target=OperationalLedgerState.DISPATCHING,
            set_dispatch_started=True,
        )

    def persist_dispatch_result(
        self,
        request: OperationalDispatchRequest,
        result: OperationalDispatchResult,
        *,
        state: OperationalLedgerState,
    ) -> OperationalLedgerEntry:
        if state not in DISPATCH_RESULT_STATES:
            raise ValueError("invalid dispatch result ledger state")
        if result.request_id != request.request_id or result.request_digest != request.request_digest:
            raise ValueError("dispatch result does not match request")
        encoded = result.model_dump_json()
        now = self._now().isoformat()
        with self._lock, self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = self._row_for(connection, request.request_id)
            self._check_digest(row, request)
            if row["dispatch_result_json"] is not None:
                existing = self._entry(row)
                if existing.dispatch_result != result:
                    connection.rollback()
                    raise OperationalLedgerError("dispatch result is immutable")
                connection.commit()
                return existing
            if OperationalLedgerState(row["state"]) not in {
                OperationalLedgerState.CLAIMED,
                OperationalLedgerState.REVALIDATED,
                OperationalLedgerState.DISPATCHING,
            }:
                connection.rollback()
                raise OperationalLedgerError("dispatch result cannot be persisted from state")
            previous_state = OperationalLedgerState(row["state"])
            connection.execute(
                """UPDATE operational_dispatch
                   SET state=?, dispatch_result_json=?, updated_at=?
                   WHERE request_id=?""",
                (state.value, encoded, now, request.request_id),
            )
            self._record_transition(
                connection,
                request,
                previous_state=previous_state,
                state=state,
                occurred_at=now,
            )
            row = self._row_for(connection, request.request_id)
            connection.commit()
            return self._entry(row)

    def begin_verification(
        self,
        request: OperationalDispatchRequest,
        *,
        resume_interrupted: bool = False,
    ) -> tuple[OperationalLedgerEntry, bool]:
        with self._lock, self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = self._row_for(connection, request.request_id)
            self._check_digest(row, request)
            state = OperationalLedgerState(row["state"])
            owner = False
            if row["verification_result_json"] is not None:
                connection.commit()
                return self._entry(row), False
            if state in {
                OperationalLedgerState.SUCCEEDED,
                OperationalLedgerState.OUTCOME_UNKNOWN,
            }:
                now = self._now().isoformat()
                connection.execute(
                    "UPDATE operational_dispatch SET state='verifying', updated_at=? WHERE request_id=?",
                    (now, request.request_id),
                )
                self._record_transition(
                    connection,
                    request,
                    previous_state=state,
                    state=OperationalLedgerState.VERIFYING,
                    occurred_at=now,
                )
                owner = True
                row = self._row_for(connection, request.request_id)
            elif state is OperationalLedgerState.VERIFYING and resume_interrupted:
                owner = True
            connection.commit()
            return self._entry(row), owner

    def persist_verification_result(
        self,
        request: OperationalDispatchRequest,
        result: OperationalVerificationResult,
    ) -> OperationalLedgerEntry:
        if result.request_id != request.request_id:
            raise ValueError("verification result does not match request")
        state = {
            "succeeded": OperationalLedgerState.VERIFIED,
            "verification_failed": OperationalLedgerState.VERIFICATION_FAILED,
            "outcome_unknown": OperationalLedgerState.OUTCOME_UNKNOWN,
            "target_replaced": OperationalLedgerState.TARGET_REPLACED,
        }[result.status.value]
        encoded = result.model_dump_json()
        with self._lock, self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = self._row_for(connection, request.request_id)
            self._check_digest(row, request)
            if row["verification_result_json"] is not None:
                existing = self._entry(row)
                if existing.verification_result != result:
                    connection.rollback()
                    raise OperationalLedgerError("verification result is immutable")
                connection.commit()
                return existing
            if OperationalLedgerState(row["state"]) is not OperationalLedgerState.VERIFYING:
                connection.rollback()
                raise OperationalLedgerError("verification result requires verifying state")
            now = self._now().isoformat()
            connection.execute(
                """UPDATE operational_dispatch
                   SET state=?, verification_result_json=?, updated_at=?
                   WHERE request_id=?""",
                (state.value, encoded, now, request.request_id),
            )
            self._record_transition(
                connection,
                request,
                previous_state=OperationalLedgerState.VERIFYING,
                state=state,
                occurred_at=now,
            )
            row = self._row_for(connection, request.request_id)
            connection.commit()
            return self._entry(row)

    def reconcile_startup(self) -> dict[str, int]:
        """Classify ambiguous dispatch without replaying mutation."""

        now = self._now()
        with self._lock, self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            rows = connection.execute(
                "SELECT * FROM operational_dispatch WHERE state='dispatching'"
            ).fetchall()
            for row in rows:
                request = OperationalDispatchRequest.model_validate_json(
                    row["request_json"]
                )
                result = OperationalDispatchResult(
                    status="outcome_unknown",
                    request_id=row["request_id"],
                    request_digest=row["request_digest"],
                    target_fingerprint=request.target_fingerprint,
                    started_at=datetime.fromisoformat(row["dispatch_started_at"]),
                    completed_at=now,
                    sanitized_message="Dispatch outcome is unknown after Core restart.",
                )
                connection.execute(
                    """UPDATE operational_dispatch
                       SET state='outcome_unknown', dispatch_result_json=?, updated_at=?
                       WHERE request_id=? AND state='dispatching'""",
                    (result.model_dump_json(), now.isoformat(), row["request_id"]),
                )
                self._record_transition(
                    connection,
                    request,
                    previous_state=OperationalLedgerState.DISPATCHING,
                    state=OperationalLedgerState.OUTCOME_UNKNOWN,
                    occurred_at=now.isoformat(),
                )
            claimed = connection.execute(
                "SELECT COUNT(*) FROM operational_dispatch WHERE state IN ('claimed','revalidated')"
            ).fetchone()[0]
            verifying = connection.execute(
                "SELECT COUNT(*) FROM operational_dispatch WHERE state='verifying'"
            ).fetchone()[0]
            connection.commit()
        for row in rows:
            request = OperationalDispatchRequest.model_validate_json(row["request_json"])
            for status in (
                OperationalDispatchAuditStatus.OUTCOME_UNKNOWN,
                OperationalDispatchAuditStatus.RECOVERY_RECONCILED,
            ):
                self.append_event(
                    OperationalDispatchAuditEvent(
                        event_id=uuid4().hex,
                        status=status,
                        occurred_at=now,
                        request_id=request.request_id,
                        request_digest=request.request_digest,
                        workflow_session_id=request.workflow_session_id,
                        candidate_planning_session_id=(
                            request.candidate_planning_session_id
                        ),
                        candidate_id=request.candidate_id,
                        candidate_plan_id=request.candidate_plan_id,
                        provider_id=request.provider_id,
                        resource_id=request.resource_id,
                        resource_type=request.resource_type,
                        target_fingerprint=request.target_fingerprint,
                    )
                )
        return {
            "retryable_pre_dispatch": int(claimed),
            "outcome_unknown": len(rows),
            "verification_resumable": int(verifying),
        }

    def get(self, request_id: str) -> OperationalLedgerEntry | None:
        with self._lock, self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM operational_dispatch WHERE request_id=?", (request_id,)
            ).fetchone()
            return self._entry(row) if row is not None else None

    def list_verification_candidates(self) -> tuple[OperationalLedgerEntry, ...]:
        """Return immutable entries eligible only for read-only reconciliation."""

        with self._lock, self._connect() as connection:
            rows = connection.execute(
                """SELECT * FROM operational_dispatch
                   WHERE verification_result_json IS NULL
                     AND state IN ('succeeded', 'outcome_unknown', 'verifying')
                   ORDER BY created_at, request_id"""
            ).fetchall()
        entries = tuple(self._entry(row) for row in rows)
        return tuple(
            entry
            for entry in entries
            if entry.state is OperationalLedgerState.VERIFYING
            or (
                entry.dispatch_result is not None
                and entry.dispatch_result.provider_operation_id is not None
            )
        )

    def list_transitions(
        self, request_id: str
    ) -> tuple[OperationalLedgerTransition, ...]:
        if not request_id or request_id != request_id.strip():
            raise ValueError("operational request ID must be exact and nonblank")
        with self._lock, self._connect() as connection:
            rows = connection.execute(
                """SELECT sequence, request_id, request_digest, previous_state,
                          state, occurred_at
                   FROM operational_dispatch_transitions
                   WHERE request_id=? ORDER BY sequence""",
                (request_id,),
            ).fetchall()
        try:
            return tuple(
                OperationalLedgerTransition(
                    sequence=row["sequence"],
                    request_id=row["request_id"],
                    request_digest=row["request_digest"],
                    previous_state=(
                        OperationalLedgerState(row["previous_state"])
                        if row["previous_state"] is not None
                        else None
                    ),
                    state=OperationalLedgerState(row["state"]),
                    occurred_at=datetime.fromisoformat(row["occurred_at"]),
                )
                for row in rows
            )
        except (TypeError, ValueError) as error:
            raise OperationalLedgerCorruptionError(
                "stored operational ledger transition is invalid"
            ) from error

    def append_event(self, event: OperationalDispatchAuditEvent) -> None:
        event = OperationalDispatchAuditEvent.model_validate(event.model_dump())
        with self._lock, self._connect() as connection:
            connection.execute(
                """INSERT INTO operational_dispatch_events
                   (event_id, status, occurred_at, event_json)
                   VALUES (?, ?, ?, ?)""",
                (
                    event.event_id,
                    event.status.value,
                    event.occurred_at.isoformat(),
                    event.model_dump_json(),
                ),
            )

    def list_events(self, *, limit: int = 100) -> tuple[OperationalDispatchAuditEvent, ...]:
        if limit < 1 or limit > 1000:
            raise ValueError("operational event limit must be between 1 and 1000")
        with self._lock, self._connect() as connection:
            rows = connection.execute(
                """SELECT event_json FROM operational_dispatch_events
                   ORDER BY occurred_at DESC, event_id DESC LIMIT ?""",
                (limit,),
            ).fetchall()
        try:
            return tuple(
                OperationalDispatchAuditEvent.model_validate_json(row["event_json"])
                for row in rows
            )
        except (ValueError, json.JSONDecodeError) as error:
            raise OperationalLedgerCorruptionError(
                "stored operational dispatch event is invalid"
            ) from error

    def list_request_events(
        self, request_id: str
    ) -> tuple[OperationalDispatchAuditEvent, ...]:
        """Return ordered audit facts for one immutable request only."""

        if not request_id or request_id != request_id.strip():
            raise ValueError("operational request ID must be exact and nonblank")
        with self._lock, self._connect() as connection:
            rows = connection.execute(
                """SELECT event_json FROM operational_dispatch_events
                   WHERE json_extract(event_json, '$.request_id')=?
                   ORDER BY occurred_at, event_id""",
                (request_id,),
            ).fetchall()
        try:
            return tuple(
                OperationalDispatchAuditEvent.model_validate_json(row["event_json"])
                for row in rows
            )
        except (ValueError, json.JSONDecodeError) as error:
            raise OperationalLedgerCorruptionError(
                "stored operational dispatch event is invalid"
            ) from error

    def _transition(
        self,
        request: OperationalDispatchRequest,
        *,
        expected: OperationalLedgerState,
        target: OperationalLedgerState,
        set_dispatch_started: bool = False,
    ) -> tuple[OperationalLedgerEntry, bool]:
        now = self._now().isoformat()
        with self._lock, self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = self._row_for(connection, request.request_id)
            self._check_digest(row, request)
            owner = False
            if OperationalLedgerState(row["state"]) is expected:
                if set_dispatch_started:
                    connection.execute(
                        """UPDATE operational_dispatch
                           SET state=?, dispatch_started_at=?, updated_at=?
                           WHERE request_id=? AND state=?""",
                        (target.value, now, now, request.request_id, expected.value),
                    )
                else:
                    connection.execute(
                        "UPDATE operational_dispatch SET state=?, updated_at=? WHERE request_id=? AND state=?",
                        (target.value, now, request.request_id, expected.value),
                    )
                owner = connection.total_changes == 1
                if owner:
                    self._record_transition(
                        connection,
                        request,
                        previous_state=expected,
                        state=target,
                        occurred_at=now,
                    )
                row = self._row_for(connection, request.request_id)
            connection.commit()
            return self._entry(row), owner

    @staticmethod
    def _row_for(connection: sqlite3.Connection, request_id: str) -> sqlite3.Row:
        row = connection.execute(
            "SELECT * FROM operational_dispatch WHERE request_id=?", (request_id,)
        ).fetchone()
        if row is None:
            raise KeyError(request_id)
        return row

    @staticmethod
    def _check_digest(row: sqlite3.Row, request: OperationalDispatchRequest) -> None:
        if row["request_digest"] != request.request_digest:
            raise OperationalLedgerConflictError(
                "operational request ID has a different digest"
            )

    @staticmethod
    def _record_transition(
        connection: sqlite3.Connection,
        request: OperationalDispatchRequest,
        *,
        previous_state: OperationalLedgerState | None,
        state: OperationalLedgerState,
        occurred_at: str,
    ) -> None:
        connection.execute(
            """INSERT INTO operational_dispatch_transitions
               (request_id, request_digest, previous_state, state, occurred_at)
               VALUES (?, ?, ?, ?, ?)""",
            (
                request.request_id,
                request.request_digest,
                previous_state.value if previous_state is not None else None,
                state.value,
                occurred_at,
            ),
        )

    @staticmethod
    def _entry(row: sqlite3.Row) -> OperationalLedgerEntry:
        try:
            request = OperationalDispatchRequest.model_validate_json(row["request_json"])
            dispatch = (
                OperationalDispatchResult.model_validate_json(row["dispatch_result_json"])
                if row["dispatch_result_json"] is not None
                else None
            )
            verification = (
                OperationalVerificationResult.model_validate_json(
                    row["verification_result_json"]
                )
                if row["verification_result_json"] is not None
                else None
            )
            state = OperationalLedgerState(row["state"])
            if (
                request.request_id != row["request_id"]
                or request.request_digest != row["request_digest"]
            ):
                raise ValueError("stored request identity does not match ledger row")
            if dispatch is not None and (
                dispatch.request_id != request.request_id
                or dispatch.request_digest != request.request_digest
            ):
                raise ValueError("stored dispatch result does not match ledger row")
            if state in DISPATCH_RESULT_STATES and dispatch is None:
                raise ValueError("dispatch result state is missing durable result")
            if (
                state in FINAL_STATES
                and state is not OperationalLedgerState.TARGET_REPLACED
                and verification is None
            ):
                raise ValueError("verification terminal state is missing durable result")
            if verification is not None and state not in {
                OperationalLedgerState.VERIFIED,
                OperationalLedgerState.VERIFICATION_FAILED,
                OperationalLedgerState.TARGET_REPLACED,
                OperationalLedgerState.OUTCOME_UNKNOWN,
            }:
                raise ValueError("verification result does not match ledger state")
            return OperationalLedgerEntry(
                request_id=row["request_id"],
                request_digest=row["request_digest"],
                state=state,
                request=request,
                created_at=datetime.fromisoformat(row["created_at"]),
                updated_at=datetime.fromisoformat(row["updated_at"]),
                dispatch_started_at=(
                    datetime.fromisoformat(row["dispatch_started_at"])
                    if row["dispatch_started_at"] is not None
                    else None
                ),
                dispatch_result=dispatch,
                verification_result=verification,
            )
        except (TypeError, ValueError, json.JSONDecodeError) as error:
            raise OperationalLedgerCorruptionError(
                "stored operational dispatch record is invalid"
            ) from error
