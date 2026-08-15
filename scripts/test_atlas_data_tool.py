"""Focused production writer and verifier tests for Atlas Core backup v3."""

from __future__ import annotations

import hashlib
import itertools
import json
import os
import runpy
import socket
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

CORE_ROOT = Path(__file__).resolve().parents[1] / "services" / "atlas-core"
sys.path.insert(0, str(CORE_ROOT))

from app.provider_intents.legacy_import import import_legacy_policy

from scripts.atlas_data_backup_models import (
    MANAGED_PATH_ORDER,
    InventoryDisposition,
)

TOOL = runpy.run_path(str(Path(__file__).with_name("atlas-data-tool.py")))
ProviderIntentActivation = TOOL["ProviderIntentActivation"]
_validate_operational_rows = TOOL["_validate_operational_rows"]
create_backup = TOOL["create_backup"]
legacy_restore_conflicts = TOOL["legacy_restore_conflicts"]
restore_backup = TOOL["restore_backup"]
validate_restore_target = TOOL["validate_restore_target"]
verify_backup = TOOL["verify_backup"]
DISPATCH_RESULT = json.dumps(
    {
        "request_id": "r1", "request_digest": "d1", "status": "succeeded",
        "target_fingerprint": "fingerprint", "started_at": "2026-01-01",
        "provider_operation": "restart",
    },
    separators=(",", ":"),
)
VERIFICATION_RESULT = json.dumps(
    {
        "request_id": "r1", "status": "succeeded", "started_at": "2026-01-01",
        "completed_at": "2026-01-01", "deadline": "2026-01-01",
    },
    separators=(",", ":"),
)

SCHEMAS = {
    "action_history.db": """
        CREATE TABLE provider_action_history (
            id TEXT PRIMARY KEY, provider_id TEXT NOT NULL, provider_name TEXT NOT NULL,
            action_id TEXT NOT NULL, action_label TEXT NOT NULL, status TEXT NOT NULL,
            success INTEGER NOT NULL, message TEXT NOT NULL, confirmed INTEGER NOT NULL,
            destructive INTEGER NOT NULL, parameter_names TEXT NOT NULL, request_id TEXT,
            started_at TEXT NOT NULL, completed_at TEXT NOT NULL, duration_ms REAL NOT NULL);
        CREATE INDEX idx_provider_action_history_completed_at
            ON provider_action_history (completed_at DESC);
        CREATE INDEX idx_provider_action_history_provider_status
            ON provider_action_history (provider_id, status, completed_at DESC);
    """,
    "provider_intelligence.db": """
        CREATE TABLE intelligence_telemetry
            (id TEXT PRIMARY KEY, collected_at TEXT NOT NULL, telemetry TEXT NOT NULL);
        CREATE INDEX idx_intelligence_telemetry_collected_at
            ON intelligence_telemetry (collected_at DESC);
    """,
    "operational_dispatch.db": """
        CREATE TABLE operational_dispatch (
            request_id TEXT PRIMARY KEY, request_digest TEXT NOT NULL, state TEXT NOT NULL,
            request_json TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
            dispatch_started_at TEXT, dispatch_result_json TEXT,
            verification_result_json TEXT);
        CREATE TABLE operational_dispatch_events (
            event_id TEXT PRIMARY KEY, status TEXT NOT NULL, occurred_at TEXT NOT NULL,
            event_json TEXT NOT NULL);
        CREATE INDEX idx_operational_dispatch_events_time
            ON operational_dispatch_events (occurred_at DESC);
        CREATE TABLE operational_dispatch_transitions (
            sequence INTEGER PRIMARY KEY AUTOINCREMENT, request_id TEXT NOT NULL,
            request_digest TEXT NOT NULL, previous_state TEXT, state TEXT NOT NULL,
            occurred_at TEXT NOT NULL);
        CREATE INDEX idx_operational_dispatch_transitions_request
            ON operational_dispatch_transitions (request_id, sequence);
    """,
    "operator_intents.db": """
        CREATE TABLE operator_intents (
            record_id TEXT PRIMARY KEY, request_digest TEXT NOT NULL, record_json TEXT NOT NULL,
            created_at TEXT NOT NULL, expires_at TEXT NOT NULL,
            schema_version INTEGER NOT NULL);
        CREATE TABLE operator_intent_audit (
            sequence INTEGER PRIMARY KEY AUTOINCREMENT, occurred_at TEXT NOT NULL,
            record_id TEXT, candidate_id TEXT, operator_id TEXT, event TEXT NOT NULL,
            reason TEXT NOT NULL);
    """,
    "operator_security_audit.db": """
        CREATE TABLE operator_security_audit (
            event_id TEXT PRIMARY KEY, occurred_at TEXT NOT NULL, request_id TEXT NOT NULL,
            operator_id TEXT, auth_method TEXT, action TEXT NOT NULL, outcome TEXT NOT NULL,
            reason TEXT NOT NULL);
    """,
}
MANAGED_CONFLICTS = tuple(
    conflict
    for path in MANAGED_PATH_ORDER
    for conflict in (
        (path.value, f"{path.value}-wal", f"{path.value}-shm")
        if path.value.endswith(".db")
        else (path.value,)
    )
)


def _database(root: Path, name: str) -> sqlite3.Connection:
    connection = sqlite3.connect(root / name)
    connection.executescript(SCHEMAS[name])
    connection.execute("PRAGMA journal_mode=WAL")
    return connection


def _source(root: Path, *, audit: bool = False) -> dict[str, sqlite3.Connection]:
    root.mkdir()
    connections = {
        name: _database(root, name)
        for name in SCHEMAS
        if audit or name != "operator_security_audit.db"
    }
    connections["action_history.db"].execute(
        "INSERT INTO provider_action_history VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        ("a1", "p", "Provider", "inspect", "Inspect", "succeeded", 1, "ok", 1,
         0, '["node"]', "req", "2026-01-01", "2026-01-01", 1.0),
    )
    connections["provider_intelligence.db"].execute(
        "INSERT INTO intelligence_telemetry VALUES (?,?,?)",
        ("i1", "2026-01-01", '{"status":"ok"}'),
    )
    request = {
        "schema_version": 1,
        "request_id": "r1",
        "request_digest": "d1",
        "idempotency_key": "key",
        "effect_kind": "operational_action",
        "execution_intent": "restart-service",
        "provider_id": "proxmox",
        "resource_id": "qemu/101",
        "resource_type": "qemu",
        "provider_action_id": "proxmox-qemu-graceful-restart-v1",
        "target_fingerprint": "fingerprint",
        "verification": {},
        "approval": {},
    }
    connections["operational_dispatch.db"].execute(
        "INSERT INTO operational_dispatch VALUES (?,?,?,?,?,?,?,?,?)",
        ("r1", "d1", "verified", json.dumps(request), "2026-01-01", "2026-01-01",
         "2026-01-01", DISPATCH_RESULT, VERIFICATION_RESULT),
    )
    for previous, state in (
        (None, "claimed"), ("claimed", "revalidated"),
        ("revalidated", "dispatching"), ("dispatching", "succeeded"),
        ("succeeded", "verifying"), ("verifying", "verified"),
    ):
        connections["operational_dispatch.db"].execute(
            "INSERT INTO operational_dispatch_transitions "
            "(request_id, request_digest, previous_state, state, occurred_at) "
            "VALUES (?,?,?,?,?)", ("r1", "d1", previous, state, "2026-01-01")
        )
    record = {"record_id": "o1", "request_digest": "od1", "schema_version": 1}
    connections["operator_intents.db"].execute(
        "INSERT INTO operator_intents VALUES (?,?,?,?,?,?)",
        ("o1", "od1", json.dumps(record), "2026-01-01", "2026-01-02", 1),
    )
    if audit:
        connections["operator_security_audit.db"].execute(
            "INSERT INTO operator_security_audit VALUES (?,?,?,?,?,?,?,?)",
            ("s1", "2026-01-01", "r1", "operator", "token", "read", "allowed", "ok"),
        )
    for connection in connections.values():
        connection.commit()
    (root / "config").mkdir()
    (root / "secrets").mkdir()
    (root / "config/policies.yaml").write_text(
        'proxmox:\n  guests:\n    "109":\n      expected: stopped\n', encoding="utf-8"
    )
    (root / "config/provider-connections.yaml").write_text(
        "version: 1\nproviders:\n  proxmox:\n    connection:\n      host: example\n",
        encoding="utf-8",
    )
    (root / "secrets/provider-connections.yaml").write_text(
        "version: 1\nproviders:\n  proxmox:\n    secrets:\n      token_value: secret\n",
        encoding="utf-8",
    )
    os.chmod(root / "secrets/provider-connections.yaml", 0o600)
    return connections


def _close(connections: dict[str, sqlite3.Connection]) -> None:
    for connection in connections.values():
        connection.close()


def _operational_event_connection(
    indexed_timestamp: str,
    payload_timestamp: str,
    *,
    indexed_status: str = "verified",
    payload_status: str = "verified",
) -> sqlite3.Connection:
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    connection.executescript(SCHEMAS["operational_dispatch.db"])
    event = {
        "event_id": "event-1",
        "status": payload_status,
        "occurred_at": payload_timestamp,
    }
    connection.execute(
        "INSERT INTO operational_dispatch_events VALUES (?,?,?,?)",
        ("event-1", indexed_status, indexed_timestamp, json.dumps(event)),
    )
    return connection


@pytest.mark.parametrize(
    ("indexed_timestamp", "payload_timestamp"),
    (
        ("2026-08-15T12:34:56+00:00", "2026-08-15T12:34:56Z"),
        ("2026-08-15T12:34:56+00:00", "2026-08-15T12:34:56+00:00"),
        ("2026-08-15T13:34:56+01:00", "2026-08-15T12:34:56Z"),
    ),
)
def test_operational_event_validation_accepts_equal_aware_timestamps(
    indexed_timestamp: str,
    payload_timestamp: str,
) -> None:
    with _operational_event_connection(
        indexed_timestamp, payload_timestamp
    ) as connection:
        _validate_operational_rows(connection)


@pytest.mark.parametrize(
    ("indexed_timestamp", "payload_timestamp"),
    (
        ("2026-08-15T12:34:56+00:00", "2026-08-15T12:34:57Z"),
        ("2026-08-15T12:34:56+00:00", "2026-08-15T12:34:56Z-invalid"),
        ("2026-08-15T12:34:56", "2026-08-15T12:34:56Z"),
        ("2026-08-15T12:34:56+25:00", "2026-08-15T12:34:56Z"),
        ("invalid", "2026-08-15T12:34:56Z"),
        ("2026-08-15T12:34:56+00:00", "invalid"),
    ),
)
def test_operational_event_validation_rejects_unequal_or_invalid_timestamps(
    indexed_timestamp: str,
    payload_timestamp: str,
) -> None:
    with _operational_event_connection(
        indexed_timestamp, payload_timestamp
    ) as connection, pytest.raises(
        RuntimeError, match="operational event evidence is inconsistent"
    ):
        _validate_operational_rows(connection)


def test_operational_event_validation_retains_other_index_integrity() -> None:
    with _operational_event_connection(
        "2026-08-15T12:34:56+00:00",
        "2026-08-15T12:34:56Z",
        indexed_status="verified",
        payload_status="outcome_unknown",
    ) as connection, pytest.raises(
        RuntimeError, match="operational event evidence is inconsistent"
    ):
        _validate_operational_rows(connection)


def _activate_provider_intents(source: Path) -> str:
    result = import_legacy_policy(
        source / "config/policies.yaml",
        source / "provider_intents.db",
    )
    return result.import_id


def _legacy_backup(
    tmp_path: Path,
    version: int,
    runtime_files: tuple[str, ...] = (),
) -> Path:
    source = tmp_path / "source"
    connections = _source(source)
    _close(connections)
    backup = tmp_path / "legacy"
    backup.mkdir()
    database_records = []
    for name in ("action_history.db", "provider_intelligence.db"):
        destination = backup / name
        destination.write_bytes((source / name).read_bytes())
        database_records.append({
            "filename": name,
            "sha256": hashlib.sha256(destination.read_bytes()).hexdigest(),
            "size": destination.stat().st_size,
        })
    manifest: dict[str, object] = {
        "format_version": version,
        "created_at": "2026-01-01T00:00:00+00:00",
        "databases": database_records,
    }
    if version == 2:
        file_records = []
        for name in runtime_files:
            destination = backup / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes((source / name).read_bytes())
            mode = 0o600 if name.startswith("secrets/") else 0o644
            destination.chmod(mode)
            file_records.append({
                "path": name,
                "sha256": hashlib.sha256(destination.read_bytes()).hexdigest(),
                "size": destination.stat().st_size,
                "mode": mode,
            })
        manifest["files"] = file_records
    (backup / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    return backup


@pytest.mark.parametrize("audit", (False, True))
def test_v3_writer_snapshot_inventory_permissions_and_evidence(
    tmp_path: Path, audit: bool
) -> None:
    source = tmp_path / "source"
    backup = tmp_path / "backup"
    connections = _source(source, audit=audit)
    # This committed row remains in WAL while the source connection stays open.
    connections["provider_intelligence.db"].execute(
        "INSERT INTO intelligence_telemetry VALUES (?,?,?)",
        ("wal", "2026-01-02", '{"committed":true}'),
    )
    connections["provider_intelligence.db"].commit()
    source_database_hashes = {
        name: hashlib.sha256((source / name).read_bytes()).hexdigest()
        for name in SCHEMAS
        if (source / name).exists()
    }
    create_backup(source, backup, operator_auth_initialized=audit)
    manifest = verify_backup(backup)
    inventory = manifest["inventory"]
    assert manifest["schema"] == "atlas-core-data-backup-v3"
    assert manifest["format_version"] == 3
    assert [entry["path"] for entry in inventory] == [path.value for path in MANAGED_PATH_ORDER]
    assert (backup.stat().st_mode & 0o777) == 0o700
    assert all((path.stat().st_mode & 0o777) == 0o600 for path in backup.rglob("*") if path.is_file())
    assert not (backup / "operator_sessions.db").exists()
    assert not (backup / "provider_intents.db").exists()
    assert inventory[8]["disposition"] == InventoryDisposition.INVALIDATE_ON_RESTORE
    assert inventory[9]["absence_reason"] == "provider_intent_store_not_activated"
    assert inventory[7]["disposition"] == (
        "required_present" if audit else "approved_absent"
    )
    with sqlite3.connect(backup / "provider_intelligence.db") as connection:
        assert connection.execute("SELECT count(*) FROM intelligence_telemetry").fetchone()[0] == 2
    with sqlite3.connect(backup / "operational_dispatch.db") as connection:
        row = connection.execute(
            "SELECT request_id, state, dispatch_result_json, verification_result_json "
            "FROM operational_dispatch"
        ).fetchone()
        assert row == (
            "r1",
            "verified",
            DISPATCH_RESULT,
            VERIFICATION_RESULT,
        )
        assert connection.execute("SELECT count(*) FROM operational_dispatch_transitions").fetchone()[0] == 6
    with sqlite3.connect(backup / "operator_intents.db") as connection:
        assert connection.execute("SELECT record_id, request_digest FROM operator_intents").fetchone() == ("o1", "od1")
    assert source_database_hashes == {
        name: hashlib.sha256((source / name).read_bytes()).hexdigest()
        for name in source_database_hashes
    }


def test_v3_writer_and_verifier_support_activated_provider_intent_store(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source"
    connections = _source(source)
    import_id = _activate_provider_intents(source)
    with sqlite3.connect(source / "provider_intents.db") as connection:
        connection.execute("PRAGMA journal_mode=WAL")
    backup = tmp_path / "backup"
    create_backup(
        source,
        backup,
        operator_auth_initialized=False,
        provider_intent_activation=ProviderIntentActivation.ACTIVATED,
        expected_legacy_import_id=import_id,
    )
    manifest = verify_backup(backup, expected_legacy_import_id=import_id)
    entry = next(
        item for item in manifest["inventory"] if item["path"] == "provider_intents.db"
    )
    assert manifest["provider_intent_activation"] == "activated"
    assert entry["role"] == "authority"
    assert entry["disposition"] == "required_present"
    assert not (backup / "provider_intents.db-wal").exists()
    assert not (backup / "provider_intents.db-shm").exists()
    _close(connections)


def test_activated_backup_requires_exact_receipt_and_matching_restore_expectation(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source"
    connections = _source(source)
    import_id = _activate_provider_intents(source)
    backup = tmp_path / "backup"
    create_backup(
        source,
        backup,
        operator_auth_initialized=False,
        provider_intent_activation=ProviderIntentActivation.ACTIVATED,
        expected_legacy_import_id=import_id,
    )
    with pytest.raises(RuntimeError, match="expected import ID"):
        verify_backup(backup)
    with pytest.raises(RuntimeError, match="expected import ID"):
        validate_restore_target(
            backup,
            tmp_path / "target",
            allow_legacy_partial_new_lineage=False,
            expected_legacy_import_id=None,
        )
    _close(connections)


def test_activated_backup_rejects_wrong_valid_import_id(tmp_path: Path) -> None:
    source = tmp_path / "source"
    connections = _source(source)
    _activate_provider_intents(source)
    with pytest.raises(RuntimeError, match="application validation failed"):
        create_backup(
            source,
            tmp_path / "backup",
            operator_auth_initialized=False,
            provider_intent_activation=ProviderIntentActivation.ACTIVATED,
            expected_legacy_import_id=(
                "provider-intent-legacy-policy-import-v1:" + "a" * 64
            ),
        )
    _close(connections)


def test_activated_backup_accepts_exact_zero_entry_import_receipt(tmp_path: Path) -> None:
    source = tmp_path / "source"
    connections = _source(source)
    (source / "config/policies.yaml").write_text(
        "proxmox:\n  guests: {}\n", encoding="utf-8"
    )
    import_id = _activate_provider_intents(source)
    backup = tmp_path / "backup"
    create_backup(
        source,
        backup,
        operator_auth_initialized=False,
        provider_intent_activation=ProviderIntentActivation.ACTIVATED,
        expected_legacy_import_id=import_id,
    )
    assert verify_backup(backup, expected_legacy_import_id=import_id)
    _close(connections)


def test_activated_backup_validates_the_captured_snapshot(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "source"
    connections = _source(source)
    import_id = _activate_provider_intents(source)
    original_backup = create_backup.__globals__["sqlite_backup"]

    def snapshot_then_mutate(source_path: Path, destination_path: Path) -> None:
        original_backup(source_path, destination_path)
        if source_path.name == "provider_intents.db":
            with sqlite3.connect(source_path) as connection:
                connection.execute(
                    "DELETE FROM provider_intent_requests WHERE request_id LIKE ?",
                    ("provider-intent-legacy-policy-import-v1:%",),
                )

    monkeypatch.setitem(create_backup.__globals__, "sqlite_backup", snapshot_then_mutate)
    backup = tmp_path / "backup"
    create_backup(
        source,
        backup,
        operator_auth_initialized=False,
        provider_intent_activation=ProviderIntentActivation.ACTIVATED,
        expected_legacy_import_id=import_id,
    )
    assert verify_backup(backup, expected_legacy_import_id=import_id)
    _close(connections)


def test_activated_backup_rejects_captured_unsupported_active_authority(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source"
    connections = _source(source)
    import_id = _activate_provider_intents(source)
    with sqlite3.connect(source / "provider_intents.db") as connection:
        row = connection.execute(
            "SELECT intent_id,record_version,record_json FROM provider_intent_records "
            "WHERE lifecycle='active'"
        ).fetchone()
        assert row is None  # Legacy import is deliberately unbound, not active authority.
        legacy = connection.execute(
            "SELECT intent_id,record_version,record_json FROM provider_intent_records LIMIT 1"
        ).fetchone()
        record = json.loads(legacy[2])
        record["lifecycle"] = "active"
        record["resource_type"] = "lxc"
        record["incarnation_fingerprint"] = "provider-management-fingerprint-v1:" + "b" * 64
        connection.execute(
            "UPDATE provider_intent_records SET lifecycle='active',record_json=? "
            "WHERE intent_id=? AND record_version=?",
            (json.dumps(record), legacy[0], legacy[1]),
        )
    with pytest.raises(RuntimeError, match="application validation failed"):
        create_backup(
            source,
            tmp_path / "backup",
            operator_auth_initialized=False,
            provider_intent_activation=ProviderIntentActivation.ACTIVATED,
            expected_legacy_import_id=import_id,
        )
    _close(connections)


@pytest.mark.parametrize(
    "arguments",
    (
        ("--provider-intent-activation", "activated", "--provider-intent-activation", "not_activated"),
        ("--expected-legacy-import-id", "first", "--expected-legacy-import-id", "second"),
    ),
)
def test_cli_rejects_duplicate_provider_intent_options(arguments: tuple[str, ...]) -> None:
    result = subprocess.run(
        [
            sys.executable,
            str(Path(__file__).with_name("atlas-data-tool.py")),
            "backup",
            "/missing-source",
            "/missing-destination",
            "--operator-auth-initialized",
            "false",
            *arguments,
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 2
    assert "may be specified only once" in result.stderr


@pytest.mark.parametrize("value", ("unknown", ""))
def test_cli_rejects_unknown_or_empty_provider_intent_activation(value: str) -> None:
    result = subprocess.run(
        [
            sys.executable,
            str(Path(__file__).with_name("atlas-data-tool.py")),
            "backup",
            "/missing-source",
            "/missing-destination",
            "--operator-auth-initialized",
            "false",
            "--provider-intent-activation",
            value,
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 2
    assert "invalid choice" in result.stderr


def test_activation_and_import_id_options_fail_closed_before_store_access(
    tmp_path: Path,
) -> None:
    with pytest.raises(RuntimeError, match="requires an expected import ID"):
        create_backup(
            tmp_path / "missing",
            tmp_path / "activated",
            operator_auth_initialized=False,
            provider_intent_activation=ProviderIntentActivation.ACTIVATED,
        )
    with pytest.raises(RuntimeError, match="cannot accept an expected import ID"):
        create_backup(
            tmp_path / "missing",
            tmp_path / "inactive",
            operator_auth_initialized=False,
            expected_legacy_import_id=(
                "provider-intent-legacy-policy-import-v1:" + "a" * 64
            ),
        )


@pytest.mark.parametrize(
    "missing",
    (
        "action_history.db", "provider_intelligence.db", "operational_dispatch.db",
        "operator_intents.db", "config/policies.yaml",
        "config/provider-connections.yaml", "secrets/provider-connections.yaml",
    ),
)
def test_writer_fails_closed_when_required_store_is_missing(
    tmp_path: Path, missing: str
) -> None:
    source = tmp_path / "source"
    connections = _source(source)
    _close(connections)
    (source / missing).unlink()
    with pytest.raises(RuntimeError, match="required store not found"):
        create_backup(source, tmp_path / "backup", operator_auth_initialized=False)


@pytest.mark.parametrize("unexpected", ("operator_security_audit.db", "provider_intents.db"))
def test_writer_rejects_unexpected_inactive_store(tmp_path: Path, unexpected: str) -> None:
    source = tmp_path / "source"
    connections = _source(source)
    _close(connections)
    (source / unexpected).touch()
    with pytest.raises(RuntimeError, match="unexpected"):
        create_backup(source, tmp_path / "backup", operator_auth_initialized=False)


@pytest.mark.parametrize("database", tuple(SCHEMAS))
def test_application_schema_failure_is_rejected(tmp_path: Path, database: str) -> None:
    source = tmp_path / "source"
    connections = _source(source, audit=database == "operator_security_audit.db")
    _close(connections)
    with sqlite3.connect(source / database) as connection:
        table = next(iter(connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        )))[0]
        connection.execute(f"DROP TABLE {table}")
    with pytest.raises(RuntimeError, match="application table set"):
        create_backup(
            source,
            tmp_path / "backup",
            operator_auth_initialized=database == "operator_security_audit.db",
        )


def test_verifier_rejects_checksum_unexpected_file_and_missing_required(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source"
    connections = _source(source)
    create_backup(source, tmp_path / "backup", operator_auth_initialized=False)
    _close(connections)
    backup = tmp_path / "backup"
    (backup / "unexpected.db").touch(mode=0o600)
    with pytest.raises(RuntimeError, match="physical file set"):
        verify_backup(backup)
    (backup / "unexpected.db").unlink()
    (backup / "action_history.db").write_bytes(b"changed")
    with pytest.raises(RuntimeError, match="size mismatch|checksum mismatch"):
        verify_backup(backup)


def test_verifier_rejects_symlink_and_application_invalid_ledger(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source"
    connections = _source(source)
    backup = tmp_path / "backup"
    create_backup(source, backup, operator_auth_initialized=False)
    _close(connections)
    (backup / "alias.db").symlink_to("action_history.db")
    with pytest.raises(RuntimeError, match="symbolic links"):
        verify_backup(backup)
    (backup / "alias.db").unlink()
    with sqlite3.connect(backup / "operational_dispatch.db") as connection:
        connection.execute(
            "UPDATE operational_dispatch SET dispatch_result_json=?",
            ('{"request_id":"other","request_digest":"d1"}',),
        )
    manifest_path = backup / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    ledger = backup / "operational_dispatch.db"
    ledger_entry = next(
        entry for entry in manifest["inventory"]
        if entry["path"] == "operational_dispatch.db"
    )
    ledger_entry["size"] = ledger.stat().st_size
    ledger_entry["sha256"] = hashlib.sha256(ledger.read_bytes()).hexdigest()
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    manifest_path.chmod(0o600)
    with pytest.raises(RuntimeError, match="dispatch result identity"):
        verify_backup(backup)


@pytest.mark.parametrize(
    "missing",
    (
        "action_history.db", "provider_intelligence.db", "operational_dispatch.db",
        "operator_intents.db", "config/policies.yaml",
        "config/provider-connections.yaml", "secrets/provider-connections.yaml",
    ),
)
def test_verifier_rejects_each_missing_required_artifact(
    tmp_path: Path, missing: str
) -> None:
    source = tmp_path / "source"
    connections = _source(source)
    backup = tmp_path / "backup"
    create_backup(source, backup, operator_auth_initialized=False)
    _close(connections)
    (backup / missing).unlink()
    with pytest.raises(RuntimeError, match="physical file set"):
        verify_backup(backup)


def test_runtime_yaml_structure_failure_is_rejected(tmp_path: Path) -> None:
    source = tmp_path / "source"
    connections = _source(source)
    _close(connections)
    (source / "config/policies.yaml").write_text("proxmox:\n guests: {}\n", encoding="utf-8")
    with pytest.raises(RuntimeError, match="indentation"):
        create_backup(source, tmp_path / "backup", operator_auth_initialized=False)


def test_v3_restore_requires_prepared_target(tmp_path: Path) -> None:
    source = tmp_path / "source"
    connections = _source(source)
    create_backup(source, tmp_path / "backup", operator_auth_initialized=False)
    _close(connections)
    target = tmp_path / "target"
    with pytest.raises(RuntimeError, match="real directory"):
        restore_backup(tmp_path / "backup", target)
    assert not target.exists()


def test_v3_restore_adopts_populated_target_transactionally(tmp_path: Path) -> None:
    source = tmp_path / "source"
    connections = _source(source)
    backup = tmp_path / "backup"
    create_backup(source, backup, operator_auth_initialized=False)
    _close(connections)
    target = tmp_path / "target"
    target.mkdir()
    existing = target / "operational_dispatch.db"
    existing.write_bytes(b"production-state")
    existing.chmod(0o640)
    restore_backup(backup, target)
    assert existing.read_bytes() != b"production-state"
    assert existing.stat().st_mode & 0o777 == 0o600
    assert not (target / "operator_sessions.db").exists()
    assert not (target / "provider_intents.db").exists()


def test_legacy_v1_requires_acknowledgement_and_restores_managed_empty_target(
    tmp_path: Path,
) -> None:
    backup = _legacy_backup(tmp_path, 1)
    target = tmp_path / "target"
    sentinels = tuple(
        target / relative_path
        for relative_path in (
            "unrelated-root-file",
            "cache/sentinel",
            "history/sentinel",
            "knowledge/sentinel",
            "providers/sentinel",
        )
    )
    for sentinel in sentinels:
        sentinel.parent.mkdir(parents=True, exist_ok=True)
        sentinel.write_text("unchanged", encoding="utf-8")
    with pytest.raises(RuntimeError, match="requires --allow-legacy"):
        restore_backup(backup, target)
    assert all(
        sentinel.read_text(encoding="utf-8") == "unchanged"
        for sentinel in sentinels
    )
    restore_backup(
        backup,
        target,
        allow_legacy_partial_new_lineage=True,
    )
    assert (target / "action_history.db").is_file()
    assert (target / "provider_intelligence.db").is_file()
    assert all(
        sentinel.read_text(encoding="utf-8") == "unchanged"
        for sentinel in sentinels
    )
    assert not (target / "config").exists()
    assert {
        path.value
        for path in MANAGED_PATH_ORDER
        if os.path.lexists(target / path.value)
    } == {"action_history.db", "provider_intelligence.db"}
    assert not (target / ".atlas-restore").exists()


@pytest.mark.parametrize(
    "conflict",
    MANAGED_CONFLICTS,
)
def test_each_managed_path_and_database_sidecar_blocks_legacy_restore(
    tmp_path: Path, conflict: str
) -> None:
    relative_path = conflict
    backup = _legacy_backup(tmp_path, 1)
    target = tmp_path / "target"
    path = target / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"existing")
    before = path.read_bytes()
    with pytest.raises(RuntimeError, match=relative_path.replace("-", "\\-")):
        restore_backup(
            backup,
            target,
            allow_legacy_partial_new_lineage=True,
        )
    assert path.read_bytes() == before
    assert not (target / ".action_history.db.restore").exists()


@pytest.mark.parametrize("kind", ("symlink", "directory", "fifo", "socket"))
def test_special_object_at_managed_path_blocks_without_traversal(
    tmp_path: Path, kind: str
) -> None:
    backup = _legacy_backup(tmp_path, 1)
    target = tmp_path / "target"
    target.mkdir()
    path = target / "provider_intents.db"
    if kind == "symlink":
        path.symlink_to(tmp_path / "missing-outside")
    elif kind == "directory":
        path.mkdir()
    elif kind == "fifo":
        os.mkfifo(path)
    else:
        sock = socket.socket(socket.AF_UNIX)
        sock.bind(str(path))
        sock.close()
    assert legacy_restore_conflicts(target) == ("provider_intents.db",)
    with pytest.raises(RuntimeError, match="provider_intents.db"):
        restore_backup(
            backup,
            target,
            allow_legacy_partial_new_lineage=True,
        )


@pytest.mark.parametrize("ancestor", ("config", "secrets"))
def test_symlinked_managed_ancestor_blocks_without_inspecting_outside(
    tmp_path: Path, ancestor: str
) -> None:
    backup = _legacy_backup(tmp_path, 1)
    target = tmp_path / "target"
    target.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    sentinel = outside / "sentinel"
    sentinel.write_bytes(b"outside-unchanged")
    (target / ancestor).symlink_to(outside, target_is_directory=True)
    conflicts = legacy_restore_conflicts(target)
    expected = tuple(
        path.value
        for path in MANAGED_PATH_ORDER
        if path.value.startswith(f"{ancestor}/")
    )
    assert conflicts == expected
    with pytest.raises(RuntimeError, match="managed-empty"):
        restore_backup(
            backup,
            target,
            allow_legacy_partial_new_lineage=True,
        )
    assert sentinel.read_bytes() == b"outside-unchanged"


@pytest.mark.parametrize("root_kind", ("symlink", "file", "fifo"))
def test_unsafe_legacy_target_root_fails_closed(
    tmp_path: Path, root_kind: str
) -> None:
    backup = _legacy_backup(tmp_path, 1)
    target = tmp_path / "target"
    outside = tmp_path / "outside"
    outside.mkdir()
    sentinel = outside / "sentinel"
    sentinel.write_bytes(b"outside-unchanged")
    if root_kind == "symlink":
        target.symlink_to(outside, target_is_directory=True)
    elif root_kind == "file":
        target.write_bytes(b"target-unchanged")
    else:
        os.mkfifo(target)
    with pytest.raises(RuntimeError, match="target root must be a real directory"):
        restore_backup(
            backup,
            target,
            allow_legacy_partial_new_lineage=True,
        )
    assert sentinel.read_bytes() == b"outside-unchanged"


def test_second_legacy_check_catches_file_created_after_preflight(
    tmp_path: Path,
) -> None:
    backup = _legacy_backup(tmp_path, 1)
    target = tmp_path / "target"
    target.mkdir()
    validate_restore_target(
        backup,
        target,
        allow_legacy_partial_new_lineage=True,
    )
    raced_path = target / "operational_dispatch.db"
    raced_path.write_bytes(b"created-after-preflight")
    before_stat = raced_path.lstat()
    with pytest.raises(RuntimeError, match="operational_dispatch.db"):
        restore_backup(
            backup,
            target,
            allow_legacy_partial_new_lineage=True,
        )
    after_stat = raced_path.lstat()
    assert raced_path.read_bytes() == b"created-after-preflight"
    assert (
        after_stat.st_mode,
        after_stat.st_size,
        after_stat.st_mtime_ns,
    ) == (
        before_stat.st_mode,
        before_stat.st_size,
        before_stat.st_mtime_ns,
    )


def test_legacy_conflict_reporting_follows_managed_inventory_order(
    tmp_path: Path,
) -> None:
    target = tmp_path / "target"
    target.mkdir()
    for relative_path in (
        "provider_intents.db-shm",
        "action_history.db-wal",
        "config/policies.yaml",
        "action_history.db",
    ):
        path = target / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.touch()
    assert legacy_restore_conflicts(target) == (
        "action_history.db",
        "action_history.db-wal",
        "config/policies.yaml",
        "provider_intents.db-shm",
    )


def test_legacy_acknowledgement_is_rejected_for_v3(tmp_path: Path) -> None:
    source = tmp_path / "source"
    connections = _source(source)
    backup = tmp_path / "backup"
    create_backup(source, backup, operator_auth_initialized=False)
    _close(connections)
    target = tmp_path / "target"
    target.mkdir()
    with pytest.raises(RuntimeError, match="valid only for legacy"):
        restore_backup(
            backup,
            target,
            allow_legacy_partial_new_lineage=True,
        )


def test_tool_rejects_duplicate_legacy_acknowledgement(tmp_path: Path) -> None:
    result = subprocess.run(
        (
            sys.executable,
            str(Path(__file__).with_name("atlas-data-tool.py")),
            "restore",
            str(tmp_path / "backup"),
            str(tmp_path / "target"),
            "--allow-legacy-partial-new-lineage",
            "--allow-legacy-partial-new-lineage",
        ),
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 2
    assert "may be specified only once" in result.stderr


def test_malformed_v3_fails_verification_without_touching_target(tmp_path: Path) -> None:
    source = tmp_path / "source"
    connections = _source(source)
    backup = tmp_path / "backup"
    create_backup(source, backup, operator_auth_initialized=False)
    _close(connections)
    (backup / "action_history.db").write_bytes(b"corrupt")
    target = tmp_path / "target"
    target.mkdir()
    marker = target / "marker"
    marker.write_bytes(b"unchanged")
    with pytest.raises(RuntimeError, match="size mismatch|checksum mismatch"):
        restore_backup(backup, target)
    assert marker.read_bytes() == b"unchanged"
    assert tuple(target.iterdir()) == (marker,)


def test_empty_runtime_valid_databases_and_default_policy_are_accepted(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source"
    connections = _source(source, audit=True)
    for connection in connections.values():
        for table in connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        ).fetchall():
            connection.execute(f"DELETE FROM {table[0]}")
        connection.commit()
    (source / "config/policies.yaml").write_text("{}\n", encoding="utf-8")
    create_backup(source, tmp_path / "backup", operator_auth_initialized=True)
    _close(connections)
    verify_backup(tmp_path / "backup")


@pytest.mark.parametrize("version", (1, 2))
def test_historical_backup_verification_is_unchanged(tmp_path: Path, version: int) -> None:
    backup = tmp_path / "legacy"
    backup.mkdir()
    records = []
    for name in ("action_history.db", "provider_intelligence.db"):
        with sqlite3.connect(backup / name) as connection:
            connection.execute("CREATE TABLE records (value TEXT)")
        path = backup / name
        records.append({
            "filename": name,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "size": path.stat().st_size,
        })
    manifest = {
        "format_version": version,
        "created_at": "2026-01-01T00:00:00+00:00",
        "databases": records,
    }
    if version == 2:
        manifest["files"] = []
    (backup / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    assert verify_backup(backup)["format_version"] == version


@pytest.mark.parametrize(
    "runtime_files",
    tuple(
        subset
        for count in range(4)
        for subset in itertools.combinations(
            (
                "config/policies.yaml",
                "config/provider-connections.yaml",
                "secrets/provider-connections.yaml",
            ),
            count,
        )
    ),
)
def test_all_historical_v2_runtime_file_subsets_remain_valid(
    tmp_path: Path, runtime_files: tuple[str, ...]
) -> None:
    backup = _legacy_backup(tmp_path, 2, runtime_files)
    assert verify_backup(backup)["format_version"] == 2
    target = tmp_path / "target"
    with pytest.raises(RuntimeError, match="requires --allow-legacy"):
        restore_backup(backup, target)
    restore_backup(
        backup,
        target,
        allow_legacy_partial_new_lineage=True,
    )
    assert all((target / name).is_file() for name in runtime_files)
    assert {
        path.relative_to(target).as_posix()
        for path in target.rglob("*.yaml")
    } == set(runtime_files)
    assert {
        path.value
        for path in MANAGED_PATH_ORDER
        if os.path.lexists(target / path.value)
    } == {
        "action_history.db",
        "provider_intelligence.db",
        *runtime_files,
    }
    assert not (target / ".atlas-restore").exists()


def test_backup_wrapper_keeps_incomplete_publication_private() -> None:
    wrapper = Path(__file__).with_name("atlas-data-backup").read_text(encoding="utf-8")
    assert 'chmod 0700 "$INCOMPLETE_DIRECTORY"' in wrapper
    assert "chmod -R" not in wrapper
    assert wrapper.index("python /tool.py backup") < wrapper.index('mv -- "$INCOMPLETE_DIRECTORY"')
    assert '--operator-auth-initialized "$operator_auth_initialized"' in wrapper


def test_failed_wrapper_creation_does_not_publish_backup(tmp_path: Path) -> None:
    executable_directory = tmp_path / "bin"
    executable_directory.mkdir()
    docker = executable_directory / "docker"
    docker.write_text(
        "#!/usr/bin/env bash\n[[ ${1:-} = volume ]] && exit 0\nexit 19\n",
        encoding="utf-8",
    )
    docker.chmod(0o700)
    backup_root = tmp_path / "backups"
    result = subprocess.run(
        [str(Path(__file__).with_name("atlas-data-backup")), str(backup_root)],
        check=False,
        env={**os.environ, "PATH": f"{executable_directory}:{os.environ['PATH']}"},
        capture_output=True,
        text=True,
    )
    assert result.returncode == 19
    assert not backup_root.exists() or list(backup_root.iterdir()) == []


def test_wrapper_rejects_malformed_auth_state_before_snapshot(tmp_path: Path) -> None:
    executable_directory = tmp_path / "bin"
    executable_directory.mkdir()
    docker = executable_directory / "docker"
    docker.write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
    docker.chmod(0o700)
    backup_root = tmp_path / "backups"
    result = subprocess.run(
        [str(Path(__file__).with_name("atlas-data-backup")), str(backup_root)],
        check=False,
        env={
            **os.environ,
            "ATLAS_OPERATOR_AUTH_ENABLED": "TRUE",
            "PATH": f"{executable_directory}:{os.environ['PATH']}",
        },
        capture_output=True,
        text=True,
    )
    assert result.returncode == 2
    assert "must be true or false" in result.stderr
    assert not backup_root.exists() or list(backup_root.iterdir()) == []


def test_failure_after_staging_manifest_does_not_publish_or_leak(
    tmp_path: Path,
) -> None:
    executable_directory = tmp_path / "bin"
    executable_directory.mkdir()
    counter = tmp_path / "docker-count"
    backup_root = tmp_path / "backups"
    docker = executable_directory / "docker"
    docker.write_text(
        "#!/usr/bin/env bash\n"
        "if [[ ${1:-} = volume ]]; then exit 0; fi\n"
        f"count=$(($(cat {counter!s} 2>/dev/null || echo 0)+1))\n"
        f"printf '%s' \"$count\" > {counter!s}\n"
        "if [[ $count = 2 ]]; then\n"
        f"  staged=$(find {backup_root!s} -maxdepth 1 -name '.*.incomplete' -type d)\n"
        "  printf '%s' staged > \"$staged/manifest.json\"\n"
        "  chmod 0600 \"$staged/manifest.json\"\n"
        "  exit 0\n"
        "fi\n"
        "if [[ $count = 3 ]]; then exit 23; fi\n"
        "exit 0\n",
        encoding="utf-8",
    )
    docker.chmod(0o700)
    result = subprocess.run(
        [str(Path(__file__).with_name("atlas-data-backup")), str(backup_root)],
        check=False,
        env={**os.environ, "PATH": f"{executable_directory}:{os.environ['PATH']}"},
        capture_output=True,
        text=True,
    )
    assert result.returncode == 23
    assert list(backup_root.iterdir()) == []
