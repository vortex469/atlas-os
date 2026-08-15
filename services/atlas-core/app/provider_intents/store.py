"""Transactional SQLite persistence for exact provider-intent series."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from threading import Lock
from typing import TYPE_CHECKING

from pydantic import ValidationError

from app.models.provider_intents import (
    PROVIDER_INTENT_SCHEMA_VERSION,
    ProviderIntentAuditEvent,
    ProviderIntentAuditEventKind,
    ProviderIntentLifecycle,
    ProviderIntentMutationCommand,
    ProviderIntentMutationResult,
    ProviderIntentProvenance,
    ProviderIntentRecord,
    ProviderIntentSupersedeCommand,
    build_provider_intent_id,
)

if TYPE_CHECKING:
    from app.provider_intents.legacy_import import (
        LegacyPolicyImportCommand,
        LegacyPolicyImportResult,
    )

_TABLE_COLUMNS = {
    "provider_intent_store_meta": ("singleton", "schema_version"),
    "provider_intent_records": (
        "intent_id",
        "record_version",
        "lifecycle",
        "record_json",
        "created_at",
        "updated_at",
        "schema_version",
    ),
    "provider_intent_requests": (
        "request_id",
        "request_digest",
        "result_json",
        "created_at",
    ),
    "provider_intent_audit": (
        "sequence",
        "occurred_at",
        "intent_id",
        "record_version",
        "request_id",
        "request_digest",
        "event",
    ),
}


class ProviderIntentStoreError(RuntimeError):
    """Base error for isolated provider-intent persistence."""


class ProviderIntentStoreSchemaError(ProviderIntentStoreError):
    """Stored schema is absent, partial, or unsupported."""


class ProviderIntentStoreConflictError(ProviderIntentStoreError):
    """An idempotency or exact-version CAS precondition failed."""


class ProviderIntentStoreCorruptionError(ProviderIntentStoreError):
    """Stored provider-intent state is invalid or inconsistent."""


class ProviderIntentStore:
    """Durable store with no provider-resolution or execution authority."""

    def __init__(self, database_path: str | Path) -> None:
        self.database_path = str(database_path)
        if self.database_path == ":memory:":
            raise ValueError("provider intent store requires a durable filesystem path")
        path = Path(self.database_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.is_symlink():
            raise ValueError("provider intent store path cannot be a symbolic link")
        if path.exists() and not path.is_file():
            raise ValueError("provider intent store path must be a regular file")
        path.touch(mode=0o600, exist_ok=True)
        path.chmod(0o600)
        self._lock = Lock()
        self._initialize_or_validate()

    def _connect(self) -> sqlite3.Connection:
        try:
            connection = sqlite3.connect(
                self.database_path,
                timeout=5,
                isolation_level=None,
                check_same_thread=False,
            )
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA busy_timeout=5000")
            connection.execute("PRAGMA foreign_keys=ON")
            connection.execute("PRAGMA journal_mode=WAL")
            connection.execute("PRAGMA synchronous=FULL")
            return connection
        except sqlite3.DatabaseError as error:
            raise ProviderIntentStoreCorruptionError(
                "provider intent database cannot be opened"
            ) from error

    def _initialize_or_validate(self) -> None:
        with self._connect() as connection:
            try:
                integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
                if integrity != "ok":
                    raise ProviderIntentStoreCorruptionError(
                        "provider intent database integrity check failed"
                    )
                tables = {
                    row["name"]
                    for row in connection.execute(
                        "SELECT name FROM sqlite_master "
                        "WHERE type='table' AND name NOT LIKE 'sqlite_%'"
                    ).fetchall()
                }
                if not tables:
                    self._create_schema(connection)
                else:
                    self._validate_schema(connection, tables)
            except ProviderIntentStoreError:
                raise
            except sqlite3.DatabaseError as error:
                raise ProviderIntentStoreCorruptionError(
                    "provider intent database validation failed"
                ) from error

    @staticmethod
    def _create_schema(connection: sqlite3.Connection) -> None:
        connection.execute("BEGIN IMMEDIATE")
        try:
            connection.execute(
                """
                CREATE TABLE provider_intent_store_meta (
                    singleton INTEGER PRIMARY KEY CHECK (singleton = 1),
                    schema_version INTEGER NOT NULL
                )
                """
            )
            connection.execute(
                "INSERT INTO provider_intent_store_meta VALUES (1, ?)",
                (PROVIDER_INTENT_SCHEMA_VERSION,),
            )
            connection.execute(
                """
                CREATE TABLE provider_intent_records (
                    intent_id TEXT NOT NULL,
                    record_version INTEGER NOT NULL CHECK (record_version >= 1),
                    lifecycle TEXT NOT NULL,
                    record_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    schema_version INTEGER NOT NULL,
                    PRIMARY KEY (intent_id, record_version)
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE provider_intent_requests (
                    request_id TEXT PRIMARY KEY,
                    request_digest TEXT NOT NULL,
                    result_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE provider_intent_audit (
                    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                    occurred_at TEXT NOT NULL,
                    intent_id TEXT NOT NULL,
                    record_version INTEGER NOT NULL,
                    request_id TEXT NOT NULL UNIQUE,
                    request_digest TEXT NOT NULL,
                    event TEXT NOT NULL,
                    UNIQUE (intent_id, record_version),
                    FOREIGN KEY (intent_id, record_version)
                        REFERENCES provider_intent_records
                            (intent_id, record_version)
                )
                """
            )
            connection.commit()
        except Exception:
            connection.rollback()
            raise

    @staticmethod
    def _validate_schema(
        connection: sqlite3.Connection,
        tables: set[str],
    ) -> None:
        if tables != set(_TABLE_COLUMNS):
            raise ProviderIntentStoreSchemaError(
                "provider intent database table set is invalid"
            )
        rows = connection.execute(
            "SELECT singleton, schema_version FROM provider_intent_store_meta"
        ).fetchall()
        if len(rows) != 1 or rows[0]["singleton"] != 1:
            raise ProviderIntentStoreSchemaError(
                "provider intent store metadata is invalid"
            )
        if rows[0]["schema_version"] != PROVIDER_INTENT_SCHEMA_VERSION:
            raise ProviderIntentStoreSchemaError(
                "provider intent store schema version is unsupported"
            )
        for table, expected_columns in _TABLE_COLUMNS.items():
            columns = tuple(
                row["name"]
                for row in connection.execute(f"PRAGMA table_info({table})").fetchall()
            )
            if columns != expected_columns:
                raise ProviderIntentStoreSchemaError(
                    f"provider intent store table '{table}' is invalid"
                )
        expected_unique_columns = {
            "provider_intent_store_meta": set(),
            "provider_intent_records": {("intent_id", "record_version")},
            "provider_intent_requests": {("request_id",)},
            "provider_intent_audit": {
                ("intent_id", "record_version"),
                ("request_id",),
            },
        }
        for table, expected in expected_unique_columns.items():
            actual = {
                tuple(
                    row["name"]
                    for row in connection.execute(
                        f"PRAGMA index_info({index['name']})"
                    ).fetchall()
                )
                for index in connection.execute(
                    f"PRAGMA index_list({table})"
                ).fetchall()
                if index["unique"]
            }
            if actual != expected:
                raise ProviderIntentStoreSchemaError(
                    f"provider intent store table '{table}' uniqueness is invalid"
                )
        foreign_keys = connection.execute(
            "PRAGMA foreign_key_list(provider_intent_audit)"
        ).fetchall()
        if tuple(
            (
                row["id"],
                row["seq"],
                row["table"],
                row["from"],
                row["to"],
                row["on_update"],
                row["on_delete"],
                row["match"],
            )
            for row in foreign_keys
        ) != (
            (
                0,
                0,
                "provider_intent_records",
                "intent_id",
                "intent_id",
                "NO ACTION",
                "NO ACTION",
                "NONE",
            ),
            (
                0,
                1,
                "provider_intent_records",
                "record_version",
                "record_version",
                "NO ACTION",
                "NO ACTION",
                "NONE",
            ),
        ):
            raise ProviderIntentStoreSchemaError(
                "provider intent audit foreign keys are invalid"
            )

    def put(
        self,
        command: ProviderIntentMutationCommand,
        *,
        now: datetime | None = None,
    ) -> ProviderIntentMutationResult:
        occurred_at = self._canonical_now(now)
        with self._lock, self._connect() as connection:
            try:
                connection.execute("BEGIN IMMEDIATE")
                replay = self._replay(
                    connection,
                    command.request_id,
                    command.request_digest,
                )
                if replay is not None:
                    connection.commit()
                    return replay
                history = self._validated_history(connection, command.intent_id)
                if not history:
                    if command.expected_record_version != 0:
                        raise ProviderIntentStoreConflictError(
                            "provider intent expected version does not exist"
                        )
                    record = ProviderIntentRecord(
                        intent_id=command.intent_id,
                        record_version=1,
                        provider_id=command.provider_id,
                        resource_type=command.resource_type,
                        resource_id=command.resource_id,
                        incarnation_fingerprint=command.incarnation_fingerprint,
                        intent_kind=command.intent_kind,
                        intent_value=command.desired_value,
                        lifecycle=ProviderIntentLifecycle.ACTIVE,
                        provenance=command.provenance,
                        created_at=occurred_at,
                        updated_at=occurred_at,
                    )
                    outcome = "created"
                    event = ProviderIntentAuditEventKind.CREATED
                else:
                    current_record = history[-1]
                    if current_record.lifecycle is not ProviderIntentLifecycle.ACTIVE:
                        raise ProviderIntentStoreConflictError(
                            "superseded provider intent cannot be updated"
                        )
                    if current_record.record_version != command.expected_record_version:
                        raise ProviderIntentStoreConflictError(
                            "provider intent expected version is stale"
                        )
                    record = current_record.model_copy(
                        update={
                            "record_version": current_record.record_version + 1,
                            "intent_value": command.desired_value,
                            "updated_at": occurred_at,
                            "previous_record_version": current_record.record_version,
                        }
                    )
                    record = ProviderIntentRecord.model_validate(record.model_dump())
                    outcome = "updated"
                    event = ProviderIntentAuditEventKind.UPDATED
                result = ProviderIntentMutationResult(outcome=outcome, record=record)
                self._persist_mutation(
                    connection,
                    record=record,
                    result=result,
                    request_id=command.request_id,
                    request_digest=command.request_digest,
                    event=event,
                    occurred_at=occurred_at,
                )
                connection.commit()
                return result
            except ProviderIntentStoreError:
                connection.rollback()
                raise
            except (sqlite3.DatabaseError, ValidationError, ValueError, json.JSONDecodeError) as error:
                connection.rollback()
                raise ProviderIntentStoreCorruptionError(
                    "provider intent mutation encountered invalid stored state"
                ) from error

    def supersede(
        self,
        command: ProviderIntentSupersedeCommand,
        *,
        now: datetime | None = None,
    ) -> ProviderIntentMutationResult:
        occurred_at = self._canonical_now(now)
        with self._lock, self._connect() as connection:
            try:
                connection.execute("BEGIN IMMEDIATE")
                replay = self._replay(
                    connection,
                    command.request_id,
                    command.request_digest,
                )
                if replay is not None:
                    connection.commit()
                    return replay
                history = self._validated_history(connection, command.intent_id)
                if not history:
                    raise ProviderIntentStoreConflictError(
                        "provider intent series does not exist"
                    )
                current_record = history[-1]
                if current_record.lifecycle is not ProviderIntentLifecycle.ACTIVE:
                    raise ProviderIntentStoreConflictError(
                        "provider intent series is already superseded"
                    )
                if current_record.record_version != command.expected_record_version:
                    raise ProviderIntentStoreConflictError(
                        "provider intent expected version is stale"
                    )
                record = current_record.model_copy(
                    update={
                        "record_version": current_record.record_version + 1,
                        "lifecycle": ProviderIntentLifecycle.SUPERSEDED,
                        "updated_at": occurred_at,
                        "previous_record_version": current_record.record_version,
                    }
                )
                record = ProviderIntentRecord.model_validate(record.model_dump())
                result = ProviderIntentMutationResult(
                    outcome="superseded",
                    record=record,
                )
                self._persist_mutation(
                    connection,
                    record=record,
                    result=result,
                    request_id=command.request_id,
                    request_digest=command.request_digest,
                    event=ProviderIntentAuditEventKind.SUPERSEDED,
                    occurred_at=occurred_at,
                )
                connection.commit()
                return result
            except ProviderIntentStoreError:
                connection.rollback()
                raise
            except (sqlite3.DatabaseError, ValidationError, ValueError, json.JSONDecodeError) as error:
                connection.rollback()
                raise ProviderIntentStoreCorruptionError(
                    "provider intent supersession encountered invalid stored state"
                ) from error

    def import_legacy_policy(
        self,
        command: LegacyPolicyImportCommand,
        *,
        now: datetime | None = None,
    ) -> LegacyPolicyImportResult:
        """Atomically persist a complete legacy shadow-import evidence batch."""

        from app.provider_intents.legacy_import import LegacyPolicyImportResult

        occurred_at = self._canonical_now(now)
        with self._lock, self._connect() as connection:
            try:
                connection.execute("BEGIN IMMEDIATE")
                marker = connection.execute(
                    "SELECT request_digest, result_json FROM provider_intent_requests "
                    "WHERE request_id=?",
                    (command.import_id,),
                ).fetchone()
                if marker is not None:
                    if marker["request_digest"] != command.import_digest:
                        raise ProviderIntentStoreConflictError(
                            "legacy import ID has a different digest"
                        )
                    stored = LegacyPolicyImportResult.model_validate_json(
                        marker["result_json"]
                    )
                    self._validate_legacy_import_replay(connection, command, stored)
                    connection.commit()
                    return stored

                source_references: list[str] = []
                for entry in command.entries:
                    intent_id = build_provider_intent_id(
                        provider_id=entry.provider_id,
                        resource_type=None,
                        resource_id=entry.resource_id,
                        incarnation_fingerprint=None,
                        intent_kind=entry.intent_kind,
                    )
                    history = self._validated_history(connection, intent_id)
                    previous = history[-1] if history else None
                    record = ProviderIntentRecord(
                        intent_id=intent_id,
                        record_version=1 if previous is None else previous.record_version + 1,
                        provider_id=entry.provider_id,
                        resource_type=None,
                        resource_id=entry.resource_id,
                        incarnation_fingerprint=None,
                        intent_kind=entry.intent_kind,
                        intent_value=entry.intent_value,
                        lifecycle=ProviderIntentLifecycle.LEGACY_UNBOUND,
                        provenance=ProviderIntentProvenance.LEGACY_POLICY_IMPORT,
                        source_reference=entry.source_reference,
                        created_at=occurred_at if previous is None else previous.created_at,
                        updated_at=occurred_at,
                        previous_record_version=(
                            None if previous is None else previous.record_version
                        ),
                    )
                    event = (
                        ProviderIntentAuditEventKind.CREATED
                        if previous is None
                        else ProviderIntentAuditEventKind.UPDATED
                    )
                    result = ProviderIntentMutationResult(
                        outcome=event.value,
                        record=record,
                    )
                    self._persist_mutation(
                        connection,
                        record=record,
                        result=result,
                        request_id=entry.source_reference,
                        request_digest=entry.source_reference,
                        event=event,
                        occurred_at=occurred_at,
                    )
                    source_references.append(entry.source_reference)

                records_digest = self._legacy_records_digest(source_references)
                completed = LegacyPolicyImportResult(
                    outcome="imported",
                    import_id=command.import_id,
                    source_policy_digest=command.source_policy_digest,
                    record_count=len(source_references),
                    records_digest=records_digest,
                )
                connection.execute(
                    "INSERT INTO provider_intent_requests VALUES (?, ?, ?, ?)",
                    (
                        command.import_id,
                        command.import_digest,
                        completed.model_dump_json(),
                        occurred_at.isoformat(),
                    ),
                )
                connection.commit()
                return completed
            except ProviderIntentStoreError:
                connection.rollback()
                raise
            except (sqlite3.DatabaseError, ValidationError, ValueError, json.JSONDecodeError) as error:
                connection.rollback()
                raise ProviderIntentStoreCorruptionError(
                    "legacy provider intent import encountered invalid stored state"
                ) from error

    @staticmethod
    def _legacy_records_digest(source_references: list[str]) -> str:
        encoded = json.dumps(
            sorted(source_references), separators=(",", ":")
        ).encode()
        return (
            "provider-intent-legacy-policy-records-v1:"
            f"{hashlib.sha256(encoded).hexdigest()}"
        )

    @classmethod
    def _validate_legacy_import_replay(
        cls,
        connection: sqlite3.Connection,
        command: LegacyPolicyImportCommand,
        stored: LegacyPolicyImportResult,
    ) -> None:
        if (
            stored.outcome != "imported"
            or stored.import_id != command.import_id
            or stored.source_policy_digest != command.source_policy_digest
            or stored.record_count != len(command.entries)
        ):
            raise ProviderIntentStoreCorruptionError(
                "legacy import completion evidence is inconsistent"
            )
        source_references: list[str] = []
        for entry in command.entries:
            result = cls._replay(
                connection,
                entry.source_reference,
                entry.source_reference,
            )
            if result is None or result.record.source_reference != entry.source_reference:
                raise ProviderIntentStoreCorruptionError(
                    "legacy import record evidence is incomplete"
                )
            source_references.append(entry.source_reference)
        if stored.records_digest != cls._legacy_records_digest(source_references):
            raise ProviderIntentStoreCorruptionError(
                "legacy import record digest is inconsistent"
            )

    def get_current(self, intent_id: str) -> ProviderIntentRecord | None:
        with self._connect() as connection:
            try:
                records = self._validated_history(connection, intent_id)
                return None if not records else records[-1]
            except ProviderIntentStoreError:
                raise
            except (sqlite3.DatabaseError, ValidationError, ValueError, json.JSONDecodeError) as error:
                raise ProviderIntentStoreCorruptionError(
                    "provider intent current record is invalid"
                ) from error

    def history(self, intent_id: str) -> tuple[ProviderIntentRecord, ...]:
        with self._connect() as connection:
            try:
                return self._validated_history(connection, intent_id)
            except ProviderIntentStoreError:
                raise
            except (sqlite3.DatabaseError, ValidationError, ValueError, json.JSONDecodeError) as error:
                raise ProviderIntentStoreCorruptionError(
                    "provider intent history is invalid"
                ) from error

    def audit(self, intent_id: str) -> tuple[ProviderIntentAuditEvent, ...]:
        with self._connect() as connection:
            try:
                self._validated_history(connection, intent_id)
                rows = connection.execute(
                    "SELECT * FROM provider_intent_audit "
                    "WHERE intent_id=? ORDER BY sequence",
                    (intent_id,),
                ).fetchall()
                return tuple(
                    ProviderIntentAuditEvent(
                        sequence=row["sequence"],
                        occurred_at=datetime.fromisoformat(row["occurred_at"]),
                        intent_id=row["intent_id"],
                        record_version=row["record_version"],
                        request_id=row["request_id"],
                        request_digest=row["request_digest"],
                        event=ProviderIntentAuditEventKind(row["event"]),
                    )
                    for row in rows
                )
            except (sqlite3.DatabaseError, ValidationError, ValueError) as error:
                raise ProviderIntentStoreCorruptionError(
                    "provider intent audit history is invalid"
                ) from error

    @classmethod
    def _validated_history(
        cls,
        connection: sqlite3.Connection,
        intent_id: str,
    ) -> tuple[ProviderIntentRecord, ...]:
        rows = connection.execute(
            "SELECT * FROM provider_intent_records "
            "WHERE intent_id=? ORDER BY record_version",
            (intent_id,),
        ).fetchall()
        records = tuple(cls._decode_record(row) for row in rows)
        if tuple(record.record_version for record in records) != tuple(
            range(1, len(records) + 1)
        ):
            raise ProviderIntentStoreCorruptionError(
                "provider intent history version chain is invalid"
            )
        evidence = connection.execute(
            "SELECT * FROM provider_intent_audit "
            "WHERE intent_id=? ORDER BY record_version",
            (intent_id,),
        ).fetchall()
        if len(evidence) != len(records):
            raise ProviderIntentStoreCorruptionError(
                "provider intent history audit evidence is incomplete"
            )
        for record, audit_row in zip(records, evidence, strict=True):
            expected_event = (
                ProviderIntentAuditEventKind.CREATED.value
                if record.record_version == 1
                else ProviderIntentAuditEventKind.SUPERSEDED.value
                if record.lifecycle is ProviderIntentLifecycle.SUPERSEDED
                else ProviderIntentAuditEventKind.UPDATED.value
            )
            request_row = connection.execute(
                "SELECT request_digest, result_json FROM provider_intent_requests "
                "WHERE request_id=?",
                (audit_row["request_id"],),
            ).fetchone()
            if request_row is None:
                raise ProviderIntentStoreCorruptionError(
                    "provider intent history request evidence is incomplete"
                )
            result = ProviderIntentMutationResult.model_validate_json(
                request_row["result_json"]
            )
            if (
                audit_row["record_version"] != record.record_version
                or audit_row["request_digest"] != request_row["request_digest"]
                or audit_row["event"] != expected_event
                or result.record != record
                or result.outcome != expected_event
            ):
                raise ProviderIntentStoreCorruptionError(
                    "provider intent history evidence is inconsistent"
                )
        return records

    @staticmethod
    def _canonical_now(value: datetime | None) -> datetime:
        timestamp = value or datetime.now(UTC)
        if timestamp.tzinfo is None or timestamp.utcoffset() is None:
            raise ValueError("provider intent store timestamp must be timezone-aware")
        return timestamp.astimezone(UTC)

    @staticmethod
    def _decode_record(row: sqlite3.Row) -> ProviderIntentRecord:
        record = ProviderIntentRecord.model_validate_json(row["record_json"])
        if (
            record.intent_id != row["intent_id"]
            or record.record_version != row["record_version"]
            or record.lifecycle.value != row["lifecycle"]
            or record.created_at.isoformat() != row["created_at"]
            or record.updated_at.isoformat() != row["updated_at"]
            or record.schema_version != row["schema_version"]
        ):
            raise ProviderIntentStoreCorruptionError(
                "provider intent record columns do not match payload"
            )
        return record

    @staticmethod
    def _replay(
        connection: sqlite3.Connection,
        request_id: str,
        request_digest: str,
    ) -> ProviderIntentMutationResult | None:
        row = connection.execute(
            "SELECT request_digest, result_json FROM provider_intent_requests "
            "WHERE request_id=?",
            (request_id,),
        ).fetchone()
        if row is None:
            return None
        if row["request_digest"] != request_digest:
            raise ProviderIntentStoreConflictError(
                "provider intent request ID has a different digest"
            )
        result = ProviderIntentMutationResult.model_validate_json(row["result_json"])
        record_row = connection.execute(
            "SELECT * FROM provider_intent_records "
            "WHERE intent_id=? AND record_version=?",
            (result.record.intent_id, result.record.record_version),
        ).fetchone()
        audit_row = connection.execute(
            "SELECT intent_id, record_version, request_digest, event "
            "FROM provider_intent_audit WHERE request_id=?",
            (request_id,),
        ).fetchone()
        expected_event = {
            "created": ProviderIntentAuditEventKind.CREATED.value,
            "updated": ProviderIntentAuditEventKind.UPDATED.value,
            "superseded": ProviderIntentAuditEventKind.SUPERSEDED.value,
        }[result.outcome]
        if (
            record_row is None
            or ProviderIntentStore._decode_record(record_row) != result.record
            or audit_row is None
            or audit_row["intent_id"] != result.record.intent_id
            or audit_row["record_version"] != result.record.record_version
            or audit_row["request_digest"] != request_digest
            or audit_row["event"] != expected_event
        ):
            raise ProviderIntentStoreCorruptionError(
                "provider intent replay evidence is inconsistent"
            )
        return result

    @staticmethod
    def _persist_mutation(
        connection: sqlite3.Connection,
        *,
        record: ProviderIntentRecord,
        result: ProviderIntentMutationResult,
        request_id: str,
        request_digest: str,
        event: ProviderIntentAuditEventKind,
        occurred_at: datetime,
    ) -> None:
        connection.execute(
            "INSERT INTO provider_intent_records VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                record.intent_id,
                record.record_version,
                record.lifecycle.value,
                record.model_dump_json(),
                record.created_at.isoformat(),
                record.updated_at.isoformat(),
                record.schema_version,
            ),
        )
        connection.execute(
            "INSERT INTO provider_intent_audit "
            "(occurred_at, intent_id, record_version, request_id, request_digest, event) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                occurred_at.isoformat(),
                record.intent_id,
                record.record_version,
                request_id,
                request_digest,
                event.value,
            ),
        )
        connection.execute(
            "INSERT INTO provider_intent_requests VALUES (?, ?, ?, ?)",
            (
                request_id,
                request_digest,
                result.model_dump_json(),
                occurred_at.isoformat(),
            ),
        )
