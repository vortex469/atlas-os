import json
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from threading import Lock

from app.actions.models import (
    ProviderActionAuditEntry,
    ProviderActionHistoryProvider,
    ProviderActionHistorySummary,
    ProviderActionPruneResult,
)
from app.config.settings import settings
from app.core.logging import get_logger


logger = get_logger("atlas.actions.history")


def utc_iso(timestamp: datetime) -> str:
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=timezone.utc)

    return timestamp.astimezone(timezone.utc).isoformat()


class ProviderActionHistory:
    """SQLite-backed history of provider action executions."""

    def __init__(
        self,
        database_path: str | Path = ":memory:",
        *,
        max_entries: int = 5000,
        retention_days: int = 90,
    ) -> None:
        if max_entries < 1:
            raise ValueError("max_entries must be at least 1.")
        if retention_days < 1:
            raise ValueError("retention_days must be at least 1.")

        self._database_path = str(database_path)
        self._max_entries = max_entries
        self._retention_days = retention_days
        self._lock = Lock()

        if self._database_path != ":memory:":
            Path(self._database_path).parent.mkdir(
                parents=True,
                exist_ok=True,
            )

        self._connection = sqlite3.connect(
            self._database_path,
            check_same_thread=False,
        )
        self._connection.row_factory = sqlite3.Row

        if self._database_path != ":memory:":
            self._connection.execute("PRAGMA journal_mode=WAL")

        self._connection.execute("PRAGMA foreign_keys=ON")
        self._initialize_schema()

    def _initialize_schema(self) -> None:
        with self._connection:
            self._connection.execute(
                """
                CREATE TABLE IF NOT EXISTS provider_action_history (
                    id TEXT PRIMARY KEY,
                    provider_id TEXT NOT NULL,
                    provider_name TEXT NOT NULL,
                    action_id TEXT NOT NULL,
                    action_label TEXT NOT NULL,
                    status TEXT NOT NULL
                        CHECK (status IN ('succeeded', 'failed')),
                    success INTEGER NOT NULL,
                    message TEXT NOT NULL,
                    confirmed INTEGER NOT NULL,
                    destructive INTEGER NOT NULL,
                    parameter_names TEXT NOT NULL,
                    request_id TEXT,
                    started_at TEXT NOT NULL,
                    completed_at TEXT NOT NULL,
                    duration_ms REAL NOT NULL
                        CHECK (duration_ms >= 0)
                )
                """,
            )
            self._connection.execute(
                """
                CREATE INDEX IF NOT EXISTS
                    idx_provider_action_history_completed_at
                ON provider_action_history (completed_at DESC)
                """,
            )
            self._connection.execute(
                """
                CREATE INDEX IF NOT EXISTS
                    idx_provider_action_history_provider_status
                ON provider_action_history (
                    provider_id,
                    status,
                    completed_at DESC
                )
                """,
            )

    def append(self, entry: ProviderActionAuditEntry) -> None:
        values = (
            entry.id,
            entry.provider_id,
            entry.provider_name,
            entry.action_id,
            entry.action_label,
            entry.status,
            int(entry.success),
            entry.message,
            int(entry.confirmed),
            int(entry.destructive),
            json.dumps(entry.parameter_names),
            entry.request_id,
            utc_iso(entry.started_at),
            utc_iso(entry.completed_at),
            entry.duration_ms,
        )

        with self._lock, self._connection:
            self._connection.execute(
                """
                INSERT INTO provider_action_history (
                    id,
                    provider_id,
                    provider_name,
                    action_id,
                    action_label,
                    status,
                    success,
                    message,
                    confirmed,
                    destructive,
                    parameter_names,
                    request_id,
                    started_at,
                    completed_at,
                    duration_ms
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                values,
            )
            self._prune()

    def _retention_cutoff(self) -> datetime:
        return datetime.now(timezone.utc) - timedelta(
            days=self._retention_days,
        )

    def _prune_expired(self, cutoff: datetime) -> int:
        cursor = self._connection.execute(
            """
            DELETE FROM provider_action_history
            WHERE completed_at < ?
            """,
            (cutoff.isoformat(),),
        )

        return cursor.rowcount

    def _prune_excess(self) -> int:
        cursor = self._connection.execute(
            """
            DELETE FROM provider_action_history
            WHERE id NOT IN (
                SELECT id
                FROM provider_action_history
                ORDER BY completed_at DESC, rowid DESC
                LIMIT ?
            )
            """,
            (self._max_entries,),
        )

        return cursor.rowcount

    def _prune(self) -> None:
        self._prune_expired(self._retention_cutoff())
        self._prune_excess()

    def prune_expired(self) -> ProviderActionPruneResult:
        cutoff = self._retention_cutoff()

        with self._lock, self._connection:
            deleted_entries = self._prune_expired(cutoff)
            row = self._connection.execute(
                """
                SELECT COUNT(*) AS entry_count
                FROM provider_action_history
                """,
            ).fetchone()

        return ProviderActionPruneResult(
            deleted_entries=deleted_entries,
            remaining_entries=int(row["entry_count"]),
            cutoff=cutoff,
        )

    def summary(self) -> ProviderActionHistorySummary:
        with self._lock, self._connection:
            self._prune()
            row = self._connection.execute(
                """
                SELECT
                    COUNT(*) AS entry_count,
                    MIN(completed_at) AS oldest_entry_at,
                    MAX(completed_at) AS newest_entry_at
                FROM provider_action_history
                """,
            ).fetchone()

        return ProviderActionHistorySummary(
            entry_count=int(row["entry_count"]),
            max_entries=self._max_entries,
            retention_days=self._retention_days,
            oldest_entry_at=(
                datetime.fromisoformat(row["oldest_entry_at"])
                if row["oldest_entry_at"]
                else None
            ),
            newest_entry_at=(
                datetime.fromisoformat(row["newest_entry_at"])
                if row["newest_entry_at"]
                else None
            ),
        )

    def export_entries(
        self,
        *,
        provider_id: str | None = None,
        status: str | None = None,
        completed_from: datetime | None = None,
        completed_to: datetime | None = None,
    ) -> list[ProviderActionAuditEntry]:
        return self.list(
            limit=self._max_entries,
            provider_id=provider_id,
            status=status,
            completed_from=completed_from,
            completed_to=completed_to,
        )

    def providers(self) -> list[ProviderActionHistoryProvider]:
        with self._lock, self._connection:
            self._prune()
            rows = self._connection.execute(
                """
                SELECT history.provider_id, history.provider_name
                FROM provider_action_history AS history
                WHERE history.rowid = (
                    SELECT latest.rowid
                    FROM provider_action_history AS latest
                    WHERE latest.provider_id = history.provider_id
                    ORDER BY latest.completed_at DESC, latest.rowid DESC
                    LIMIT 1
                )
                ORDER BY history.provider_name, history.provider_id
                """,
            ).fetchall()

        return [
            ProviderActionHistoryProvider(
                id=row["provider_id"],
                name=row["provider_name"],
            )
            for row in rows
        ]

    def list(
        self,
        *,
        limit: int = 50,
        provider_id: str | None = None,
        status: str | None = None,
        completed_from: datetime | None = None,
        completed_to: datetime | None = None,
    ) -> list[ProviderActionAuditEntry]:
        conditions: list[str] = []
        parameters: list[str | int] = []

        if provider_id is not None:
            conditions.append("provider_id = ?")
            parameters.append(provider_id)
        if status is not None:
            conditions.append("status = ?")
            parameters.append(status)
        if completed_from is not None:
            conditions.append("completed_at >= ?")
            parameters.append(utc_iso(completed_from))
        if completed_to is not None:
            conditions.append("completed_at <= ?")
            parameters.append(utc_iso(completed_to))

        where_clause = (
            f"WHERE {' AND '.join(conditions)}"
            if conditions
            else ""
        )
        parameters.append(limit)

        with self._lock, self._connection:
            self._prune()
            rows = self._connection.execute(
                f"""
                SELECT *
                FROM provider_action_history
                {where_clause}
                ORDER BY completed_at DESC, rowid DESC
                LIMIT ?
                """,
                parameters,
            ).fetchall()

        return [
            ProviderActionAuditEntry(
                id=row["id"],
                provider_id=row["provider_id"],
                provider_name=row["provider_name"],
                action_id=row["action_id"],
                action_label=row["action_label"],
                status=row["status"],
                success=bool(row["success"]),
                message=row["message"],
                confirmed=bool(row["confirmed"]),
                destructive=bool(row["destructive"]),
                parameter_names=json.loads(
                    row["parameter_names"],
                ),
                request_id=row["request_id"],
                started_at=datetime.fromisoformat(
                    row["started_at"],
                ),
                completed_at=datetime.fromisoformat(
                    row["completed_at"],
                ),
                duration_ms=row["duration_ms"],
            )
            for row in rows
        ]

    def clear(self) -> None:
        with self._lock, self._connection:
            self._connection.execute(
                "DELETE FROM provider_action_history",
            )

    def close(self) -> None:
        with self._lock:
            self._connection.close()

    def __len__(self) -> int:
        with self._lock:
            row = self._connection.execute(
                """
                SELECT COUNT(*) AS entry_count
                FROM provider_action_history
                """,
            ).fetchone()

        return int(row["entry_count"])


def create_provider_action_history() -> ProviderActionHistory:
    try:
        return ProviderActionHistory(
            database_path=settings.audit.database,
            max_entries=settings.audit.max_entries,
            retention_days=settings.audit.retention_days,
        )
    except (OSError, sqlite3.Error) as error:
        logger.warning(
            "Unable to open action history database %s; "
            "falling back to process-local memory: %s",
            settings.audit.database,
            error,
        )
        return ProviderActionHistory(
            max_entries=settings.audit.max_entries,
            retention_days=settings.audit.retention_days,
        )


provider_action_history = create_provider_action_history()


def get_provider_action_history() -> ProviderActionHistory:
    return provider_action_history


def record_provider_action_audit(
    entry: ProviderActionAuditEntry,
) -> None:
    try:
        get_provider_action_history().append(entry)
    except (OSError, sqlite3.Error) as error:
        logger.error(
            "Unable to persist provider action audit entry %s: %s",
            entry.id,
            error,
        )
