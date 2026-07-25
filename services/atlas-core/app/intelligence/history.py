from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path
from threading import Lock
from uuid import uuid4

from app.config.settings import settings
from app.intelligence.report import (
    IntelligenceTelemetry,
    IntelligenceTelemetrySnapshot,
)


class IntelligenceTelemetryHistory:
    """SQLite-backed history of ACE provider collection telemetry."""

    def __init__(
        self,
        database_path: str | Path = ":memory:",
        *,
        max_entries: int = 10_000,
        retention_days: int = 30,
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

        with self._connection:
            self._connection.execute(
                """
                CREATE TABLE IF NOT EXISTS intelligence_telemetry (
                    id TEXT PRIMARY KEY,
                    collected_at TEXT NOT NULL,
                    telemetry TEXT NOT NULL
                )
                """,
            )
            self._connection.execute(
                """
                CREATE INDEX IF NOT EXISTS
                    idx_intelligence_telemetry_collected_at
                ON intelligence_telemetry (collected_at DESC)
                """,
            )

    def append(
        self,
        telemetry: IntelligenceTelemetry,
        *,
        collected_at: datetime | None = None,
    ) -> IntelligenceTelemetrySnapshot:
        timestamp = collected_at or datetime.now(UTC)
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=UTC)
        timestamp = timestamp.astimezone(UTC)
        snapshot = IntelligenceTelemetrySnapshot(
            id=str(uuid4()),
            collected_at=timestamp,
            telemetry=telemetry,
        )

        with self._lock, self._connection:
            self._connection.execute(
                """
                INSERT INTO intelligence_telemetry (
                    id,
                    collected_at,
                    telemetry
                ) VALUES (?, ?, ?)
                """,
                (
                    snapshot.id,
                    snapshot.collected_at.isoformat(),
                    json.dumps(
                        telemetry.model_dump(mode="json"),
                        separators=(",", ":"),
                    ),
                ),
            )
            self._prune_locked(timestamp)

        return snapshot

    def list(
        self,
        *,
        limit: int = 50,
    ) -> list[IntelligenceTelemetrySnapshot]:
        if limit < 1 or limit > 500:
            raise ValueError("limit must be between 1 and 500.")

        with self._lock:
            rows = self._connection.execute(
                """
                SELECT id, collected_at, telemetry
                FROM intelligence_telemetry
                ORDER BY collected_at DESC, id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()

        return [
            IntelligenceTelemetrySnapshot(
                id=row["id"],
                collected_at=datetime.fromisoformat(
                    row["collected_at"]
                ),
                telemetry=IntelligenceTelemetry.model_validate(
                    json.loads(row["telemetry"])
                ),
            )
            for row in rows
        ]

    def _prune_locked(self, now: datetime) -> None:
        cutoff = now - timedelta(days=self._retention_days)
        self._connection.execute(
            """
            DELETE FROM intelligence_telemetry
            WHERE collected_at < ?
            """,
            (cutoff.isoformat(),),
        )
        self._connection.execute(
            """
            DELETE FROM intelligence_telemetry
            WHERE id IN (
                SELECT id
                FROM intelligence_telemetry
                ORDER BY collected_at DESC, id DESC
                LIMIT -1 OFFSET ?
            )
            """,
            (self._max_entries,),
        )

    def close(self) -> None:
        with self._lock:
            self._connection.close()


intelligence_telemetry_history = IntelligenceTelemetryHistory(
    database_path=settings.intelligence.telemetry_database,
    max_entries=settings.intelligence.telemetry_max_entries,
    retention_days=settings.intelligence.telemetry_retention_days,
)
