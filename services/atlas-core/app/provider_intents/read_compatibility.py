"""Read-only compatibility for activated P2c authority during P3 rollout."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Protocol

from app.models.provider_intents import (
    PROVIDER_INTENT_STORE_P2C_SCHEMA_VERSION,
    PROVIDER_INTENT_STORE_SCHEMA_VERSION,
    ProviderIntentLifecycle,
)
from app.provider_intents.backup_validation import (
    validate_activated_provider_intent_backup_store,
)
from app.provider_intents.migration import _validate_p2c_store
from app.provider_intents.store import (
    ProviderIntentReadSnapshot,
    ProviderIntentStore,
    ProviderIntentStoreCorruptionError,
)


class ProviderIntentReadStore(Protocol):
    """Narrow authority dependency shared by P2c and P3 readers."""

    def read_snapshot(self) -> ProviderIntentReadSnapshot:
        """Return one validated immutable authority snapshot."""


class P2cProviderIntentReadStore:
    """Read-only facade; deliberately exposes no mutation or migration method."""

    def __init__(self, database_path: Path) -> None:
        self.database_path = str(database_path)
        with self._connect() as connection:
            connection.execute("BEGIN")
            self._validate_integrity(connection)
            _validate_p2c_store(connection)
            connection.commit()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(
            f"file:{Path(self.database_path).resolve()}?mode=ro",
            uri=True,
            isolation_level=None,
        )
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA busy_timeout=5000")
        connection.execute("PRAGMA query_only=ON")
        connection.execute("PRAGMA foreign_keys=ON")
        return connection

    @staticmethod
    def _validate_integrity(connection: sqlite3.Connection) -> None:
        if connection.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise ProviderIntentStoreCorruptionError(
                "provider intent P2c database integrity check failed"
            )

    def read_snapshot(self) -> ProviderIntentReadSnapshot:
        with self._connect() as connection:
            connection.execute("BEGIN")
            self._validate_integrity(connection)
            histories = _validate_p2c_store(connection)
            current = tuple(history[-1] for history in histories if history)
            identity_bound = tuple(
                sorted(
                    (
                        record
                        for record in current
                        if record.resource_type is not None
                        and record.incarnation_fingerprint is not None
                    ),
                    key=ProviderIntentStore._record_order,
                )
            )
            legacy = tuple(
                sorted(
                    (
                        record
                        for history in histories
                        for record in history
                        if record.lifecycle
                        is ProviderIntentLifecycle.LEGACY_UNBOUND
                    ),
                    key=ProviderIntentStore._history_record_order,
                )
            )
            snapshot = ProviderIntentReadSnapshot(
                current_identity_bound_records=identity_bound,
                active_identity_bound_records=tuple(
                    record
                    for record in identity_bound
                    if record.lifecycle is ProviderIntentLifecycle.ACTIVE
                ),
                legacy_unbound_records=legacy,
            )
            connection.commit()
            return snapshot


def open_activated_provider_intent_read_store(
    database_path: Path,
    policy_path: Path,
    expected_import_id: str,
) -> ProviderIntentReadStore:
    """Open exact P2c or P3 for reads without migration or schema rewriting."""

    if database_path.is_symlink() or not database_path.is_file():
        raise ValueError(
            "activated Provider Intent store must be a regular non-symlink file"
        )
    with sqlite3.connect(
        f"file:{database_path.resolve()}?mode=ro", uri=True
    ) as connection:
        row = connection.execute(
            "SELECT schema_version FROM provider_intent_store_meta WHERE singleton=1"
        ).fetchone()
    if row is None:
        raise ValueError("activated Provider Intent store metadata is missing")
    if row[0] == PROVIDER_INTENT_STORE_SCHEMA_VERSION:
        from app.provider_intents.legacy_import import (
            validate_activated_provider_intent_store,
        )

        return validate_activated_provider_intent_store(
            database_path, policy_path, expected_import_id
        )
    if row[0] != PROVIDER_INTENT_STORE_P2C_SCHEMA_VERSION:
        raise ValueError("activated Provider Intent store schema is unsupported")
    validate_activated_provider_intent_backup_store(
        database_path, policy_path, expected_import_id
    )
    return P2cProviderIntentReadStore(database_path)
