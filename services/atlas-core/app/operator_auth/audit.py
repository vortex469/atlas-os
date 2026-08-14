from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from threading import Lock
from uuid import uuid4


@dataclass(frozen=True, slots=True)
class OperatorSecurityAuditEvent:
    event_id: str
    occurred_at: datetime
    request_id: str
    operator_id: str | None
    auth_method: str | None
    action: str
    outcome: str
    reason: str


class OperatorSecurityAuditStore:
    def __init__(self, database_path: str | Path) -> None:
        self.database_path = str(database_path)
        if self.database_path != ":memory:":
            Path(self.database_path).parent.mkdir(parents=True, exist_ok=True)
        self._lock = Lock()
        with self._connect() as connection:
            connection.execute("""
                CREATE TABLE IF NOT EXISTS operator_security_audit (
                    event_id TEXT PRIMARY KEY, occurred_at TEXT NOT NULL,
                    request_id TEXT NOT NULL, operator_id TEXT, auth_method TEXT,
                    action TEXT NOT NULL, outcome TEXT NOT NULL, reason TEXT NOT NULL
                )
            """)

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path, timeout=5, check_same_thread=False)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA busy_timeout=5000")
        connection.execute("PRAGMA synchronous=FULL")
        return connection

    def append(self, event: OperatorSecurityAuditEvent) -> None:
        with self._lock, self._connect() as connection:
            connection.execute(
                "INSERT INTO operator_security_audit VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (event.event_id, event.occurred_at.isoformat(), event.request_id,
                 event.operator_id, event.auth_method, event.action, event.outcome, event.reason),
            )
        if self.database_path != ":memory:":
            Path(self.database_path).chmod(0o600)

    def record(self, **values: object) -> None:
        self.append(OperatorSecurityAuditEvent(event_id=uuid4().hex, **values))  # type: ignore[arg-type]

    def list(self) -> tuple[OperatorSecurityAuditEvent, ...]:
        with self._connect() as connection:
            rows = connection.execute("SELECT * FROM operator_security_audit ORDER BY occurred_at").fetchall()
        return tuple(OperatorSecurityAuditEvent(
            event_id=row["event_id"], occurred_at=datetime.fromisoformat(row["occurred_at"]),
            request_id=row["request_id"], operator_id=row["operator_id"],
            auth_method=row["auth_method"], action=row["action"], outcome=row["outcome"],
            reason=row["reason"],
        ) for row in rows)
