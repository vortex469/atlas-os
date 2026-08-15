#!/usr/bin/env python3

import argparse
import hashlib
import json
import os
import re
import shutil
import sqlite3
import stat
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path, PurePosixPath

try:
    from atlas_data_backup_models import (
        BACKUP_DIRECTORY_MODE,
        LEGACY_V1_REQUIRED_DATABASES,
        MANAGED_PATH_ORDER,
        PRIVATE_FILE_MODE,
        V3_FORMAT_VERSION,
        ArtifactMetadata,
        AtlasCoreBackupV3Manifest,
        ContentKind,
        InventoryDisposition,
        ManagedPath,
        ProviderIntentActivation,
        build_v3_manifest,
        classify_backup_format,
        classify_legacy_inventory,
    )
except ModuleNotFoundError:  # Imported as scripts.atlas_data_tool in tests.
    from scripts.atlas_data_backup_models import (
        BACKUP_DIRECTORY_MODE,
        LEGACY_V1_REQUIRED_DATABASES,
        MANAGED_PATH_ORDER,
        PRIVATE_FILE_MODE,
        V3_FORMAT_VERSION,
        ArtifactMetadata,
        AtlasCoreBackupV3Manifest,
        ContentKind,
        InventoryDisposition,
        ManagedPath,
        ProviderIntentActivation,
        build_v3_manifest,
        classify_backup_format,
        classify_legacy_inventory,
    )

DATABASES = tuple(sorted(LEGACY_V1_REQUIRED_DATABASES))
RUNTIME_FILES = (
    "config/policies.yaml",
    "config/provider-connections.yaml",
    "secrets/provider-connections.yaml",
)
SECRET_RUNTIME_FILES = {"secrets/provider-connections.yaml"}
MANIFEST_NAME = "manifest.json"
FORMAT_VERSION = V3_FORMAT_VERSION
SUPPORTED_FORMAT_VERSIONS = {1, 2, FORMAT_VERSION}
BACKUP_NAME_PATTERN = re.compile(
    r"^atlas-data-(?P<timestamp>\d{8}T\d{6}Z)$"
)


class UniqueStoreAction(argparse.Action):
    """Store one explicit option value and reject duplicate occurrences."""

    def __call__(
        self,
        parser: argparse.ArgumentParser,
        namespace: argparse.Namespace,
        values: object,
        option_string: str | None = None,
    ) -> None:
        marker = f"_{self.dest}_explicit"
        if getattr(namespace, marker, False):
            parser.error(f"{option_string} may be specified only once")
        setattr(namespace, marker, True)
        setattr(namespace, self.dest, values)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def safe_relative_path(value: object) -> Path:
    if not isinstance(value, str) or not value:
        raise RuntimeError("runtime file path is invalid")

    relative = PurePosixPath(value)
    if relative.is_absolute() or ".." in relative.parts:
        raise RuntimeError(f"unsafe runtime file path: {value}")
    if any(part in {"", "."} for part in relative.parts):
        raise RuntimeError(f"unsafe runtime file path: {value}")

    return Path(*relative.parts)


def integrity(path: Path) -> str:
    connection = sqlite3.connect(
        f"file:{path}?mode=ro&immutable=1",
        uri=True,
    )
    try:
        return str(connection.execute("PRAGMA integrity_check").fetchone()[0])
    finally:
        connection.close()


def sqlite_backup(source: Path, destination: Path) -> None:
    source_connection = sqlite3.connect(
        f"file:{source}?mode=ro",
        uri=True,
    )
    destination_connection = sqlite3.connect(destination)
    try:
        source_connection.backup(destination_connection)
        destination_connection.execute("PRAGMA journal_mode=DELETE")
    finally:
        destination_connection.close()
        source_connection.close()


def create_backup(
    source: Path,
    destination: Path,
    *,
    operator_auth_initialized: bool,
    provider_intent_activation: ProviderIntentActivation = ProviderIntentActivation.NOT_ACTIVATED,
    expected_legacy_import_id: str | None = None,
) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    os.chmod(destination, BACKUP_DIRECTORY_MODE)
    if any(destination.iterdir()):
        raise RuntimeError(f"backup destination is not empty: {destination}")
    if not isinstance(operator_auth_initialized, bool):
        raise TypeError("operator auth initialization must be explicit")
    audit_source = source / ManagedPath.OPERATOR_SECURITY_AUDIT.value
    provider_intent_source = source / ManagedPath.PROVIDER_INTENTS.value
    if not operator_auth_initialized and audit_source.exists():
        raise RuntimeError("unexpected operator security audit database")
    _validate_activation_options(provider_intent_activation, expected_legacy_import_id)
    if provider_intent_activation is ProviderIntentActivation.NOT_ACTIVATED:
        if provider_intent_source.exists():
            raise RuntimeError("unexpected inactive provider intent database")
    elif not provider_intent_source.is_file() or provider_intent_source.is_symlink():
        raise RuntimeError("required provider intent store not found")

    present_paths = list(MANAGED_PATH_ORDER[:7])
    if operator_auth_initialized:
        present_paths.append(ManagedPath.OPERATOR_SECURITY_AUDIT)
    if provider_intent_activation is ProviderIntentActivation.ACTIVATED:
        present_paths.append(ManagedPath.PROVIDER_INTENTS)
    artifacts: dict[ManagedPath, ArtifactMetadata] = {}
    for managed_path in present_paths:
        source_path = source / managed_path.value
        if not source_path.is_file():
            raise RuntimeError(f"required store not found: {source_path}")
        destination_path = destination / managed_path.value
        destination_path.parent.mkdir(parents=True, exist_ok=True)
        if managed_path.value.endswith(".db"):
            if managed_path is not ManagedPath.PROVIDER_INTENTS:
                validate_sqlite_application(source_path, managed_path)
            sqlite_backup(source_path, destination_path)
            if integrity(destination_path) != "ok":
                raise RuntimeError(f"backup integrity check failed for {managed_path.value}")
            validate_sqlite_application(
                destination_path,
                managed_path,
                policy_path=source / ManagedPath.POLICIES.value,
                expected_legacy_import_id=expected_legacy_import_id,
            )
        else:
            validate_runtime_file(
                source_path,
                managed_path.value,
                source_path.stat().st_mode & 0o777,
            )
            shutil.copyfile(source_path, destination_path)
            validate_runtime_file(destination_path, managed_path.value, PRIVATE_FILE_MODE)
        os.chmod(destination_path, PRIVATE_FILE_MODE)
        artifacts[managed_path] = ArtifactMetadata(
            sha256=sha256(destination_path),
            size=destination_path.stat().st_size,
        )

    manifest = build_v3_manifest(
        created_at=datetime.now(timezone.utc),
        artifacts=artifacts,
        operator_security_audit_present=operator_auth_initialized,
        provider_intent_activation=provider_intent_activation,
    ).to_dict()
    manifest_path = destination / MANIFEST_NAME
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    os.chmod(manifest_path, PRIVATE_FILE_MODE)
    verify_backup(destination, expected_legacy_import_id=expected_legacy_import_id)


def apply_owner(path: Path, uid: int, gid: int) -> None:
    if uid < 0 or gid < 0:
        raise RuntimeError("output owner uid and gid must be non-negative")

    for current, directories, filenames in os.walk(path):
        current_path = Path(current)
        os.chown(current_path, uid, gid)
        for name in directories:
            os.chown(current_path / name, uid, gid)
        for name in filenames:
            os.chown(current_path / name, uid, gid)


def verify_backup(
    backup: Path,
    *,
    expected_legacy_import_id: str | None = None,
) -> dict[str, object]:
    manifest_path = backup / MANIFEST_NAME
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(manifest, dict):
        raise RuntimeError("backup manifest must be an object")  # noqa: TRY004
    format_version = manifest.get("format_version")
    if format_version not in SUPPORTED_FORMAT_VERSIONS:
        raise RuntimeError("unsupported backup format version")

    if format_version == V3_FORMAT_VERSION:
        return verify_v3_backup(
            backup,
            manifest,
            expected_legacy_import_id=expected_legacy_import_id,
        )
    if expected_legacy_import_id is not None:
        raise RuntimeError("legacy backups cannot carry Provider Intent activation")

    classify_legacy_inventory(
        format_version=format_version,
        databases=frozenset(
            record.get("filename")
            for record in manifest.get("databases", [])
            if isinstance(record, dict) and isinstance(record.get("filename"), str)
        ),
        runtime_files=frozenset(
            record.get("path")
            for record in manifest.get("files", [])
            if isinstance(record, dict) and isinstance(record.get("path"), str)
        ),
    )

    records = manifest.get("databases")
    if not isinstance(records, list):
        raise RuntimeError("backup manifest has no database records")  # noqa: TRY004

    filenames = {
        record.get("filename")
        for record in records
        if isinstance(record, dict)
    }
    if len(filenames) != len(records):
        raise RuntimeError("backup manifest database records contain duplicates")
    if filenames != set(DATABASES):
        raise RuntimeError("backup manifest database set is invalid")

    file_records = manifest.get("files", [])
    if format_version == 1 and "files" not in manifest:
        file_records = []
    if not isinstance(file_records, list):
        raise RuntimeError("backup manifest file records are invalid")  # noqa: TRY004

    expected_paths = {Path(filename) for filename in DATABASES}
    expected_paths.add(Path(MANIFEST_NAME))
    runtime_paths: set[Path] = set()

    for record in file_records:
        if not isinstance(record, dict):
            raise RuntimeError("backup manifest file record is invalid")  # noqa: TRY004
        relative_path = safe_relative_path(record.get("path"))
        if relative_path.as_posix() not in RUNTIME_FILES:
            raise RuntimeError(f"unexpected runtime file path: {relative_path}")
        if relative_path in runtime_paths:
            raise RuntimeError(f"duplicate runtime file path: {relative_path}")
        validate_runtime_manifest_record(relative_path.as_posix(), record)
        runtime_paths.add(relative_path)
        expected_paths.add(relative_path)

    actual_paths = {
        path.relative_to(backup)
        for path in backup.rglob("*")
        if path.is_file()
    }
    if actual_paths != expected_paths:
        unexpected = sorted(path.as_posix() for path in actual_paths - expected_paths)
        missing = sorted(path.as_posix() for path in expected_paths - actual_paths)
        raise RuntimeError(
            f"backup file set is invalid; unexpected={unexpected}, "
            f"missing={missing}"
        )

    for record in records:
        if not isinstance(record, dict):
            raise RuntimeError("backup manifest record is invalid")  # noqa: TRY004
        filename = record["filename"]
        if filename not in DATABASES:
            raise RuntimeError(f"unexpected database filename: {filename}")
        path = backup / filename
        if not path.is_file():
            raise RuntimeError(f"backup database not found: {filename}")
        if path.stat().st_size != record.get("size"):
            raise RuntimeError(f"backup size mismatch: {filename}")
        if sha256(path) != record.get("sha256"):
            raise RuntimeError(f"backup checksum mismatch: {filename}")
        result = integrity(path)
        if result != "ok":
            raise RuntimeError(
                f"backup integrity check failed for {filename}: {result}"
            )

    for record in file_records:
        relative_path = safe_relative_path(record.get("path"))
        if relative_path not in runtime_paths:
            raise RuntimeError(f"backup runtime file not registered: {relative_path}")
        path = backup / relative_path
        if not path.is_file():
            raise RuntimeError(f"backup runtime file not found: {relative_path}")
        if path.stat().st_size != record.get("size"):
            raise RuntimeError(f"backup runtime file size mismatch: {relative_path}")
        if sha256(path) != record.get("sha256"):
            raise RuntimeError(f"backup runtime file checksum mismatch: {relative_path}")
        mode = record.get("mode")
        validate_runtime_file(
            path,
            relative_path.as_posix(),
            mode if isinstance(mode, int) else 0o600,
        )

    return manifest


def verify_v3_backup(
    backup: Path,
    manifest_data: dict[str, object],
    *,
    expected_legacy_import_id: str | None = None,
) -> dict[str, object]:
    try:
        manifest = AtlasCoreBackupV3Manifest.from_dict(manifest_data)
    except (TypeError, ValueError) as error:
        raise RuntimeError("backup v3 manifest is invalid") from error
    _validate_activation_options(
        manifest.provider_intent_activation,
        expected_legacy_import_id,
    )
    if (
        not backup.is_dir()
        or backup.is_symlink()
        or backup.stat().st_mode & 0o777 != BACKUP_DIRECTORY_MODE
    ):
        raise RuntimeError("backup v3 directory mode is invalid")
    manifest_path = backup / MANIFEST_NAME
    if (
        not manifest_path.is_file()
        or manifest_path.is_symlink()
        or manifest_path.stat().st_mode & 0o777 != PRIVATE_FILE_MODE
    ):
        raise RuntimeError("backup v3 manifest mode is invalid")

    expected_files = {Path(MANIFEST_NAME)}
    for entry in manifest.inventory:
        if entry.disposition is InventoryDisposition.REQUIRED_PRESENT:
            expected_files.add(Path(entry.path.value))
    expected_directories = {
        path.parent for path in expected_files if path.parent != Path(".")
    }
    physical_entries = tuple(backup.rglob("*"))
    if any(path.is_symlink() for path in physical_entries):
        raise RuntimeError("backup v3 cannot contain symbolic links")
    actual_files = {
        path.relative_to(backup) for path in physical_entries if path.is_file()
    }
    actual_directories = {
        path.relative_to(backup) for path in physical_entries if path.is_dir()
    }
    if actual_files != expected_files:
        raise RuntimeError("backup v3 physical file set is invalid")
    if actual_directories != expected_directories:
        raise RuntimeError("backup v3 directory set is invalid")

    for entry in manifest.inventory:
        path = backup / entry.path.value
        if entry.disposition is not InventoryDisposition.REQUIRED_PRESENT:
            if path.exists():
                raise RuntimeError(f"excluded backup artifact exists: {entry.path.value}")
            continue
        assert entry.artifact is not None
        if (
            not path.is_file()
            or path.is_symlink()
            or path.stat().st_mode & 0o777 != entry.mode
        ):
            raise RuntimeError(f"backup artifact mode or type is invalid: {entry.path.value}")
        if path.stat().st_size != entry.artifact.size:
            raise RuntimeError(f"backup size mismatch: {entry.path.value}")
        if sha256(path) != entry.artifact.sha256:
            raise RuntimeError(f"backup checksum mismatch: {entry.path.value}")
        if entry.content_kind is ContentKind.SQLITE:
            if integrity(path) != "ok":
                raise RuntimeError(f"backup integrity check failed: {entry.path.value}")
            validate_sqlite_application(
                path,
                entry.path,
                policy_path=backup / ManagedPath.POLICIES.value,
                expected_legacy_import_id=expected_legacy_import_id,
            )
        else:
            validate_runtime_file(path, entry.path.value, entry.mode)
    classify_backup_format(V3_FORMAT_VERSION)
    return manifest_data


_SQLITE_SCHEMAS: dict[
    ManagedPath,
    tuple[dict[str, tuple[str, ...]], dict[str, tuple[str, ...]]],
] = {
    ManagedPath.ACTION_HISTORY: (
        {
            "provider_action_history": (
                "id", "provider_id", "provider_name", "action_id", "action_label",
                "status", "success", "message", "confirmed", "destructive",
                "parameter_names", "request_id", "started_at", "completed_at",
                "duration_ms",
            )
        },
        {
            "idx_provider_action_history_completed_at": ("completed_at",),
            "idx_provider_action_history_provider_status": (
                "provider_id", "status", "completed_at",
            ),
        },
    ),
    ManagedPath.PROVIDER_INTELLIGENCE: (
        {"intelligence_telemetry": ("id", "collected_at", "telemetry")},
        {"idx_intelligence_telemetry_collected_at": ("collected_at",)},
    ),
    ManagedPath.OPERATIONAL_DISPATCH: (
        {
            "operational_dispatch": (
                "request_id", "request_digest", "state", "request_json", "created_at",
                "updated_at", "dispatch_started_at", "dispatch_result_json",
                "verification_result_json",
            ),
            "operational_dispatch_events": (
                "event_id", "status", "occurred_at", "event_json",
            ),
            "operational_dispatch_transitions": (
                "sequence", "request_id", "request_digest", "previous_state", "state",
                "occurred_at",
            ),
        },
        {
            "idx_operational_dispatch_events_time": ("occurred_at",),
            "idx_operational_dispatch_transitions_request": ("request_id", "sequence"),
        },
    ),
    ManagedPath.OPERATOR_INTENTS: (
        {
            "operator_intents": (
                "record_id", "request_digest", "record_json", "created_at", "expires_at",
                "schema_version",
            ),
            "operator_intent_audit": (
                "sequence", "occurred_at", "record_id", "candidate_id", "operator_id",
                "event", "reason",
            ),
        },
        {},
    ),
    ManagedPath.OPERATOR_SECURITY_AUDIT: (
        {
            "operator_security_audit": (
                "event_id", "occurred_at", "request_id", "operator_id", "auth_method",
                "action", "outcome", "reason",
            )
        },
        {},
    ),
}

_SQLITE_PRIMARY_KEYS: dict[ManagedPath, dict[str, tuple[str, ...]]] = {
    ManagedPath.ACTION_HISTORY: {"provider_action_history": ("id",)},
    ManagedPath.PROVIDER_INTELLIGENCE: {"intelligence_telemetry": ("id",)},
    ManagedPath.OPERATIONAL_DISPATCH: {
        "operational_dispatch": ("request_id",),
        "operational_dispatch_events": ("event_id",),
        "operational_dispatch_transitions": ("sequence",),
    },
    ManagedPath.OPERATOR_INTENTS: {
        "operator_intents": ("record_id",),
        "operator_intent_audit": ("sequence",),
    },
    ManagedPath.OPERATOR_SECURITY_AUDIT: {
        "operator_security_audit": ("event_id",),
    },
}


def _validate_activation_options(
    activation: ProviderIntentActivation,
    expected_legacy_import_id: str | None,
) -> None:
    if not isinstance(activation, ProviderIntentActivation):
        raise TypeError("Provider Intent activation must use its closed enum")
    if activation is ProviderIntentActivation.ACTIVATED:
        if not expected_legacy_import_id:
            raise RuntimeError("activated Provider Intent requires an expected import ID")
    elif expected_legacy_import_id is not None:
        raise RuntimeError("inactive Provider Intent cannot accept an expected import ID")


def _validate_provider_intent_application(
    path: Path,
    policy_path: Path,
    expected_legacy_import_id: str | None,
) -> None:
    resolved = Path(__file__).resolve()
    installed_core_root = Path("/opt/atlas/services/atlas-core")
    if installed_core_root.is_dir() and str(installed_core_root) not in sys.path:
        sys.path.insert(0, str(installed_core_root))
    if len(resolved.parents) > 1:
        core_root = resolved.parents[1] / "services" / "atlas-core"
        if core_root.is_dir() and str(core_root) not in sys.path:
            sys.path.insert(0, str(core_root))
    try:
        from app.provider_intents.legacy_import import (
            load_legacy_policy_import,
            validate_activated_provider_intent_store,
        )

        expected_legacy_import_id = (
            expected_legacy_import_id
            or load_legacy_policy_import(policy_path).import_id
        )

        validate_activated_provider_intent_store(
            path,
            policy_path,
            expected_legacy_import_id,
        )
    except (ImportError, OSError, TypeError, ValueError, RuntimeError) as error:
        raise RuntimeError("provider intent application validation failed") from error


def validate_sqlite_application(
    path: Path,
    managed_path: ManagedPath,
    *,
    policy_path: Path | None = None,
    expected_legacy_import_id: str | None = None,
) -> None:
    if managed_path is ManagedPath.PROVIDER_INTENTS:
        if policy_path is None:
            raise RuntimeError("provider intent validation context is required")
        _validate_provider_intent_application(
            path,
            policy_path,
            expected_legacy_import_id,
        )
        return
    if managed_path not in _SQLITE_SCHEMAS:
        raise RuntimeError(f"no application validator for {managed_path.value}")
    tables, indexes = _SQLITE_SCHEMAS[managed_path]
    connection = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    try:
        actual_tables = {
            row["name"]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
            )
        }
        if actual_tables != set(tables):
            raise RuntimeError(f"application table set is invalid: {managed_path.value}")
        for table, expected_columns in tables.items():
            table_info = connection.execute(f"PRAGMA table_info({table})").fetchall()
            columns = tuple(row["name"] for row in table_info)
            if columns != expected_columns:
                raise RuntimeError(f"application columns are invalid: {managed_path.value}")
            primary_key = tuple(
                row["name"]
                for row in sorted(table_info, key=lambda item: item["pk"])
                if row["pk"]
            )
            if primary_key != _SQLITE_PRIMARY_KEYS[managed_path][table]:
                raise RuntimeError(
                    f"application primary key is invalid: {managed_path.value}"
                )
        for index, expected_columns in indexes.items():
            columns = tuple(
                row["name"]
                for row in connection.execute(f"PRAGMA index_info({index})")
            )
            if columns != expected_columns:
                raise RuntimeError(f"application index is invalid: {managed_path.value}")
        _validate_sqlite_rows(connection, managed_path)
    except sqlite3.DatabaseError as error:
        raise RuntimeError(f"application database is invalid: {managed_path.value}") from error
    finally:
        connection.close()


_LEDGER_TRANSITIONS = {
    (None, "claimed"), ("claimed", "revalidated"),
    ("revalidated", "dispatching"),
    *( (start, end) for start in ("claimed", "revalidated", "dispatching") for end in ("succeeded", "failed", "outcome_unknown", "target_replaced") ),
    ("succeeded", "verifying"), ("outcome_unknown", "verifying"),
    *( ("verifying", end) for end in ("verified", "verification_failed", "outcome_unknown", "target_replaced") ),
}


def _validate_sqlite_rows(connection: sqlite3.Connection, managed_path: ManagedPath) -> None:
    if managed_path is ManagedPath.ACTION_HISTORY:
        for row in connection.execute("SELECT parameter_names FROM provider_action_history"):
            if not isinstance(json.loads(row[0]), list):
                raise RuntimeError("action history parameters are invalid")  # noqa: TRY004
    elif managed_path is ManagedPath.PROVIDER_INTELLIGENCE:
        for row in connection.execute("SELECT telemetry FROM intelligence_telemetry"):
            if not isinstance(json.loads(row[0]), dict):
                raise RuntimeError(  # noqa: TRY004
                    "provider intelligence telemetry is invalid"
                )
    elif managed_path is ManagedPath.OPERATOR_INTENTS:
        for row in connection.execute("SELECT * FROM operator_intents"):
            record = json.loads(row["record_json"])
            if (
                not isinstance(record, dict)
                or record.get("record_id") != row["record_id"]
                or record.get("request_digest") != row["request_digest"]
                or record.get("schema_version") != row["schema_version"]
                or row["schema_version"] != 1
            ):
                raise RuntimeError("operator intent record is inconsistent")
    elif managed_path is ManagedPath.OPERATIONAL_DISPATCH:
        _validate_operational_rows(connection)


def _validate_operational_rows(connection: sqlite3.Connection) -> None:
    orphan_count = connection.execute(
        "SELECT count(*) FROM operational_dispatch_transitions AS transitions "
        "LEFT JOIN operational_dispatch AS requests "
        "ON requests.request_id = transitions.request_id "
        "WHERE requests.request_id IS NULL"
    ).fetchone()[0]
    if orphan_count:
        raise RuntimeError("operational transition history contains an orphan")
    for event_row in connection.execute("SELECT * FROM operational_dispatch_events"):
        event = json.loads(event_row["event_json"])
        if (
            not isinstance(event, dict)
            or event.get("event_id") != event_row["event_id"]
            or event.get("status") != event_row["status"]
            or event.get("occurred_at") != event_row["occurred_at"]
        ):
            raise RuntimeError("operational event evidence is inconsistent")
    for row in connection.execute("SELECT * FROM operational_dispatch"):
        request = json.loads(row["request_json"])
        if (
            not isinstance(request, dict)
            or request.get("request_id") != row["request_id"]
            or request.get("request_digest") != row["request_digest"]
            or not {
                "schema_version", "idempotency_key", "effect_kind",
                "execution_intent", "provider_id", "resource_id", "resource_type",
                "provider_action_id", "target_fingerprint", "verification", "approval",
            }.issubset(request)
        ):
            raise RuntimeError("operational request identity is inconsistent")
        for field in ("dispatch_result_json", "verification_result_json"):
            if row[field] is not None and not isinstance(json.loads(row[field]), dict):
                raise RuntimeError("operational result evidence is invalid")
        dispatch_result = (
            json.loads(row["dispatch_result_json"])
            if row["dispatch_result_json"] is not None
            else None
        )
        verification_result = (
            json.loads(row["verification_result_json"])
            if row["verification_result_json"] is not None
            else None
        )
        if dispatch_result is not None and (
            dispatch_result.get("request_id") != row["request_id"]
            or dispatch_result.get("request_digest") != row["request_digest"]
            or dispatch_result.get("status")
            not in {"succeeded", "failed", "outcome_unknown"}
            or not {"target_fingerprint", "started_at"}.issubset(dispatch_result)
        ):
            raise RuntimeError("operational dispatch result identity is inconsistent")
        if (
            verification_result is not None
            and (
                verification_result.get("request_id") != row["request_id"]
                or verification_result.get("status")
                not in {
                    "succeeded", "verification_failed", "outcome_unknown",
                    "target_replaced",
                }
                or not {"started_at", "completed_at", "deadline"}.issubset(
                    verification_result
                )
            )
        ):
            raise RuntimeError("operational verification identity is inconsistent")
        state = row["state"]
        dispatch_result_states = {
            "succeeded", "failed", "outcome_unknown", "target_replaced",
        }
        final_states = {"verified", "verification_failed", "target_replaced"}
        verification_result_states = {
            "verified", "verification_failed", "target_replaced", "outcome_unknown",
        }
        if state in dispatch_result_states and dispatch_result is None:
            raise RuntimeError("operational dispatch result is missing")
        if state in final_states - {"target_replaced"} and verification_result is None:
            raise RuntimeError("operational verification result is missing")
        if verification_result is not None and state not in verification_result_states:
            raise RuntimeError("operational verification state is inconsistent")
        transitions = connection.execute(
            "SELECT * FROM operational_dispatch_transitions WHERE request_id=? ORDER BY sequence",
            (row["request_id"],),
        ).fetchall()
        previous = None
        for transition in transitions:
            if (
                transition["request_digest"] != row["request_digest"]
                or transition["previous_state"] != previous
                or (previous, transition["state"]) not in _LEDGER_TRANSITIONS
            ):
                raise RuntimeError("operational transition history is invalid")
            previous = transition["state"]
        if not transitions or previous != row["state"]:
            raise RuntimeError("operational current state is inconsistent")


def atomic_restore_file(source: Path, target: Path, mode: int = 0o600) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = target.with_name(f".{target.name}.restore")
    if temporary_path.exists():
        temporary_path.unlink()
    shutil.copyfile(source, temporary_path)
    os.chmod(temporary_path, mode)
    os.replace(temporary_path, target)


def _legacy_path_is_populated(target: Path, relative_path: str) -> bool:
    current = target
    parts = Path(relative_path).parts
    for index, part in enumerate(parts):
        current /= part
        try:
            current_stat = current.lstat()
        except FileNotFoundError:
            return False
        if index == len(parts) - 1:
            return True
        if not stat.S_ISDIR(current_stat.st_mode):
            return True
    return False


def legacy_restore_conflicts(target: Path) -> tuple[str, ...]:
    try:
        target_stat = target.lstat()
    except FileNotFoundError:
        return ()
    if not stat.S_ISDIR(target_stat.st_mode):
        raise RuntimeError("legacy restore target root must be a real directory")

    conflicts: list[str] = []
    for managed_path in MANAGED_PATH_ORDER:
        relative_path = managed_path.value
        if _legacy_path_is_populated(target, relative_path):
            conflicts.append(relative_path)
        if relative_path not in RUNTIME_FILES:
            for suffix in ("-wal", "-shm"):
                sidecar = f"{relative_path}{suffix}"
                if _legacy_path_is_populated(target, sidecar):
                    conflicts.append(sidecar)
    return tuple(conflicts)


def validate_restore_target(
    backup: Path,
    target: Path,
    *,
    allow_legacy_partial_new_lineage: bool,
    expected_provider_intent_activation: ProviderIntentActivation = ProviderIntentActivation.NOT_ACTIVATED,
    expected_legacy_import_id: str | None = None,
) -> dict[str, object]:
    _validate_activation_options(
        expected_provider_intent_activation,
        expected_legacy_import_id,
    )
    manifest = verify_backup(
        backup,
        expected_legacy_import_id=expected_legacy_import_id,
    )
    if manifest.get("format_version") == V3_FORMAT_VERSION:
        if allow_legacy_partial_new_lineage:
            raise RuntimeError(
                "--allow-legacy-partial-new-lineage is valid only for "
                "legacy v1/v2 backups"
            )
        parsed = AtlasCoreBackupV3Manifest.from_dict(manifest)
        if parsed.provider_intent_activation is not expected_provider_intent_activation:
            raise RuntimeError("backup and target Provider Intent activation disagree")
        return manifest
    if not allow_legacy_partial_new_lineage:
        raise RuntimeError(
            "legacy v1/v2 partial restore requires "
            "--allow-legacy-partial-new-lineage"
        )
    conflicts = legacy_restore_conflicts(target)
    if conflicts:
        raise RuntimeError(
            "legacy v1/v2 partial restore requires a managed-empty target; "
            f"conflicting managed paths: {', '.join(conflicts)}"
        )
    return manifest


def restore_backup(
    backup: Path,
    target: Path,
    *,
    allow_legacy_partial_new_lineage: bool = False,
    expected_provider_intent_activation: ProviderIntentActivation = ProviderIntentActivation.NOT_ACTIVATED,
    expected_legacy_import_id: str | None = None,
) -> None:
    manifest = validate_restore_target(
        backup,
        target,
        allow_legacy_partial_new_lineage=allow_legacy_partial_new_lineage,
        expected_provider_intent_activation=expected_provider_intent_activation,
        expected_legacy_import_id=expected_legacy_import_id,
    )
    if manifest.get("format_version") == V3_FORMAT_VERSION:
        try:
            from atlas_data_restore_transaction import (
                execute_v3_restore,
                recover_v3_restore,
                verify_v3_target,
            )
        except ModuleNotFoundError:
            from scripts.atlas_data_restore_transaction import (
                execute_v3_restore,
                recover_v3_restore,
                verify_v3_target,
            )

        recovery = recover_v3_restore(
            target,
            expected_legacy_import_id=expected_legacy_import_id,
        )
        print(f"Prior restore recovery: {recovery}")
        execute_v3_restore(
            backup,
            target,
            runtime_uid=os.getuid(),
            runtime_gid=os.getgid(),
            expected_legacy_import_id=expected_legacy_import_id,
        )
        verify_v3_target(
            target,
            AtlasCoreBackupV3Manifest.from_dict(manifest),
            runtime_uid=os.getuid(),
            runtime_gid=os.getgid(),
            expected_legacy_import_id=expected_legacy_import_id,
        )
        return
    target.mkdir(parents=True, exist_ok=True)

    for filename in DATABASES:
        temporary_path = target / f".{filename}.restore"
        if temporary_path.exists():
            temporary_path.unlink()
        sqlite_backup(backup / filename, temporary_path)
        result = integrity(temporary_path)
        if result != "ok":
            raise RuntimeError(
                f"restored database integrity check failed for "
                f"{filename}: {result}"
            )
        os.replace(temporary_path, target / filename)
        for suffix in ("-wal", "-shm"):
            journal = target / f"{filename}{suffix}"
            if journal.exists():
                journal.unlink()

    for record in manifest.get("files", []):
        relative_path = safe_relative_path(record.get("path"))
        atomic_restore_file(backup / relative_path, target / relative_path, 0o600)


def validate_runtime_manifest_record(relative_path: str, record: dict[str, object]) -> None:
    mode = record.get("mode")
    if mode is not None and not isinstance(mode, int):
        raise RuntimeError(f"backup runtime file mode is invalid: {relative_path}")
    if relative_path in SECRET_RUNTIME_FILES and mode not in (None, 0o600):
        raise RuntimeError(f"backup runtime secret file mode is invalid: {relative_path}")


def validate_runtime_file(path: Path, relative_path: str, mode: int) -> None:
    if relative_path == "config/policies.yaml":
        validate_policy_file(path)
    elif relative_path == "config/provider-connections.yaml":
        document = load_provider_store_document(path, relative_path)
        if document.get("version") != 1:
            raise RuntimeError("provider connection store version is invalid")
        if not isinstance(document.get("providers", {}), dict):
            raise RuntimeError("provider connection store providers are invalid")
        for provider_id, entry in document.get("providers", {}).items():
            validate_identifier(provider_id, "provider id")
            if not isinstance(entry, dict) or not isinstance(entry.get("connection", {}), dict):
                raise RuntimeError(  # noqa: TRY004
                    "provider connection store entry is invalid"
                )
    elif relative_path == "secrets/provider-connections.yaml":
        if mode != 0o600:
            raise RuntimeError("provider secret store mode is invalid")
        document = load_provider_store_document(path, relative_path)
        if document.get("version") != 1:
            raise RuntimeError("provider secret store version is invalid")
        if not isinstance(document.get("providers", {}), dict):
            raise RuntimeError("provider secret store providers are invalid")
        for provider_id, entry in document.get("providers", {}).items():
            validate_identifier(provider_id, "provider id")
            if not isinstance(entry, dict) or not isinstance(entry.get("secrets", {}), dict):
                raise RuntimeError(  # noqa: TRY004
                    "provider secret store entry is invalid"
                )
            for secret_name, secret_value in entry.get("secrets", {}).items():
                validate_identifier(secret_name, "secret name")
                if not isinstance(secret_value, str):
                    raise RuntimeError(  # noqa: TRY004
                        "provider secret store value is invalid"
                    )


def validate_policy_file(path: Path) -> None:
    """Validate the deterministic YAML subset accepted in Atlas policy files."""

    scopes: dict[int, tuple[str, ...]] = {-2: ()}
    keys_by_scope: dict[tuple[str, ...], set[str]] = {}
    for line_number, raw_line in enumerate(
        path.read_text(encoding="utf-8").splitlines(), start=1
    ):
        if not raw_line.strip() or raw_line.lstrip().startswith("#"):
            continue
        if "\t" in raw_line:
            raise RuntimeError(f"policy YAML contains a tab on line {line_number}")
        indent = len(raw_line) - len(raw_line.lstrip(" "))
        if indent % 2 or indent < 0:
            raise RuntimeError(f"policy YAML indentation is invalid on line {line_number}")
        text = raw_line.strip()
        if indent == 0 and text == "{}":
            continue
        if text.startswith("- "):
            if indent == 0 or not text[2:].strip():
                raise RuntimeError(f"policy YAML list item is invalid on line {line_number}")
            continue
        if ":" not in text:
            raise RuntimeError(f"policy YAML mapping is invalid on line {line_number}")
        raw_key, raw_value = text.split(":", 1)
        key = raw_key.strip().strip('"')
        if not key or any(character in key for character in "[]{}"):
            raise RuntimeError(f"policy YAML key is invalid on line {line_number}")
        parent = scopes.get(indent - 2)
        if parent is None:
            raise RuntimeError(f"policy YAML nesting is invalid on line {line_number}")
        seen = keys_by_scope.setdefault(parent, set())
        if key in seen:
            raise RuntimeError(f"policy YAML key is duplicated on line {line_number}")
        seen.add(key)
        current = (*parent, key)
        scopes[indent] = current
        for deeper in tuple(level for level in scopes if level > indent):
            del scopes[deeper]
        value = raw_value.strip()
        if key == "expected":
            allowed = (
                {"running", "stopped", "ignored"}
                if current[0] == "proxmox"
                else {"running", "stopped"}
                if current[0] == "docker"
                else {"active", "inactive"}
                if current[0] == "frigate"
                else None
            )
            if allowed is not None and value not in allowed:
                raise RuntimeError(f"policy expectation is invalid on line {line_number}")
        if value.startswith("[") and not value.endswith("]"):
            raise RuntimeError(f"policy YAML list is malformed on line {line_number}")
    # The runtime Policies model accepts an empty document and ignores unknown
    # top-level keys, so absence of a recognized section is not corruption.


def load_provider_store_document(path: Path, relative_path: str) -> dict[str, object]:
    """Parse the strict provider store YAML subset Atlas writes.

    The backup helper runs in a minimal Python image with no third-party YAML
    dependency. Provider connection stores are versioned Atlas-owned files with
    a narrow shape, so verification accepts only that explicit subset.
    """

    document: dict[str, object] = {"version": 1, "providers": {}}
    current_provider: str | None = None
    current_section: str | None = None

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        if not raw_line.strip() or raw_line.lstrip().startswith("#"):
            continue
        if "[" in raw_line or "]" in raw_line:
            raise RuntimeError(f"runtime file is malformed: {relative_path}")
        indent = len(raw_line) - len(raw_line.lstrip(" "))
        line = raw_line.strip()

        if indent == 0 and line == "version: 1":
            document["version"] = 1
        elif indent == 0 and line in {"providers:", "providers: {}"}:
            continue
        elif indent == 2 and line.endswith(":"):
            provider_id = line[:-1]
            validate_identifier(provider_id, "provider id")
            providers = document["providers"]
            assert isinstance(providers, dict)
            providers[provider_id] = {}
            current_provider = provider_id
            current_section = None
        elif indent == 4 and line in {"connection:", "secrets:"}:
            if current_provider is None:
                raise RuntimeError(f"runtime file is malformed: {relative_path}")
            current_section = line[:-1]
            providers = document["providers"]
            assert isinstance(providers, dict)
            entry = providers[current_provider]
            assert isinstance(entry, dict)
            entry[current_section] = {}
        elif indent == 6 and ":" in line:
            if current_provider is None or current_section is None:
                raise RuntimeError(f"runtime file is malformed: {relative_path}")
            key, value = line.split(":", 1)
            key = key.strip().strip('"')
            value = value.strip().strip('"')
            validate_identifier(key, "field name")
            providers = document["providers"]
            assert isinstance(providers, dict)
            entry = providers[current_provider]
            assert isinstance(entry, dict)
            section = entry[current_section]
            assert isinstance(section, dict)
            section[key] = parse_scalar(value)
        else:
            raise RuntimeError(f"runtime file is malformed: {relative_path}")

    return document


def parse_scalar(value: str) -> object:
    if value.lower() == "true":
        return True
    if value.lower() == "false":
        return False
    if re.fullmatch(r"\d+", value):
        return int(value)
    return value


def validate_identifier(value: object, label: str) -> None:
    if (
        not isinstance(value, str)
        or not value.strip()
        or value.strip() in {".", ".."}
        or "/" in value
        or "\\" in value
    ):
        raise RuntimeError(f"provider connection {label} is invalid")


def prune_backups(
    backup_root: Path,
    retention_days: int,
    minimum_count: int,
    *,
    dry_run: bool,
) -> None:
    if retention_days < 1:
        raise ValueError("retention days must be at least 1")
    if minimum_count < 1:
        raise ValueError("minimum count must be at least 1")
    if not backup_root.is_dir():
        raise RuntimeError(f"backup root not found: {backup_root}")

    backups: list[tuple[datetime, Path]] = []
    for path in backup_root.iterdir():
        if not path.is_dir():
            continue
        match = BACKUP_NAME_PATTERN.fullmatch(path.name)
        if match is None:
            continue
        timestamp = datetime.strptime(
            match.group("timestamp"),
            "%Y%m%dT%H%M%SZ",
        ).replace(tzinfo=timezone.utc)
        backups.append((timestamp, path))

    backups.sort(reverse=True)
    cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)
    candidates = [
        path
        for timestamp, path in backups[minimum_count:]
        if timestamp < cutoff
    ]

    for path in candidates:
        verify_backup(path)
        if dry_run:
            print(f"Would remove expired backup: {path}")
        else:
            shutil.rmtree(path)
            print(f"Removed expired backup: {path}")

    print(
        f"Backup retention complete: total={len(backups)} "
        f"expired={len(candidates)} minimum_kept={minimum_count}"
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)

    backup_parser = subparsers.add_parser("backup")
    backup_parser.add_argument("source", type=Path)
    backup_parser.add_argument("destination", type=Path)
    backup_parser.add_argument("--output-owner-uid", type=int)
    backup_parser.add_argument("--output-owner-gid", type=int)
    backup_parser.add_argument(
        "--operator-auth-initialized",
        choices=("true", "false"),
        required=True,
    )
    backup_parser.add_argument(
        "--provider-intent-activation",
        action=UniqueStoreAction,
        choices=tuple(item.value for item in ProviderIntentActivation),
        default=ProviderIntentActivation.NOT_ACTIVATED.value,
    )
    backup_parser.add_argument("--expected-legacy-import-id", action=UniqueStoreAction)

    verify_parser = subparsers.add_parser("verify")
    verify_parser.add_argument("backup", type=Path)
    verify_parser.add_argument("--expected-legacy-import-id", action=UniqueStoreAction)

    chown_parser = subparsers.add_parser("chown")
    chown_parser.add_argument("path", type=Path)
    chown_parser.add_argument("uid", type=int)
    chown_parser.add_argument("gid", type=int)

    restore_parser = subparsers.add_parser("restore")
    restore_parser.add_argument("backup", type=Path)
    restore_parser.add_argument("target", type=Path)
    restore_parser.add_argument(
        "--allow-legacy-partial-new-lineage",
        action="count",
        default=0,
    )
    restore_parser.add_argument(
        "--provider-intent-activation",
        action=UniqueStoreAction,
        choices=tuple(item.value for item in ProviderIntentActivation),
        default=ProviderIntentActivation.NOT_ACTIVATED.value,
    )
    restore_parser.add_argument("--expected-legacy-import-id", action=UniqueStoreAction)

    check_restore_parser = subparsers.add_parser("check-restore-target")
    check_restore_parser.add_argument("backup", type=Path)
    check_restore_parser.add_argument("target", type=Path)
    check_restore_parser.add_argument(
        "--allow-legacy-partial-new-lineage",
        action="count",
        default=0,
    )
    check_restore_parser.add_argument(
        "--provider-intent-activation",
        action=UniqueStoreAction,
        choices=tuple(item.value for item in ProviderIntentActivation),
        default=ProviderIntentActivation.NOT_ACTIVATED.value,
    )
    check_restore_parser.add_argument(
        "--expected-legacy-import-id", action=UniqueStoreAction
    )

    prune_parser = subparsers.add_parser("prune")
    prune_parser.add_argument("backup_root", type=Path)
    prune_parser.add_argument(
        "--retention-days",
        type=int,
        default=30,
    )
    prune_parser.add_argument(
        "--minimum-count",
        type=int,
        default=7,
    )
    prune_parser.add_argument("--dry-run", action="store_true")

    args = parser.parse_args()
    if getattr(args, "allow_legacy_partial_new_lineage", 0) > 1:
        parser.error("--allow-legacy-partial-new-lineage may be specified only once")
    return args


def main() -> None:
    args = parse_args()
    if args.command == "backup":
        create_backup(
            args.source,
            args.destination,
            operator_auth_initialized=args.operator_auth_initialized == "true",
            provider_intent_activation=ProviderIntentActivation(
                args.provider_intent_activation
            ),
            expected_legacy_import_id=args.expected_legacy_import_id,
        )
        if args.output_owner_uid is not None or args.output_owner_gid is not None:
            if args.output_owner_uid is None or args.output_owner_gid is None:
                raise RuntimeError(
                    "both --output-owner-uid and --output-owner-gid are required"
                )
            apply_owner(args.destination, args.output_owner_uid, args.output_owner_gid)
    elif args.command == "verify":
        manifest = verify_backup(
            args.backup,
            expected_legacy_import_id=args.expected_legacy_import_id,
        )
        if manifest.get("format_version") == V3_FORMAT_VERSION:
            parsed = AtlasCoreBackupV3Manifest.from_dict(manifest)
            database_count = sum(
                entry.content_kind is ContentKind.SQLITE
                and entry.disposition is InventoryDisposition.REQUIRED_PRESENT
                for entry in parsed.inventory
            )
            file_count = sum(
                entry.content_kind is ContentKind.YAML
                and entry.disposition is InventoryDisposition.REQUIRED_PRESENT
                for entry in parsed.inventory
            )
        else:
            database_count = len(manifest["databases"])
            file_count = len(manifest.get("files", []))
        print(
            f"Backup verified: {database_count} databases, "
            f"{file_count} runtime files, "
            f"created {manifest['created_at']}"
        )
    elif args.command == "chown":
        apply_owner(args.path, args.uid, args.gid)
    elif args.command == "restore":
        restore_backup(
            args.backup,
            args.target,
            allow_legacy_partial_new_lineage=(
                args.allow_legacy_partial_new_lineage == 1
            ),
            expected_provider_intent_activation=ProviderIntentActivation(
                args.provider_intent_activation
            ),
            expected_legacy_import_id=args.expected_legacy_import_id,
        )
        print("Backup restored and verified")
    elif args.command == "check-restore-target":
        validate_restore_target(
            args.backup,
            args.target,
            allow_legacy_partial_new_lineage=(
                args.allow_legacy_partial_new_lineage == 1
            ),
            expected_provider_intent_activation=ProviderIntentActivation(
                args.provider_intent_activation
            ),
            expected_legacy_import_id=args.expected_legacy_import_id,
        )
        print("Restore target preflight passed")
    else:
        prune_backups(
            args.backup_root,
            args.retention_days,
            args.minimum_count,
            dry_run=args.dry_run,
        )


if __name__ == "__main__":
    main()
