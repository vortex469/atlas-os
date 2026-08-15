from __future__ import annotations

import hashlib
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

import pytest

from app.provider_intents.backup_validation import (
    validate_activated_provider_intent_backup_store,
)
from app.provider_intents.legacy_import import load_legacy_policy_import
from app.provider_intents.migration import migrate_p2c_provider_intent_store
from app.provider_intents.store import (
    ProviderIntentStore,
    ProviderIntentStoreCorruptionError,
    ProviderIntentStoreSchemaError,
)
from app.provider_intents.test_store import command, supersede_command

NOW = datetime(2026, 8, 15, tzinfo=UTC)
FINGERPRINT_B = "provider-management-fingerprint-v1:" + "b" * 64
_P3_TABLES = (
    "provider_intent_active_coordinates",
    "provider_intent_operations",
    "provider_intent_operation_audit",
)


def _downgrade_fixture(path: Path) -> None:
    with sqlite3.connect(path) as connection:
        for table in reversed(_P3_TABLES):
            connection.execute(f"DROP TABLE {table}")
        connection.execute(
            "UPDATE provider_intent_store_meta SET schema_version=1"
        )


def _evidence_digest(path: Path) -> str:
    with sqlite3.connect(path) as connection:
        payload = repr(
            tuple(
                (table, connection.execute(f"SELECT * FROM {table}").fetchall())
                for table in (
                    "provider_intent_records",
                    "provider_intent_requests",
                    "provider_intent_audit",
                )
            )
        ).encode()
    return hashlib.sha256(payload).hexdigest()


def test_empty_exact_p2c_store_migrates_only_when_explicit(tmp_path: Path) -> None:
    path = tmp_path / "provider_intents.db"
    ProviderIntentStore(path)
    _downgrade_fixture(path)
    with pytest.raises(ProviderIntentStoreSchemaError, match="migration is required"):
        ProviderIntentStore.open_existing(path)
    migrate_p2c_provider_intent_store(path)
    with sqlite3.connect(path) as connection:
        assert connection.execute(
            "SELECT schema_version FROM provider_intent_store_meta"
        ).fetchone()[0] == 2
    assert ProviderIntentStore.open_existing(path).read_snapshot().active_identity_bound_records == ()


def test_migration_preserves_active_superseded_request_and_audit_evidence(
    tmp_path: Path,
) -> None:
    path = tmp_path / "provider_intents.db"
    store = ProviderIntentStore(path)
    active = store.put(command("create-active", resource_id="111"), now=NOW)
    old = store.put(command("create-old"), now=NOW)
    superseded = store.supersede(
        supersede_command("supersede-old", old.record.intent_id, 1), now=NOW
    )
    _downgrade_fixture(path)
    before = _evidence_digest(path)

    migrated = migrate_p2c_provider_intent_store(path)

    assert _evidence_digest(path) == before
    assert migrated.get_current(active.record.intent_id) == active.record
    assert migrated.get_current(old.record.intent_id) == superseded.record
    assert len(migrated.audit(old.record.intent_id)) == 2
    assert migrated.read_snapshot().active_identity_bound_records == (active.record,)


def test_migration_preserves_legacy_records_and_import_receipt(tmp_path: Path) -> None:
    path = tmp_path / "provider_intents.db"
    policy = tmp_path / "policies.yaml"
    policy.write_text("proxmox:\n  guests:\n    '110':\n      expected: running\n")
    import_command = load_legacy_policy_import(policy)
    store = ProviderIntentStore(path)
    result = store.import_legacy_policy(import_command, now=NOW)
    _downgrade_fixture(path)
    before = _evidence_digest(path)

    migrated = migrate_p2c_provider_intent_store(path)

    assert _evidence_digest(path) == before
    assert migrated.get_import_completion(import_command) == result
    assert len(migrated.read_snapshot().legacy_unbound_records) == 1


def test_backup_validation_accepts_exact_p2c_and_p3_without_migrating(
    tmp_path: Path,
) -> None:
    path = tmp_path / "provider_intents.db"
    policy = tmp_path / "policies.yaml"
    policy.write_text("proxmox:\n  guests:\n    '110':\n      expected: running\n")
    import_command = load_legacy_policy_import(policy)
    ProviderIntentStore(path).import_legacy_policy(import_command, now=NOW)
    validate_activated_provider_intent_backup_store(
        path, policy, import_command.import_id
    )
    _downgrade_fixture(path)
    validate_activated_provider_intent_backup_store(
        path, policy, import_command.import_id
    )
    with sqlite3.connect(path) as connection:
        assert connection.execute(
            "SELECT schema_version FROM provider_intent_store_meta"
        ).fetchone()[0] == 1


def test_backup_validation_does_not_create_or_follow_a_store_path(
    tmp_path: Path,
) -> None:
    policy = tmp_path / "policies.yaml"
    policy.write_text("{}\n")
    import_command = load_legacy_policy_import(policy)
    missing = tmp_path / "missing.db"
    with pytest.raises(ValueError, match="regular non-symlink"):
        validate_activated_provider_intent_backup_store(
            missing, policy, import_command.import_id
        )
    assert not missing.exists()

    target = tmp_path / "target.db"
    ProviderIntentStore(target).import_legacy_policy(import_command, now=NOW)
    link = tmp_path / "linked.db"
    link.symlink_to(target)
    with pytest.raises(ValueError, match="regular non-symlink"):
        validate_activated_provider_intent_backup_store(
            link, policy, import_command.import_id
        )


@pytest.mark.parametrize(
    "stage",
    (
        "after_p2c_validation",
        "after_active_coordinate_schema",
        "after_operation_schema",
        "after_operation_audit_schema",
        "after_active_coordinate_population",
        "before_schema_version_update",
        "after_schema_version_update",
    ),
)
def test_every_migration_failure_rolls_back_to_exact_readable_p2c(
    tmp_path: Path, stage: str
) -> None:
    path = tmp_path / f"{stage}.db"
    ProviderIntentStore(path).put(command("create-active"), now=NOW)
    _downgrade_fixture(path)
    before = _evidence_digest(path)

    def fail(current: str) -> None:
        if current == stage:
            raise RuntimeError(stage)

    with pytest.raises(RuntimeError, match=stage):
        migrate_p2c_provider_intent_store(path, failure_injector=fail)
    assert _evidence_digest(path) == before
    with sqlite3.connect(path) as connection:
        assert connection.execute(
            "SELECT schema_version FROM provider_intent_store_meta"
        ).fetchone()[0] == 1
        assert {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table' "
                "AND name NOT LIKE 'sqlite_%'"
            )
        } == {
            "provider_intent_store_meta",
            "provider_intent_records",
            "provider_intent_requests",
            "provider_intent_audit",
        }


def test_migration_rejects_multiple_active_incarnations_without_repair(
    tmp_path: Path,
) -> None:
    path = tmp_path / "primary.db"
    other = tmp_path / "other.db"
    ProviderIntentStore(path).put(command("create-a"), now=NOW)
    ProviderIntentStore(other).put(
        command("create-b", fingerprint=FINGERPRINT_B), now=NOW
    )
    _downgrade_fixture(path)
    _downgrade_fixture(other)
    with sqlite3.connect(path) as target, sqlite3.connect(other) as source:
        record = source.execute("SELECT * FROM provider_intent_records").fetchone()
        request = source.execute("SELECT * FROM provider_intent_requests").fetchone()
        audit = source.execute("SELECT * FROM provider_intent_audit").fetchone()
        target.execute(
            "INSERT INTO provider_intent_records VALUES (?, ?, ?, ?, ?, ?, ?)", record
        )
        target.execute(
            "INSERT INTO provider_intent_requests VALUES (?, ?, ?, ?)", request
        )
        target.execute(
            "INSERT INTO provider_intent_audit "
            "(occurred_at,intent_id,record_version,request_id,request_digest,event) "
            "VALUES (?, ?, ?, ?, ?, ?)", audit[1:]
        )
    before = _evidence_digest(path)
    with pytest.raises(
        ProviderIntentStoreCorruptionError, match="multiple active incarnations"
    ):
        migrate_p2c_provider_intent_store(path)
    assert _evidence_digest(path) == before


@pytest.mark.parametrize("version", (0, 2, 99))
def test_migration_rejects_non_p2c_schema(tmp_path: Path, version: int) -> None:
    path = tmp_path / f"version-{version}.db"
    ProviderIntentStore(path)
    if version == 2:
        with pytest.raises(ProviderIntentStoreSchemaError):
            migrate_p2c_provider_intent_store(path)
        return
    _downgrade_fixture(path)
    with sqlite3.connect(path) as connection:
        connection.execute(
            "UPDATE provider_intent_store_meta SET schema_version=?", (version,)
        )
    with pytest.raises(ProviderIntentStoreSchemaError, match="exact P2c"):
        migrate_p2c_provider_intent_store(path)


def test_p3_persistence_modules_have_no_runtime_or_production_path_dependency() -> None:
    package = Path(__file__).parent
    source = "\n".join(
        (package / name).read_text(encoding="utf-8").casefold()
        for name in ("migration.py", "store.py", "backup_validation.py")
    )
    for forbidden in (
        "providers.proxmox",
        "provider_actions",
        "operational_dispatch",
        "execution_candidates",
        "approval",
        "discovery",
        "execution_gate",
        "handler_registry",
        "policies.yaml",
        "/var/lib/docker/volumes/atlas_atlas-data",
        "/opt/atlas/data/provider_intents.db",
    ):
        assert forbidden not in source
