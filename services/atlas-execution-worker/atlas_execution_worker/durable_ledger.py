"""Durable SQLite ledger for worker request claims and terminal results."""

from __future__ import annotations

import json
import sqlite3
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from threading import Lock
from typing import Literal

from app.execution.worker_contracts import (
    BoundedOutput,
    WorkerAttestation,
    WorkerExecutionRequest,
    WorkerExecutionResult,
    WorkerExecutionStatus,
    WorkerFailureCode,
)
from app.execution.worker_ledger_contract import (
    LEDGER_COLUMNS,
    validate_worker_ledger_row,
)

DurableState = Literal[
    "claimed",
    "executing",
    "completed",
    "failed_terminal",
    "unknown_outcome",
]
TERMINAL_STATES = {"completed", "failed_terminal", "unknown_outcome"}
_INITIALIZATION_LOCK = Lock()
_INITIALIZATION_RETRY_DELAYS = (0.01, 0.025, 0.05, 0.1, 0.2, 0.4, 0.8)


class DurableLedgerError(RuntimeError):
    """Base class for durable ledger failures."""


class DurableLedgerConflictError(DurableLedgerError):
    """A request ID was reused with different immutable evidence."""


class DurableLedgerCorruptionError(DurableLedgerError):
    """Persisted result data cannot be safely decoded or validated."""


@dataclass(frozen=True, slots=True)
class DurableLedgerEntry:
    execution_request_id: str
    request_digest: str
    schema_version: int
    state: DurableState
    created_at: str
    updated_at: str
    attempt: int
    execution_started_at: str | None = None
    workspace_token: str | None = None
    result: WorkerExecutionResult | None = None


class DurableLedgerStartConflict(DurableLedgerError):
    """Another caller already owns the start barrier; never execute again."""

    def __init__(self, entry: DurableLedgerEntry) -> None:
        super().__init__("execution start is already owned")
        self.entry = entry


class DurableRequestLedger:
    """SQLite-backed single-owner ledger with an explicit execution barrier."""

    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = Lock()
        self._initialize()

    def _connect(self, *, configure_wal: bool = False) -> sqlite3.Connection:
        connection = sqlite3.connect(
            self.database_path,
            timeout=0.5 if configure_wal else 5.0,
            isolation_level=None,
            check_same_thread=False,
        )
        try:
            connection.row_factory = sqlite3.Row
            connection.execute(
                f"PRAGMA busy_timeout={500 if configure_wal else 5000}"
            )
            connection.execute("PRAGMA foreign_keys=ON")
            connection.execute("PRAGMA journal_mode=WAL")
            connection.execute("PRAGMA synchronous=FULL")
            return connection
        except Exception:
            connection.close()
            raise

    def _initialize(self) -> None:
        with _INITIALIZATION_LOCK:
            for delay in (*_INITIALIZATION_RETRY_DELAYS, None):
                try:
                    with self._connect(configure_wal=True) as connection:
                        connection.execute(
                            """
                            CREATE TABLE IF NOT EXISTS executions (
                                execution_request_id TEXT PRIMARY KEY,
                                request_digest TEXT NOT NULL,
                                schema_version INTEGER NOT NULL,
                                state TEXT NOT NULL,
                                created_at TEXT NOT NULL,
                                updated_at TEXT NOT NULL,
                                attempt INTEGER NOT NULL DEFAULT 1,
                                execution_started_at TEXT,
                                workspace_token TEXT,
                                result_json TEXT
                            )
                            """
                        )
                        if {row[1] for row in connection.execute('PRAGMA table_info(executions)')} != LEDGER_COLUMNS:
                            raise DurableLedgerCorruptionError("unsupported worker ledger schema")
                    return
                except sqlite3.OperationalError as exc:
                    if not any(
                        marker in str(exc).lower() for marker in ("locked", "busy")
                    ) or delay is None:
                        raise
                    time.sleep(delay)

    @staticmethod
    def _now() -> str:
        return datetime.now(UTC).isoformat()

    def claim(self, request: WorkerExecutionRequest) -> DurableLedgerEntry:
        request.validate()
        now = self._now()
        with self._lock, self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT * FROM executions WHERE execution_request_id = ?",
                (request.execution_request_id,),
            ).fetchone()
            if row is None:
                connection.execute(
                    """
                    INSERT INTO executions
                    (execution_request_id, request_digest, schema_version, state,
                     created_at, updated_at, workspace_token)
                    VALUES (?, ?, ?, 'claimed', ?, ?, ?)
                    """,
                    (
                        request.execution_request_id,
                        request.request_digest,
                        request.schema_version,
                        now,
                        now,
                        request.execution_request_id,
                    ),
                )
                row = connection.execute(
                    "SELECT * FROM executions WHERE execution_request_id = ?",
                    (request.execution_request_id,),
                ).fetchone()
            else:
                self._entry(row)
                if row["request_digest"] != request.request_digest:
                    connection.rollback()
                    raise DurableLedgerConflictError("execution request ID has a different digest")
            connection.commit()
            return self._entry(row)

    def mark_executing(self, request: WorkerExecutionRequest) -> DurableLedgerEntry:
        request.validate()
        now = self._now()
        with self._lock, self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = self._row_for(connection, request.execution_request_id)
            self._check_digest(row, request)
            if row["state"] != "claimed":
                raise DurableLedgerStartConflict(self._entry(row))
            if row["state"] == "claimed":
                connection.execute(
                    """
                    UPDATE executions SET state='executing', execution_started_at=?,
                    updated_at=? WHERE execution_request_id=? AND state='claimed'
                    """,
                    (now, now, request.execution_request_id),
                )
                row = self._row_for(connection, request.execution_request_id)
            connection.commit()
            return self._entry(row)

    def persist_result(
        self,
        request: WorkerExecutionRequest,
        result: WorkerExecutionResult,
    ) -> DurableLedgerEntry:
        result.validate(request)
        state: DurableState = (
            "completed"
            if result.status is WorkerExecutionStatus.SUCCEEDED
            else "unknown_outcome"
            if result.failure_code is WorkerFailureCode.WORKER_CRASH
            else "failed_terminal"
        )
        encoded = json.dumps(result.to_dict(), sort_keys=True, separators=(",", ":"))
        now = self._now()
        with self._lock, self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = self._row_for(connection, request.execution_request_id)
            self._check_digest(row, request)
            if row["state"] in TERMINAL_STATES:
                existing = self._entry(row)
                if existing.result is None or existing.result.to_dict() != result.to_dict():
                    connection.rollback()
                    raise DurableLedgerError("terminal result is immutable")
                connection.commit()
                return existing
            if result.status is WorkerExecutionStatus.SUCCEEDED and row["state"] != "executing":
                raise DurableLedgerError("successful result requires the execution start barrier")
            candidate = dict(row)
            candidate.update(state=state, result_json=encoded, updated_at=now)
            self._entry(candidate)
            connection.execute(
                "UPDATE executions SET state=?, result_json=?, updated_at=? WHERE execution_request_id=?",
                (state, encoded, now, request.execution_request_id),
            )
            row = self._row_for(connection, request.execution_request_id)
            connection.commit()
            return self._entry(row)

    @staticmethod
    def _unknown_result(request_id: str) -> str:
        result = WorkerExecutionResult(
            schema_version=1,
            execution_request_id=request_id,
            status=WorkerExecutionStatus.UNKNOWN,
            return_code=None,
            stdout=BoundedOutput(""),
            stderr=BoundedOutput(""),
            changed_files=(),
            patch_digest=None,
            patch_size_bytes=None,
            patch_truncated=False,
            duration_seconds=0,
            failure_code=WorkerFailureCode.WORKER_CRASH,
            workspace_head=None,
            worker_attestation=WorkerAttestation(
                runtime_uid=10001,
                readonly_rootfs=True,
                no_new_privileges=True,
                effective_capabilities="0000000000000000",
                sandbox_profile="unknown-outcome",
            ),
        )
        return json.dumps(result.to_dict(), sort_keys=True, separators=(",", ":"))

    def mark_unknown_outcome(self, request_id: str) -> DurableLedgerEntry:
        now = self._now()
        encoded = self._unknown_result(request_id)
        with self._lock, self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = self._row_for(connection, request_id)
            self._entry(row)
            if row["state"] == "executing":
                connection.execute(
                    "UPDATE executions SET state='unknown_outcome', result_json=?, updated_at=? WHERE execution_request_id=?",
                    (encoded, now, request_id),
                )
                row = self._row_for(connection, request_id)
            connection.commit()
            return self._entry(row)

    def reconcile_startup(self) -> dict[str, int]:
        """Classify persisted in-flight work without relaunching anything."""

        with self._lock, self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            claimed = 0
            executing = []
            for row in connection.execute("SELECT * FROM executions"):
                entry = self._entry(row)
                if entry.state == "claimed":
                    claimed += 1
                elif entry.state == "executing":
                    executing.append(entry.execution_request_id)
            now = self._now()
            for request_id in executing:
                encoded = self._unknown_result(request_id)
                connection.execute(
                    "UPDATE executions SET state='unknown_outcome', result_json=?, updated_at=? WHERE execution_request_id=? AND state='executing'",
                    (encoded, now, request_id),
                )
            connection.commit()
        return {"claimed": claimed, "unknown_outcome": len(executing)}

    def get(self, request_id: str) -> DurableLedgerEntry | None:
        with self._lock, self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM executions WHERE execution_request_id = ?", (request_id,)
            ).fetchone()
            return self._entry(row) if row else None

    def counts(self) -> dict[str, int]:
        # Validate the same records used by execution/lookup. Corruption is not
        # healthy emptiness and must never be hidden behind aggregate counts.
        counts: dict[str, int] = {}
        with self._lock, self._connect() as connection:
            for row in connection.execute("SELECT * FROM executions"):
                entry = self._entry(row)
                counts[entry.state] = counts.get(entry.state, 0) + 1
        return counts

    def __len__(self) -> int:
        return sum(self.counts().values())

    @staticmethod
    def _row_for(connection: sqlite3.Connection, request_id: str) -> sqlite3.Row:
        row = connection.execute(
            "SELECT * FROM executions WHERE execution_request_id = ?", (request_id,)
        ).fetchone()
        if row is None:
            raise KeyError(request_id)
        return row

    @classmethod
    def _check_digest(cls, row: sqlite3.Row, request: WorkerExecutionRequest) -> None:
        cls._entry(row)
        if row["request_digest"] != request.request_digest:
            raise DurableLedgerConflictError("execution request ID has a different digest")

    @classmethod
    def _entry(cls, row: sqlite3.Row) -> DurableLedgerEntry:
        try:
            result = validate_worker_ledger_row(dict(row))
        except (TypeError, ValueError, RecursionError) as exc:
            raise DurableLedgerCorruptionError("stored worker ledger record is invalid") from exc
        return DurableLedgerEntry(
            execution_request_id=row["execution_request_id"],
            request_digest=row["request_digest"],
            schema_version=row["schema_version"],
            state=row["state"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            attempt=row["attempt"],
            execution_started_at=row["execution_started_at"],
            workspace_token=row["workspace_token"],
            result=result,
        )
