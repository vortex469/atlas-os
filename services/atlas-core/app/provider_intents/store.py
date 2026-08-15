"""Transactional SQLite persistence for exact provider-intent series."""

from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from threading import Lock
from typing import TYPE_CHECKING, NamedTuple

from pydantic import ValidationError

from app.models.provider_intents import (
    PROVIDER_INTENT_STORE_SCHEMA_VERSION,
    ProviderIntentAuditEvent,
    ProviderIntentAuditEventKind,
    ProviderIntentCoordinateMutationCommand,
    ProviderIntentCoordinateMutationResult,
    ProviderIntentDomainAuditEvent,
    ProviderIntentKind,
    ProviderIntentLifecycle,
    ProviderIntentMutationCommand,
    ProviderIntentMutationResult,
    ProviderIntentProvenance,
    ProviderIntentRecord,
    ProviderIntentSupersedeCommand,
    ProviderIntentValue,
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
    "provider_intent_active_coordinates": (
        "coordinate_key",
        "provider_id",
        "resource_type",
        "resource_id",
        "intent_kind",
        "intent_id",
        "management_fingerprint",
        "record_version",
    ),
    "provider_intent_operations": (
        "request_id",
        "request_digest",
        "operator_id",
        "result_json",
        "created_at",
    ),
    "provider_intent_operation_audit": (
        "sequence",
        "event_id",
        "occurred_at",
        "operation_id",
        "request_id",
        "operator_id",
        "intent_id",
        "record_version",
        "event",
        "lifecycle",
        "resulting_value",
    ),
}
_LEGACY_IMPORT_REQUEST_DIGEST = re.compile(
    r"^provider-intent-legacy-policy-import-request-v1:[a-f0-9]{64}$"
)
_COORDINATE_MUTATION_DIGEST = re.compile(
    r"^provider-intent-coordinate-mutation-v1:[a-f0-9]{64}$"
)


class ProviderIntentStoreError(RuntimeError):
    """Base error for isolated provider-intent persistence."""


class ProviderIntentStoreSchemaError(ProviderIntentStoreError):
    """Stored schema is absent, partial, or unsupported."""


class ProviderIntentStoreConflictError(ProviderIntentStoreError):
    """An idempotency or exact-version CAS precondition failed."""


class ProviderIntentStoreCorruptionError(ProviderIntentStoreError):
    """Stored provider-intent state is invalid or inconsistent."""


class ProviderIntentReadSnapshot(NamedTuple):
    """One coherent, immutable, fully validated store generation."""

    current_identity_bound_records: tuple[ProviderIntentRecord, ...]
    active_identity_bound_records: tuple[ProviderIntentRecord, ...]
    legacy_unbound_records: tuple[ProviderIntentRecord, ...]


class ProviderIntentStore:
    """Durable store with no provider-resolution or execution authority."""

    def __init__(
        self,
        database_path: str | Path,
        *,
        create_if_missing: bool = True,
    ) -> None:
        self.database_path = str(database_path)
        if self.database_path == ":memory:":
            raise ValueError("provider intent store requires a durable filesystem path")
        path = Path(self.database_path)
        if create_if_missing:
            path.parent.mkdir(parents=True, exist_ok=True)
        if path.is_symlink():
            raise ValueError("provider intent store path cannot be a symbolic link")
        if not create_if_missing and not path.exists():
            raise ProviderIntentStoreSchemaError(
                "activated provider intent database does not exist"
            )
        if path.exists() and not path.is_file():
            raise ValueError("provider intent store path must be a regular file")
        if create_if_missing:
            path.touch(mode=0o600, exist_ok=True)
            path.chmod(0o600)
        self._lock = Lock()
        if create_if_missing:
            self._initialize_or_validate()
        else:
            self._validate_existing_readonly()

    @classmethod
    def open_existing(cls, database_path: str | Path) -> ProviderIntentStore:
        """Open and validate an existing store without creating or chmodding it."""

        store = cls(database_path, create_if_missing=False)
        store.validate_all()
        return store

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

    def _connect_readonly(self) -> sqlite3.Connection:
        try:
            connection = sqlite3.connect(
                f"file:{Path(self.database_path).resolve()}?mode=ro",
                uri=True,
                timeout=5,
                isolation_level=None,
                check_same_thread=False,
            )
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA busy_timeout=5000")
            connection.execute("PRAGMA foreign_keys=ON")
            connection.execute("PRAGMA query_only=ON")
            return connection
        except sqlite3.DatabaseError as error:
            raise ProviderIntentStoreCorruptionError(
                "provider intent database cannot be opened for reading"
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

    def _validate_existing_readonly(self) -> None:
        with self._connect_readonly() as connection:
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
                    raise ProviderIntentStoreSchemaError(
                        "provider intent database schema is absent"
                    )
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
                (PROVIDER_INTENT_STORE_SCHEMA_VERSION,),
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
            connection.execute(
                """
                CREATE TABLE provider_intent_active_coordinates (
                    coordinate_key TEXT PRIMARY KEY,
                    provider_id TEXT NOT NULL,
                    resource_type TEXT NOT NULL,
                    resource_id TEXT NOT NULL,
                    intent_kind TEXT NOT NULL,
                    intent_id TEXT NOT NULL UNIQUE,
                    management_fingerprint TEXT NOT NULL,
                    record_version INTEGER NOT NULL,
                    UNIQUE (provider_id, resource_type, resource_id, intent_kind),
                    FOREIGN KEY (intent_id, record_version)
                        REFERENCES provider_intent_records
                            (intent_id, record_version)
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE provider_intent_operations (
                    request_id TEXT PRIMARY KEY,
                    request_digest TEXT NOT NULL,
                    operator_id TEXT NOT NULL,
                    result_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE provider_intent_operation_audit (
                    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_id TEXT NOT NULL UNIQUE,
                    occurred_at TEXT NOT NULL,
                    operation_id TEXT NOT NULL,
                    request_id TEXT NOT NULL,
                    operator_id TEXT NOT NULL,
                    intent_id TEXT NOT NULL,
                    record_version INTEGER NOT NULL,
                    event TEXT NOT NULL,
                    lifecycle TEXT NOT NULL,
                    resulting_value TEXT NOT NULL,
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
        if "provider_intent_store_meta" not in tables:
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
        if rows[0]["schema_version"] != PROVIDER_INTENT_STORE_SCHEMA_VERSION:
            if rows[0]["schema_version"] == 1:
                raise ProviderIntentStoreSchemaError(
                    "provider intent store schema migration is required"
                )
            raise ProviderIntentStoreSchemaError(
                "provider intent store schema version is unsupported"
            )
        if tables != set(_TABLE_COLUMNS):
            raise ProviderIntentStoreSchemaError(
                "provider intent database table set is invalid"
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
            "provider_intent_active_coordinates": {
                ("coordinate_key",),
                ("intent_id",),
                ("provider_id", "resource_type", "resource_id", "intent_kind"),
            },
            "provider_intent_operations": {("request_id",)},
            "provider_intent_operation_audit": {
                ("event_id",),
                ("intent_id", "record_version"),
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
        expected_record_foreign_key = (
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
        )
        for table in (
            "provider_intent_audit",
            "provider_intent_active_coordinates",
            "provider_intent_operation_audit",
        ):
            foreign_keys = tuple(
                (
                    row["id"], row["seq"], row["table"], row["from"],
                    row["to"], row["on_update"], row["on_delete"], row["match"],
                )
                for row in connection.execute(
                    f"PRAGMA foreign_key_list({table})"
                ).fetchall()
            )
            if foreign_keys != expected_record_foreign_key:
                raise ProviderIntentStoreSchemaError(
                    f"provider intent table '{table}' foreign keys are invalid"
                )

    @staticmethod
    def _coordinate_key(
        provider_id: str,
        resource_type: str,
        resource_id: str,
        intent_kind: ProviderIntentKind,
    ) -> str:
        encoded = json.dumps(
            {
                "intent_kind": intent_kind.value,
                "provider_id": provider_id,
                "resource_id": resource_id,
                "resource_type": resource_type,
                "version": "provider-intent-coordinate-v1",
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
        return f"provider-intent-coordinate-v1:{hashlib.sha256(encoded).hexdigest()}"

    @classmethod
    def _insert_active_coordinate(
        cls,
        connection: sqlite3.Connection,
        record: ProviderIntentRecord,
    ) -> None:
        assert record.resource_type is not None
        assert record.incarnation_fingerprint is not None
        try:
            connection.execute(
                "INSERT INTO provider_intent_active_coordinates "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    cls._coordinate_key(
                        record.provider_id,
                        record.resource_type,
                        record.resource_id,
                        record.intent_kind,
                    ),
                    record.provider_id,
                    record.resource_type,
                    record.resource_id,
                    record.intent_kind.value,
                    record.intent_id,
                    record.incarnation_fingerprint,
                    record.record_version,
                ),
            )
        except sqlite3.IntegrityError as error:
            raise ProviderIntentStoreConflictError(
                "provider intent coordinate already has an active incarnation"
            ) from error

    @staticmethod
    def _update_active_coordinate(
        connection: sqlite3.Connection,
        record: ProviderIntentRecord,
    ) -> None:
        cursor = connection.execute(
            "UPDATE provider_intent_active_coordinates "
            "SET record_version=? WHERE intent_id=?",
            (record.record_version, record.intent_id),
        )
        if cursor.rowcount != 1:
            raise ProviderIntentStoreCorruptionError(
                "provider intent active coordinate evidence is missing"
            )

    @staticmethod
    def _delete_active_coordinate(
        connection: sqlite3.Connection,
        intent_id: str,
    ) -> None:
        cursor = connection.execute(
            "DELETE FROM provider_intent_active_coordinates WHERE intent_id=?",
            (intent_id,),
        )
        if cursor.rowcount != 1:
            raise ProviderIntentStoreCorruptionError(
                "provider intent active coordinate evidence is missing"
            )

    @staticmethod
    def _failure(
        injector: Callable[[str], None] | None,
        stage: str,
    ) -> None:
        if injector is not None:
            injector(stage)

    def mutate_coordinate(
        self,
        command: ProviderIntentCoordinateMutationCommand,
        *,
        now: datetime | None = None,
        failure_injector: Callable[[str], None] | None = None,
    ) -> ProviderIntentCoordinateMutationResult:
        """Atomically create, update, or rebind one supported coordinate."""

        occurred_at = self._canonical_now(now)
        with self._lock, self._connect() as connection:
            try:
                observed_active = connection.execute(
                    "SELECT intent_id, record_version FROM "
                    "provider_intent_active_coordinates WHERE coordinate_key=?",
                    (
                        self._coordinate_key(
                            command.provider_id,
                            command.resource_type,
                            command.resource_id,
                            command.intent_kind,
                        ),
                    ),
                ).fetchone()
                observed_generation = (
                    None
                    if observed_active is None
                    else (observed_active["intent_id"], observed_active["record_version"])
                )
                self._failure(failure_injector, "after_active_state_observation")
                connection.execute("BEGIN IMMEDIATE")
                replay = self._replay_coordinate_operation(connection, command)
                if replay is not None:
                    connection.commit()
                    return replay

                histories = self._validated_store_records(connection)
                active = tuple(
                    history[-1]
                    for history in histories
                    if history
                    and history[-1].lifecycle is ProviderIntentLifecycle.ACTIVE
                    and history[-1].provider_id == command.provider_id
                    and history[-1].resource_type == command.resource_type
                    and history[-1].resource_id == command.resource_id
                    and history[-1].intent_kind is command.intent_kind
                )
                if len(active) > 1:
                    raise ProviderIntentStoreCorruptionError(
                        "provider intent coordinate has multiple active incarnations"
                    )
                current_generation = (
                    None
                    if not active
                    else (active[0].intent_id, active[0].record_version)
                )
                if current_generation != observed_generation:
                    raise ProviderIntentStoreConflictError(
                        "provider intent coordinate changed concurrently"
                    )
                self._failure(failure_injector, "after_active_state_validation")

                previous = active[0] if active else None
                target_history = self._validated_history(
                    connection,
                    command.intent_id,
                )
                audit_records: list[
                    tuple[ProviderIntentRecord, ProviderIntentAuditEventKind]
                ] = []

                if previous is None:
                    if command.expected_record_version != 0:
                        raise ProviderIntentStoreConflictError(
                            "provider intent expected version does not exist"
                        )
                    if target_history:
                        raise ProviderIntentStoreConflictError(
                            "superseded provider intent incarnation cannot be reactivated"
                        )
                    record = self._new_coordinate_record(command, occurred_at)
                    self._persist_internal_record(
                        connection,
                        record,
                        request_id=command.request_id,
                        request_digest=command.request_digest,
                        event=ProviderIntentAuditEventKind.CREATED,
                        occurred_at=occurred_at,
                    )
                    self._insert_active_coordinate(connection, record)
                    self._failure(failure_injector, "after_new_record_append")
                    audit_records.append((record, ProviderIntentAuditEventKind.CREATED))
                    outcome = "created"
                elif previous.intent_id == command.intent_id:
                    if previous.record_version != command.expected_record_version:
                        raise ProviderIntentStoreConflictError(
                            "provider intent expected version is stale"
                        )
                    record = previous.model_copy(
                        update={
                            "record_version": previous.record_version + 1,
                            "intent_value": command.desired_value,
                            "updated_at": occurred_at,
                            "previous_record_version": previous.record_version,
                        }
                    )
                    record = ProviderIntentRecord.model_validate(record.model_dump())
                    self._persist_internal_record(
                        connection,
                        record,
                        request_id=command.request_id,
                        request_digest=command.request_digest,
                        event=ProviderIntentAuditEventKind.UPDATED,
                        occurred_at=occurred_at,
                    )
                    self._update_active_coordinate(connection, record)
                    self._failure(failure_injector, "after_new_record_append")
                    audit_records.append((record, ProviderIntentAuditEventKind.UPDATED))
                    outcome = "updated"
                else:
                    if command.expected_record_version != 0:
                        raise ProviderIntentStoreConflictError(
                            "replacement binding requires expected version zero"
                        )
                    if target_history:
                        raise ProviderIntentStoreConflictError(
                            "replacement incarnation already has stored history"
                        )
                    superseded = previous.model_copy(
                        update={
                            "record_version": previous.record_version + 1,
                            "lifecycle": ProviderIntentLifecycle.SUPERSEDED,
                            "updated_at": occurred_at,
                            "previous_record_version": previous.record_version,
                        }
                    )
                    superseded = ProviderIntentRecord.model_validate(
                        superseded.model_dump()
                    )
                    self._persist_internal_record(
                        connection,
                        superseded,
                        request_id=f"{command.request_id}-supersede",
                        request_digest=command.request_digest,
                        event=ProviderIntentAuditEventKind.SUPERSEDED,
                        occurred_at=occurred_at,
                    )
                    self._failure(failure_injector, "after_old_superseded_record_append")
                    record = self._new_coordinate_record(command, occurred_at)
                    self._persist_internal_record(
                        connection,
                        record,
                        request_id=f"{command.request_id}-activate",
                        request_digest=command.request_digest,
                        event=ProviderIntentAuditEventKind.CREATED,
                        occurred_at=occurred_at,
                    )
                    self._delete_active_coordinate(connection, previous.intent_id)
                    self._insert_active_coordinate(connection, record)
                    self._failure(failure_injector, "after_new_record_append")
                    audit_records.extend(
                        (
                            (superseded, ProviderIntentAuditEventKind.SUPERSEDED),
                            (record, ProviderIntentAuditEventKind.REBOUND),
                        )
                    )
                    outcome = "rebound"

                result = ProviderIntentCoordinateMutationResult(
                    outcome=outcome,
                    request_id=command.request_id,
                    provider_id=command.provider_id,
                    resource_type=command.resource_type,
                    resource_id=command.resource_id,
                    management_fingerprint=command.management_fingerprint,
                    expectation=command.desired_value,
                    record_version=record.record_version,
                    superseded_previous_incarnation=outcome == "rebound",
                )
                for index, (audit_record, event) in enumerate(audit_records, 1):
                    self._persist_domain_audit(
                        connection,
                        command=command,
                        record=audit_record,
                        event=event,
                        occurred_at=occurred_at,
                    )
                    self._failure(failure_injector, f"after_audit_event_{index}")
                self._failure(failure_injector, "before_idempotency_result")
                connection.execute(
                    "INSERT INTO provider_intent_operations VALUES (?, ?, ?, ?, ?)",
                    (
                        command.request_id,
                        command.request_digest,
                        command.operator_id,
                        result.model_dump_json(),
                        occurred_at.isoformat(),
                    ),
                )
                self._failure(
                    failure_injector,
                    "after_idempotency_result_before_commit",
                )
                connection.commit()
                return result
            except ProviderIntentStoreError:
                connection.rollback()
                raise
            except (sqlite3.DatabaseError, ValidationError, ValueError) as error:
                connection.rollback()
                raise ProviderIntentStoreCorruptionError(
                    "provider intent coordinate mutation failed closed"
                ) from error

    @staticmethod
    def _new_coordinate_record(
        command: ProviderIntentCoordinateMutationCommand,
        occurred_at: datetime,
    ) -> ProviderIntentRecord:
        return ProviderIntentRecord(
            intent_id=command.intent_id,
            record_version=1,
            provider_id=command.provider_id,
            resource_type=command.resource_type,
            resource_id=command.resource_id,
            incarnation_fingerprint=command.management_fingerprint,
            intent_kind=command.intent_kind,
            intent_value=command.desired_value,
            lifecycle=ProviderIntentLifecycle.ACTIVE,
            provenance=ProviderIntentProvenance.OPERATOR,
            created_at=occurred_at,
            updated_at=occurred_at,
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
                if outcome == "created":
                    self._insert_active_coordinate(connection, record)
                else:
                    self._update_active_coordinate(connection, record)
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
                self._delete_active_coordinate(connection, record.intent_id)
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

    def validate_all(self) -> None:
        """Validate every durable series and all request evidence."""

        with self._connect_readonly() as connection:
            try:
                connection.execute("BEGIN")
                self._validated_store_records(connection)
                connection.commit()
            except ProviderIntentStoreError:
                connection.rollback()
                raise
            except (sqlite3.DatabaseError, ValidationError, ValueError, json.JSONDecodeError) as error:
                connection.rollback()
                raise ProviderIntentStoreCorruptionError(
                    "provider intent full-store validation failed"
                ) from error

    def read_snapshot(self) -> ProviderIntentReadSnapshot:
        """Read one fresh coherent generation; no snapshot is retained or cached."""

        with self._connect_readonly() as connection:
            try:
                connection.execute("BEGIN")
                histories = self._validated_store_records(connection)
                current = tuple(history[-1] for history in histories if history)
                identity_bound = tuple(
                    sorted(
                        (
                            record
                            for record in current
                            if record.resource_type is not None
                            and record.incarnation_fingerprint is not None
                        ),
                        key=self._record_order,
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
                        key=self._history_record_order,
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
            except ProviderIntentStoreError:
                connection.rollback()
                raise
            except (sqlite3.DatabaseError, ValidationError, ValueError, json.JSONDecodeError) as error:
                connection.rollback()
                raise ProviderIntentStoreCorruptionError(
                    "provider intent read snapshot validation failed"
                ) from error

    def current_identity_bound_records(self) -> tuple[ProviderIntentRecord, ...]:
        return self.read_snapshot().current_identity_bound_records

    def active_identity_bound_records(self) -> tuple[ProviderIntentRecord, ...]:
        return self.read_snapshot().active_identity_bound_records

    def get_identity_bound_current(
        self,
        *,
        provider_id: str,
        resource_type: str,
        resource_id: str,
        incarnation_fingerprint: str,
        intent_kind: ProviderIntentKind,
    ) -> ProviderIntentRecord | None:
        return next(
            (
                record
                for record in self.read_snapshot().current_identity_bound_records
                if record.provider_id == provider_id
                and record.resource_type == resource_type
                and record.resource_id == resource_id
                and record.incarnation_fingerprint == incarnation_fingerprint
                and record.intent_kind is intent_kind
            ),
            None,
        )

    def identity_bound_records_for_coordinate(
        self,
        *,
        provider_id: str,
        resource_type: str,
        resource_id: str,
    ) -> tuple[ProviderIntentRecord, ...]:
        return tuple(
            record
            for record in self.read_snapshot().current_identity_bound_records
            if (
                record.provider_id == provider_id
                and record.resource_type == resource_type
                and record.resource_id == resource_id
            )
        )

    def legacy_unbound_history(
        self,
        *,
        provider_id: str,
        resource_id: str,
    ) -> tuple[ProviderIntentRecord, ...]:
        return tuple(
            record
            for record in self.read_snapshot().legacy_unbound_records
            if record.provider_id == provider_id
            and record.resource_id == resource_id
            and record.intent_kind is ProviderIntentKind.MONITORING_EXPECTATION
        )

    def get_import_completion(
        self,
        command: LegacyPolicyImportCommand,
    ) -> LegacyPolicyImportResult | None:
        from app.provider_intents.legacy_import import LegacyPolicyImportResult

        with self._connect_readonly() as connection:
            try:
                connection.execute("BEGIN")
                self._validated_store_records(connection)
                marker = connection.execute(
                    "SELECT request_digest, result_json FROM provider_intent_requests "
                    "WHERE request_id=?",
                    (command.import_id,),
                ).fetchone()
                if marker is None:
                    connection.commit()
                    return None
                if marker["request_digest"] != command.import_digest:
                    raise ProviderIntentStoreConflictError(
                        "legacy import ID has a different digest"
                    )
                result = LegacyPolicyImportResult.model_validate_json(
                    marker["result_json"]
                )
                self._validate_legacy_import_replay(connection, command, result)
                connection.commit()
                return result
            except ProviderIntentStoreError:
                connection.rollback()
                raise
            except (sqlite3.DatabaseError, ValidationError, ValueError, json.JSONDecodeError) as error:
                connection.rollback()
                raise ProviderIntentStoreCorruptionError(
                    "legacy import completion evidence is invalid"
                ) from error

    @classmethod
    def _validated_store_records(
        cls,
        connection: sqlite3.Connection,
    ) -> tuple[tuple[ProviderIntentRecord, ...], ...]:
        """Validate all related evidence within the caller's read transaction."""

        from app.provider_intents.legacy_import import LegacyPolicyImportResult

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
        cls._validate_schema(connection, tables)
        intent_ids = tuple(
            row["intent_id"]
            for row in connection.execute(
                "SELECT DISTINCT intent_id FROM provider_intent_records "
                "ORDER BY intent_id"
            ).fetchall()
        )
        histories = tuple(
            cls._validated_history(connection, intent_id) for intent_id in intent_ids
        )
        if any(
            record.lifecycle is ProviderIntentLifecycle.ACTIVE
            and (
                record.provider_id != "proxmox"
                or record.resource_type != "qemu"
                or record.intent_kind
                is not ProviderIntentKind.MONITORING_EXPECTATION
            )
            for history in histories
            for record in history
        ):
            raise ProviderIntentStoreCorruptionError(
                "unsupported active provider intent is stored"
            )
        audit_request_ids = {
            row["request_id"]
            for row in connection.execute(
                "SELECT request_id FROM provider_intent_audit"
            ).fetchall()
        }
        audit_intent_ids = {
            row["intent_id"]
            for row in connection.execute(
                "SELECT DISTINCT intent_id FROM provider_intent_audit"
            ).fetchall()
        }
        if audit_intent_ids != set(intent_ids):
            raise ProviderIntentStoreCorruptionError(
                "provider intent audit series set is inconsistent"
            )
        for row in connection.execute(
            "SELECT request_id, request_digest, result_json "
            "FROM provider_intent_requests ORDER BY request_id"
        ).fetchall():
            if row["request_id"] in audit_request_ids:
                continue
            result = LegacyPolicyImportResult.model_validate_json(row["result_json"])
            if (
                result.import_id != row["request_id"]
                or _LEGACY_IMPORT_REQUEST_DIGEST.fullmatch(row["request_digest"])
                is None
            ):
                raise ProviderIntentStoreCorruptionError(
                    "provider intent request evidence is orphaned"
                )
        cls._validate_p3_evidence(connection, histories)
        return histories

    @classmethod
    def _validate_p3_evidence(
        cls,
        connection: sqlite3.Connection,
        histories: tuple[tuple[ProviderIntentRecord, ...], ...],
    ) -> None:
        active = tuple(
            history[-1]
            for history in histories
            if history
            and history[-1].lifecycle is ProviderIntentLifecycle.ACTIVE
            and history[-1].resource_type is not None
            and history[-1].incarnation_fingerprint is not None
        )
        coordinates = [
            (
                record.provider_id,
                record.resource_type,
                record.resource_id,
                record.intent_kind.value,
            )
            for record in active
        ]
        if len(coordinates) != len(set(coordinates)):
            raise ProviderIntentStoreCorruptionError(
                "provider intent coordinate has multiple active incarnations"
            )
        expected_active = {
            (
                cls._coordinate_key(
                    record.provider_id,
                    record.resource_type or "",
                    record.resource_id,
                    record.intent_kind,
                ),
                record.provider_id,
                record.resource_type,
                record.resource_id,
                record.intent_kind.value,
                record.intent_id,
                record.incarnation_fingerprint,
                record.record_version,
            )
            for record in active
        }
        stored_active = {
            tuple(row)
            for row in connection.execute(
                "SELECT * FROM provider_intent_active_coordinates"
            ).fetchall()
        }
        if stored_active != expected_active:
            raise ProviderIntentStoreCorruptionError(
                "provider intent active coordinate evidence is inconsistent"
            )

        operation_ids = {
            row["request_id"]
            for row in connection.execute(
                "SELECT request_id FROM provider_intent_operations"
            ).fetchall()
        }
        audit_operation_ids = {
            row["request_id"]
            for row in connection.execute(
                "SELECT DISTINCT request_id "
                "FROM provider_intent_operation_audit"
            ).fetchall()
        }
        if operation_ids != audit_operation_ids:
            raise ProviderIntentStoreCorruptionError(
                "provider intent operation audit set is inconsistent"
            )
        for operation in connection.execute(
            "SELECT * FROM provider_intent_operations ORDER BY request_id"
        ).fetchall():
            result = ProviderIntentCoordinateMutationResult.model_validate_json(
                operation["result_json"]
            )
            if (
                result.request_id != operation["request_id"]
                or _COORDINATE_MUTATION_DIGEST.fullmatch(
                    operation["request_digest"]
                )
                is None
            ):
                raise ProviderIntentStoreCorruptionError(
                    "provider intent operation result identity is inconsistent"
                )
            rows = connection.execute(
                "SELECT * FROM provider_intent_operation_audit "
                "WHERE request_id=? ORDER BY sequence",
                (operation["request_id"],),
            ).fetchall()
            expected_events = (
                (
                    ProviderIntentAuditEventKind.SUPERSEDED,
                    ProviderIntentAuditEventKind.REBOUND,
                )
                if result.outcome == "rebound"
                else (
                    ProviderIntentAuditEventKind.CREATED
                    if result.outcome == "created"
                    else ProviderIntentAuditEventKind.UPDATED,
                )
            )
            if len(rows) != len(expected_events):
                raise ProviderIntentStoreCorruptionError(
                    "provider intent operation audit count is inconsistent"
                )
            for row, expected_event in zip(rows, expected_events, strict=True):
                event = ProviderIntentDomainAuditEvent(
                    sequence=row["sequence"],
                    event_id=row["event_id"],
                    occurred_at=datetime.fromisoformat(row["occurred_at"]),
                    operation_id=row["operation_id"],
                    request_id=row["request_id"],
                    operator_id=row["operator_id"],
                    intent_id=row["intent_id"],
                    record_version=row["record_version"],
                    event=ProviderIntentAuditEventKind(row["event"]),
                    lifecycle=ProviderIntentLifecycle(row["lifecycle"]),
                    resulting_value=ProviderIntentValue(row["resulting_value"]),
                )
                record_row = connection.execute(
                    "SELECT * FROM provider_intent_records "
                    "WHERE intent_id=? AND record_version=?",
                    (event.intent_id, event.record_version),
                ).fetchone()
                if (
                    event.event is not expected_event
                    or event.event_id
                    != cls._audit_event_id(
                        event.request_id,
                        event.intent_id,
                        event.record_version,
                        event.event,
                    )
                    or event.operation_id != operation["request_id"]
                    or event.request_id != operation["request_id"]
                    or event.operator_id != operation["operator_id"]
                    or record_row is None
                ):
                    raise ProviderIntentStoreCorruptionError(
                        "provider intent operation audit evidence is invalid"
                    )
                record = cls._decode_record(record_row)
                if (
                    event.lifecycle is not record.lifecycle
                    or event.resulting_value is not record.intent_value
                ):
                    raise ProviderIntentStoreCorruptionError(
                        "provider intent operation audit result is inconsistent"
                    )
            result_record_row = connection.execute(
                    "SELECT * FROM provider_intent_records WHERE intent_id=? "
                    "AND record_version=?",
                    (
                        build_provider_intent_id(
                            provider_id=result.provider_id,
                            resource_type=result.resource_type,
                            resource_id=result.resource_id,
                            incarnation_fingerprint=result.management_fingerprint,
                            intent_kind=ProviderIntentKind.MONITORING_EXPECTATION,
                        ),
                        result.record_version,
                    ),
                ).fetchone()
            if result_record_row is None:
                raise ProviderIntentStoreCorruptionError(
                    "provider intent operation result record is missing"
                )
            result_record = cls._decode_record(result_record_row)
            if result_record.intent_value is not result.expectation:
                raise ProviderIntentStoreCorruptionError(
                    "provider intent operation result record is inconsistent"
                )

    @staticmethod
    def _record_order(record: ProviderIntentRecord) -> tuple[str, ...]:
        return (
            record.provider_id,
            record.resource_type or "",
            record.resource_id,
            record.incarnation_fingerprint or "",
            record.intent_kind.value,
            record.intent_id,
        )

    @staticmethod
    def _history_record_order(record: ProviderIntentRecord) -> tuple[str, ...]:
        return (
            *ProviderIntentStore._record_order(record),
            f"{record.record_version:020d}",
        )

    def get_current(self, intent_id: str) -> ProviderIntentRecord | None:
        with self._connect_readonly() as connection:
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
        with self._connect_readonly() as connection:
            try:
                return self._validated_history(connection, intent_id)
            except ProviderIntentStoreError:
                raise
            except (sqlite3.DatabaseError, ValidationError, ValueError, json.JSONDecodeError) as error:
                raise ProviderIntentStoreCorruptionError(
                    "provider intent history is invalid"
                ) from error

    def audit(self, intent_id: str) -> tuple[ProviderIntentAuditEvent, ...]:
        with self._connect_readonly() as connection:
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

    def operation_audit(
        self,
        request_id: str | None = None,
    ) -> tuple[ProviderIntentDomainAuditEvent, ...]:
        with self._connect_readonly() as connection:
            try:
                self._validated_store_records(connection)
                query = "SELECT * FROM provider_intent_operation_audit"
                values: tuple[str, ...] = ()
                if request_id is not None:
                    query += " WHERE request_id=?"
                    values = (request_id,)
                query += " ORDER BY sequence"
                rows = connection.execute(query, values).fetchall()
                return tuple(
                    ProviderIntentDomainAuditEvent(
                        sequence=row["sequence"],
                        event_id=row["event_id"],
                        occurred_at=datetime.fromisoformat(row["occurred_at"]),
                        operation_id=row["operation_id"],
                        request_id=row["request_id"],
                        operator_id=row["operator_id"],
                        intent_id=row["intent_id"],
                        record_version=row["record_version"],
                        event=ProviderIntentAuditEventKind(row["event"]),
                        lifecycle=ProviderIntentLifecycle(row["lifecycle"]),
                        resulting_value=ProviderIntentValue(row["resulting_value"]),
                    )
                    for row in rows
                )
            except (sqlite3.DatabaseError, ValidationError, ValueError) as error:
                raise ProviderIntentStoreCorruptionError(
                    "provider intent operation audit history is invalid"
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
    def _replay_coordinate_operation(
        connection: sqlite3.Connection,
        command: ProviderIntentCoordinateMutationCommand,
    ) -> ProviderIntentCoordinateMutationResult | None:
        row = connection.execute(
            "SELECT request_digest, operator_id, result_json "
            "FROM provider_intent_operations WHERE request_id=?",
            (command.request_id,),
        ).fetchone()
        if row is None:
            return None
        if (
            row["request_digest"] != command.request_digest
            or row["operator_id"] != command.operator_id
        ):
            raise ProviderIntentStoreConflictError(
                "provider intent mutation request ID has different input"
            )
        result = ProviderIntentCoordinateMutationResult.model_validate_json(
            row["result_json"]
        )
        audits = connection.execute(
            "SELECT * FROM provider_intent_operation_audit "
            "WHERE request_id=? ORDER BY sequence",
            (command.request_id,),
        ).fetchall()
        expected_count = 2 if result.outcome == "rebound" else 1
        if len(audits) != expected_count or any(
            audit["operator_id"] != command.operator_id for audit in audits
        ):
            raise ProviderIntentStoreCorruptionError(
                "provider intent operation replay evidence is inconsistent"
            )
        return result

    @staticmethod
    def _audit_event_id(
        request_id: str,
        intent_id: str,
        record_version: int,
        event: ProviderIntentAuditEventKind,
    ) -> str:
        encoded = json.dumps(
            {
                "event": event.value,
                "intent_id": intent_id,
                "record_version": record_version,
                "request_id": request_id,
                "version": "provider-intent-audit-v1",
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
        return f"provider-intent-audit-v1:{hashlib.sha256(encoded).hexdigest()}"

    @classmethod
    def _persist_domain_audit(
        cls,
        connection: sqlite3.Connection,
        *,
        command: ProviderIntentCoordinateMutationCommand,
        record: ProviderIntentRecord,
        event: ProviderIntentAuditEventKind,
        occurred_at: datetime,
    ) -> None:
        connection.execute(
            "INSERT INTO provider_intent_operation_audit "
            "(event_id, occurred_at, operation_id, request_id, operator_id, "
            "intent_id, record_version, event, lifecycle, resulting_value) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                cls._audit_event_id(
                    command.request_id,
                    record.intent_id,
                    record.record_version,
                    event,
                ),
                occurred_at.isoformat(),
                command.request_id,
                command.request_id,
                command.operator_id,
                record.intent_id,
                record.record_version,
                event.value,
                record.lifecycle.value,
                record.intent_value.value,
            ),
        )

    @classmethod
    def _persist_internal_record(
        cls,
        connection: sqlite3.Connection,
        record: ProviderIntentRecord,
        *,
        request_id: str,
        request_digest: str,
        event: ProviderIntentAuditEventKind,
        occurred_at: datetime,
    ) -> None:
        result = ProviderIntentMutationResult(
            outcome=(
                "superseded"
                if event is ProviderIntentAuditEventKind.SUPERSEDED
                else "updated"
                if event is ProviderIntentAuditEventKind.UPDATED
                else "created"
            ),
            record=record,
        )
        cls._persist_mutation(
            connection,
            record=record,
            result=result,
            request_id=request_id,
            request_digest=request_digest,
            event=(
                ProviderIntentAuditEventKind.CREATED
                if event is ProviderIntentAuditEventKind.REBOUND
                else event
            ),
            occurred_at=occurred_at,
        )

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
