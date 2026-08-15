"""Explicit transactional migration from the accepted P2c store to P3.

P2c schema v1 has four tables. Its audit makes request_id unique, so one client
request cannot describe both sides of a rebind; its request result is the
single-record P2 result; and it has no database object representing the sole
active incarnation for a coordinate. Legacy import completion is retained as
an otherwise-orphaned row in provider_intent_requests. P3 schema v2 preserves
those tables byte-for-byte and adds separate coordinate, operation, and
actor-bound multi-event audit evidence.

Production use must retain an accepted pre-P3 activated rollback anchor before
explicit migration. Rollback restores that complete anchor; P2c code is not
required or expected to open a schema-v2 store in place.
"""

from __future__ import annotations

import re
import sqlite3
from collections.abc import Callable
from pathlib import Path

from pydantic import ValidationError

from app.models.provider_intents import (
    PROVIDER_INTENT_STORE_P2C_SCHEMA_VERSION,
    PROVIDER_INTENT_STORE_SCHEMA_VERSION,
    ProviderIntentLifecycle,
)
from app.provider_intents.legacy_import import LegacyPolicyImportResult
from app.provider_intents.store import (
    ProviderIntentStore,
    ProviderIntentStoreCorruptionError,
    ProviderIntentStoreError,
    ProviderIntentStoreSchemaError,
)

_P2C_COLUMNS = {
    "provider_intent_store_meta": ("singleton", "schema_version"),
    "provider_intent_records": (
        "intent_id", "record_version", "lifecycle", "record_json", "created_at",
        "updated_at", "schema_version",
    ),
    "provider_intent_requests": (
        "request_id", "request_digest", "result_json", "created_at",
    ),
    "provider_intent_audit": (
        "sequence", "occurred_at", "intent_id", "record_version", "request_id",
        "request_digest", "event",
    ),
}
_IMPORT_DIGEST = re.compile(
    r"^provider-intent-legacy-policy-import-request-v1:[a-f0-9]{64}$"
)


def _validate_p2c_store(connection: sqlite3.Connection) -> tuple[object, ...]:
    """Validate exact P2c SQLite structure and all persisted evidence."""

    tables = {
        row["name"]
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table' "
            "AND name NOT LIKE 'sqlite_%'"
        )
    }
    if tables != set(_P2C_COLUMNS):
        raise ProviderIntentStoreSchemaError("provider intent P2c table set is invalid")
    meta = connection.execute(
        "SELECT singleton, schema_version FROM provider_intent_store_meta"
    ).fetchall()
    if len(meta) != 1 or meta[0]["singleton"] != 1:
        raise ProviderIntentStoreSchemaError("provider intent P2c metadata is invalid")
    if meta[0]["schema_version"] != PROVIDER_INTENT_STORE_P2C_SCHEMA_VERSION:
        raise ProviderIntentStoreSchemaError(
            "provider intent migration requires exact P2c schema"
        )
    for table, expected in _P2C_COLUMNS.items():
        columns = tuple(
            row["name"] for row in connection.execute(
                f"PRAGMA table_info({table})"
            ).fetchall()
        )
        if columns != expected:
            raise ProviderIntentStoreSchemaError(
                f"provider intent P2c table '{table}' is invalid"
            )
    expected_unique = {
        "provider_intent_store_meta": set(),
        "provider_intent_records": {("intent_id", "record_version")},
        "provider_intent_requests": {("request_id",)},
        "provider_intent_audit": {
            ("intent_id", "record_version"),
            ("request_id",),
        },
    }
    for table, expected in expected_unique.items():
        actual = {
            tuple(
                row["name"]
                for row in connection.execute(
                    f"PRAGMA index_info({index['name']})"
                )
            )
            for index in connection.execute(f"PRAGMA index_list({table})")
            if index["unique"]
        }
        if actual != expected:
            raise ProviderIntentStoreSchemaError(
                f"provider intent P2c table '{table}' uniqueness is invalid"
            )
    foreign_keys = tuple(
        (
            row["id"], row["seq"], row["table"], row["from"], row["to"],
            row["on_update"], row["on_delete"], row["match"],
        )
        for row in connection.execute(
            "PRAGMA foreign_key_list(provider_intent_audit)"
        )
    )
    if foreign_keys != (
        (0, 0, "provider_intent_records", "intent_id", "intent_id", "NO ACTION", "NO ACTION", "NONE"),
        (0, 1, "provider_intent_records", "record_version", "record_version", "NO ACTION", "NO ACTION", "NONE"),
    ):
        raise ProviderIntentStoreSchemaError(
            "provider intent P2c audit foreign keys are invalid"
        )

    intent_ids = tuple(
        row["intent_id"] for row in connection.execute(
            "SELECT DISTINCT intent_id FROM provider_intent_records ORDER BY intent_id"
        )
    )
    histories = tuple(
        ProviderIntentStore._validated_history(connection, intent_id)
        for intent_id in intent_ids
    )
    audit_requests = {
        row["request_id"]
        for row in connection.execute("SELECT request_id FROM provider_intent_audit")
    }
    if {
        row["intent_id"]
        for row in connection.execute(
            "SELECT DISTINCT intent_id FROM provider_intent_audit"
        )
    } != set(intent_ids):
        raise ProviderIntentStoreCorruptionError(
            "provider intent P2c audit series set is inconsistent"
        )
    for row in connection.execute(
        "SELECT request_id, request_digest, result_json FROM "
        "provider_intent_requests ORDER BY request_id"
    ):
        if row["request_id"] in audit_requests:
            continue
        result = LegacyPolicyImportResult.model_validate_json(row["result_json"])
        if (
            result.import_id != row["request_id"]
            or _IMPORT_DIGEST.fullmatch(row["request_digest"]) is None
        ):
            raise ProviderIntentStoreCorruptionError(
                "provider intent P2c request evidence is orphaned"
            )

    active = tuple(
        history[-1]
        for history in histories
        if history and history[-1].lifecycle is ProviderIntentLifecycle.ACTIVE
    )
    coordinates = [
        (record.provider_id, record.resource_type, record.resource_id, record.intent_kind)
        for record in active
    ]
    if len(coordinates) != len(set(coordinates)):
        raise ProviderIntentStoreCorruptionError(
            "provider intent P2c store has multiple active incarnations"
        )
    return histories


def migrate_p2c_provider_intent_store(
    database_path: str | Path,
    *,
    failure_injector: Callable[[str], None] | None = None,
) -> ProviderIntentStore:
    """Explicitly migrate one caller-selected regular file; never inferred."""

    path = Path(database_path)
    if path.is_symlink() or not path.is_file():
        raise ValueError("provider intent migration path must be a regular non-symlink file")
    connection = sqlite3.connect(path, timeout=5, isolation_level=None)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA busy_timeout=5000")
    connection.execute("PRAGMA foreign_keys=ON")
    try:
        connection.execute("BEGIN IMMEDIATE")
        if connection.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise ProviderIntentStoreCorruptionError(
                "provider intent P2c database integrity check failed"
            )
        histories = _validate_p2c_store(connection)
        _inject(failure_injector, "after_p2c_validation")
        connection.execute(
            """CREATE TABLE provider_intent_active_coordinates (
                coordinate_key TEXT PRIMARY KEY,
                provider_id TEXT NOT NULL, resource_type TEXT NOT NULL,
                resource_id TEXT NOT NULL, intent_kind TEXT NOT NULL,
                intent_id TEXT NOT NULL UNIQUE,
                management_fingerprint TEXT NOT NULL, record_version INTEGER NOT NULL,
                UNIQUE (provider_id, resource_type, resource_id, intent_kind),
                FOREIGN KEY (intent_id, record_version) REFERENCES
                    provider_intent_records (intent_id, record_version))"""
        )
        _inject(failure_injector, "after_active_coordinate_schema")
        connection.execute(
            """CREATE TABLE provider_intent_operations (
                request_id TEXT PRIMARY KEY, request_digest TEXT NOT NULL,
                operator_id TEXT NOT NULL, result_json TEXT NOT NULL,
                created_at TEXT NOT NULL)"""
        )
        _inject(failure_injector, "after_operation_schema")
        connection.execute(
            """CREATE TABLE provider_intent_operation_audit (
                sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id TEXT NOT NULL UNIQUE, occurred_at TEXT NOT NULL,
                operation_id TEXT NOT NULL, request_id TEXT NOT NULL,
                operator_id TEXT NOT NULL, intent_id TEXT NOT NULL,
                record_version INTEGER NOT NULL, event TEXT NOT NULL,
                lifecycle TEXT NOT NULL, resulting_value TEXT NOT NULL,
                UNIQUE (intent_id, record_version),
                FOREIGN KEY (intent_id, record_version) REFERENCES
                    provider_intent_records (intent_id, record_version))"""
        )
        _inject(failure_injector, "after_operation_audit_schema")
        for history in histories:
            if not history or history[-1].lifecycle is not ProviderIntentLifecycle.ACTIVE:
                continue
            record = history[-1]
            ProviderIntentStore._insert_active_coordinate(connection, record)
        _inject(failure_injector, "after_active_coordinate_population")
        _inject(failure_injector, "before_schema_version_update")
        connection.execute(
            "UPDATE provider_intent_store_meta SET schema_version=? WHERE singleton=1",
            (PROVIDER_INTENT_STORE_SCHEMA_VERSION,),
        )
        _inject(failure_injector, "after_schema_version_update")
        connection.commit()
    except ProviderIntentStoreError:
        connection.rollback()
        raise
    except (sqlite3.DatabaseError, ValidationError, ValueError) as error:
        connection.rollback()
        raise ProviderIntentStoreCorruptionError(
            "provider intent P2c migration failed closed"
        ) from error
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()
    return ProviderIntentStore.open_existing(path)


def _inject(injector: Callable[[str], None] | None, stage: str) -> None:
    if injector is not None:
        injector(stage)
