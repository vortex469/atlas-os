"""Durable SQLite selection/tombstone store with transactional CAS transitions."""

from __future__ import annotations

import hashlib
import sqlite3
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from app.installation_targets.contract import InstallationDestinationSelectionV1

MAX_ACTIVE_SELECTIONS_PER_PRINCIPAL = 16


def _utc_now() -> datetime:
    return datetime.now(UTC).replace(microsecond=0)


def _whole_second_utc(clock: Callable[[], datetime]) -> str:
    try:
        instant = clock()
    except Exception as error:
        raise SelectionStoreError("selection store open clock is unavailable") from error
    if (
        type(instant) is not datetime
        or instant.tzinfo is None
        or instant.utcoffset() != UTC.utcoffset(instant)
        or instant.microsecond != 0
    ):
        raise SelectionStoreError(
            "selection store open clock must return whole-second UTC"
        )
    return instant.strftime("%Y-%m-%dT%H:%M:%SZ")


class SelectionStoreError(RuntimeError):
    pass


class SelectionNotFoundError(SelectionStoreError):
    pass


class SelectionIdempotencyConflictError(SelectionStoreError):
    pass


class SelectionActiveLimitError(SelectionStoreError):
    pass


@dataclass(frozen=True, slots=True)
class StoredSelection:
    record: InstallationDestinationSelectionV1
    record_version: int


class InstallationDestinationSelectionStore:
    """Preserves immutable identity and terminal tombstones across restarts.

    Tombstones are retained indefinitely here. The P0 90-day purge boundary is
    intentionally deferred until Atlas has an explicit maintenance scheduler.
    """

    def __init__(
        self,
        database_path: str | Path,
        *,
        open_clock: Callable[[], datetime] = _utc_now,
    ) -> None:
        self.database_path = str(database_path)
        opened_at = _whole_second_utc(open_clock)
        if self.database_path != ":memory:":
            Path(self.database_path).parent.mkdir(parents=True, exist_ok=True)
        try:
            self._initialize(opened_at)
        except Exception as error:
            raise SelectionStoreError(
                "selection store initialization failed"
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

    def _initialize(self, opened_at: str) -> None:
        with self._connect() as connection:
            connection.execute("""
                CREATE TABLE IF NOT EXISTS installation_destination_selections (
                    selection_id TEXT PRIMARY KEY,
                    selected_by TEXT NOT NULL,
                    idempotency_identity TEXT NOT NULL,
                    idempotency_key_verifier TEXT NOT NULL,
                    request_digest TEXT NOT NULL,
                    resource_id TEXT NOT NULL,
                    record_json TEXT NOT NULL,
                    status TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    record_version INTEGER NOT NULL CHECK(record_version >= 1),
                    UNIQUE(selected_by, idempotency_identity)
                )
            """)
            connection.execute("BEGIN IMMEDIATE")
            rows = connection.execute(
                "SELECT * FROM installation_destination_selections "
                "WHERE status='active' AND expires_at<=?",
                (opened_at,),
            ).fetchall()
            for row in rows:
                stored = self._decode(row)
                expired = InstallationDestinationSelectionV1.model_validate(
                    {
                        **stored.record.model_dump(),
                        "status": "expired",
                        "terminated_at": opened_at,
                    }
                )
                if (
                    expired.selection_fingerprint
                    != stored.record.selection_fingerprint
                ):
                    raise SelectionStoreError(
                        "open-time expiry changed immutable identity"
                    )
                cursor = connection.execute(
                    "UPDATE installation_destination_selections "
                    "SET record_json=?, status='expired', "
                    "record_version=record_version+1 "
                    "WHERE selection_id=? AND record_version=? "
                    "AND status='active'",
                    (
                        expired.model_dump_json(),
                        expired.selection_id,
                        stored.record_version,
                    ),
                )
                if cursor.rowcount != 1:
                    raise SelectionStoreError("open-time expiry lost atomicity")

    @staticmethod
    def idempotency_identity(selected_by: str, idempotency_key: str) -> str:
        verifier = InstallationDestinationSelectionStore.idempotency_key_verifier(
            idempotency_key
        )
        return hashlib.sha256(
            b"atlas:installation-destination-selection-idempotency:v1\0"
            + selected_by.encode()
            + b"\0"
            + verifier.encode("ascii")
        ).hexdigest()

    @staticmethod
    def idempotency_key_verifier(idempotency_key: str) -> str:
        return hashlib.sha256(
            b"atlas:installation-destination-selection-idempotency-key:v1\0"
            + idempotency_key.encode()
        ).hexdigest()

    @staticmethod
    def _decode(row: sqlite3.Row) -> StoredSelection:
        from app.installation_targets.fingerprint import build_selection_fingerprint

        record = InstallationDestinationSelectionV1.model_validate_json(
            row["record_json"]
        )
        duplicated = {
            "selection_id": record.selection_id,
            "selected_by": record.selected_by,
            "request_digest": record.request_digest,
            "resource_id": record.resource_id,
            "status": record.status,
            "expires_at": record.expires_at,
        }
        for column, expected in duplicated.items():
            if row[column] != expected:
                raise SelectionStoreError(f"stored selection {column} mismatch")
        verifier = row["idempotency_key_verifier"]
        identity = row["idempotency_identity"]
        if (
            type(verifier) is not str
            or len(verifier) != 64
            or any(character not in "0123456789abcdef" for character in verifier)
            or type(identity) is not str
            or identity
            != hashlib.sha256(
                b"atlas:installation-destination-selection-idempotency:v1\0"
                + record.selected_by.encode()
                + b"\0"
                + verifier.encode("ascii")
            ).hexdigest()
        ):
            raise SelectionStoreError("stored idempotency index is invalid")
        record_version = row["record_version"]
        if type(record_version) is not int or record_version < 1:
            raise SelectionStoreError("stored selection record_version is invalid")
        if record.selection_fingerprint != build_selection_fingerprint(record):
            raise SelectionStoreError("stored selection fingerprint mismatch")
        return StoredSelection(record=record, record_version=record_version)

    def get_by_idempotency(
        self, *, selected_by: str, idempotency_key: str
    ) -> StoredSelection | None:
        identity = self.idempotency_identity(selected_by, idempotency_key)
        verifier = self.idempotency_key_verifier(idempotency_key)
        try:
            with self._connect() as connection:
                row = connection.execute(
                    "SELECT * FROM installation_destination_selections WHERE selected_by=? AND idempotency_identity=?",
                    (selected_by, identity),
                ).fetchone()
            if row is None:
                return None
            stored = self._decode(row)
            if row["idempotency_key_verifier"] != verifier:
                raise SelectionStoreError("stored idempotency verifier mismatch")
            return stored
        except SelectionStoreError:
            raise
        except Exception as error:
            raise SelectionStoreError("selection store read failed") from error

    def create(
        self,
        *,
        record: InstallationDestinationSelectionV1,
        idempotency_key: str,
        evaluation_time: str,
    ) -> tuple[StoredSelection, bool]:
        identity = self.idempotency_identity(record.selected_by, idempotency_key)
        verifier = self.idempotency_key_verifier(idempotency_key)
        try:
            with self._connect() as connection:
                connection.execute("BEGIN IMMEDIATE")
                prior = connection.execute(
                    "SELECT * FROM installation_destination_selections WHERE selected_by=? AND idempotency_identity=?",
                    (record.selected_by, identity),
                ).fetchone()
                if prior is not None:
                    if prior["request_digest"] != record.request_digest:
                        raise SelectionIdempotencyConflictError(
                            "idempotency identity conflicts"
                        )
                    return self._decode(prior), False
                expired_rows = connection.execute(
                    "SELECT * FROM installation_destination_selections WHERE selected_by=? AND status='active' AND expires_at<=?",
                    (record.selected_by, evaluation_time),
                ).fetchall()
                for expired_row in expired_rows:
                    stored = self._decode(expired_row)
                    expired = InstallationDestinationSelectionV1.model_validate(
                        {
                            **stored.record.model_dump(),
                            "status": "expired",
                            "terminated_at": evaluation_time,
                        }
                    )
                    connection.execute(
                        "UPDATE installation_destination_selections SET record_json=?, status='expired', record_version=record_version+1 WHERE selection_id=? AND record_version=? AND status='active'",
                        (
                            expired.model_dump_json(),
                            expired.selection_id,
                            stored.record_version,
                        ),
                    )
                active = connection.execute(
                    "SELECT COUNT(*) FROM installation_destination_selections WHERE selected_by=? AND status='active'",
                    (record.selected_by,),
                ).fetchone()[0]
                if active >= MAX_ACTIVE_SELECTIONS_PER_PRINCIPAL:
                    raise SelectionActiveLimitError("active selection limit reached")
                connection.execute(
                    "INSERT INTO installation_destination_selections VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1)",
                    (
                        record.selection_id,
                        record.selected_by,
                        identity,
                        verifier,
                        record.request_digest,
                        record.resource_id,
                        record.model_dump_json(),
                        record.status,
                        record.expires_at,
                    ),
                )
                return StoredSelection(record, 1), True
        except (
            SelectionIdempotencyConflictError,
            SelectionActiveLimitError,
            SelectionStoreError,
        ):
            raise
        except Exception as error:
            raise SelectionStoreError("selection store create failed") from error

    def get(self, selection_id: str, selected_by: str) -> StoredSelection:
        try:
            with self._connect() as connection:
                row = connection.execute(
                    "SELECT * FROM installation_destination_selections WHERE selection_id=? AND selected_by=?",
                    (selection_id, selected_by),
                ).fetchone()
            if row is None:
                raise SelectionNotFoundError("selection not found")
            return self._decode(row)
        except SelectionStoreError:
            raise
        except Exception as error:
            raise SelectionStoreError("selection store read failed") from error

    def transition(
        self, *, selection_id: str, selected_by: str, status: str, terminated_at: str
    ) -> StoredSelection:
        if status not in {"cancelled", "expired", "stale"}:
            raise ValueError("invalid terminal status")
        try:
            with self._connect() as connection:
                connection.execute("BEGIN IMMEDIATE")
                row = connection.execute(
                    "SELECT * FROM installation_destination_selections WHERE selection_id=? AND selected_by=?",
                    (selection_id, selected_by),
                ).fetchone()
                if row is None:
                    raise SelectionNotFoundError("selection not found")
                stored = self._decode(row)
                if stored.record.status != "active":
                    return stored
                updated = InstallationDestinationSelectionV1.model_validate(
                    {
                        **stored.record.model_dump(),
                        "status": status,
                        "terminated_at": terminated_at,
                    }
                )
                if updated.selection_fingerprint != stored.record.selection_fingerprint:
                    raise SelectionStoreError(
                        "terminal transition changed immutable identity"
                    )
                cursor = connection.execute(
                    "UPDATE installation_destination_selections SET record_json=?, status=?, record_version=record_version+1 "
                    "WHERE selection_id=? AND selected_by=? AND record_version=? AND status='active'",
                    (
                        updated.model_dump_json(),
                        status,
                        selection_id,
                        selected_by,
                        stored.record_version,
                    ),
                )
                if cursor.rowcount != 1:
                    winner = connection.execute(
                        "SELECT * FROM installation_destination_selections WHERE selection_id=? AND selected_by=?",
                        (selection_id, selected_by),
                    ).fetchone()
                    if winner is None:
                        raise SelectionStoreError(
                            "terminal transition winner is missing"
                        )
                    return self._decode(winner)
                return StoredSelection(updated, stored.record_version + 1)
        except SelectionStoreError:
            raise
        except Exception as error:
            raise SelectionStoreError("selection store transition failed") from error

    def list_for_principal(self, selected_by: str) -> tuple[StoredSelection, ...]:
        try:
            with self._connect() as connection:
                rows = connection.execute(
                    "SELECT * FROM installation_destination_selections WHERE selected_by=? ORDER BY selection_id",
                    (selected_by,),
                ).fetchall()
            return tuple(self._decode(row) for row in rows)
        except SelectionStoreError:
            raise
        except Exception as error:
            raise SelectionStoreError("selection store list failed") from error
