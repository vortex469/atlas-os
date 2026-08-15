from __future__ import annotations

import json
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from app.models.provider_intents import (
    ProviderIntentKind,
    ProviderIntentLifecycle,
    ProviderIntentMutationCommand,
    ProviderIntentSupersedeCommand,
    ProviderIntentValue,
    build_provider_intent_request_digest,
    build_provider_intent_supersede_digest,
)
from app.provider_intents.store import (
    ProviderIntentStore,
    ProviderIntentStoreConflictError,
    ProviderIntentStoreCorruptionError,
    ProviderIntentStoreSchemaError,
)

FINGERPRINT_A = "provider-management-fingerprint-v1:" + "a" * 64
FINGERPRINT_B = "provider-management-fingerprint-v1:" + "b" * 64
NOW = datetime(2026, 8, 15, tzinfo=UTC)


def command(
    request_id: str,
    *,
    fingerprint: str = FINGERPRINT_A,
    value: ProviderIntentValue = ProviderIntentValue.RUNNING,
    expected_version: int = 0,
) -> ProviderIntentMutationCommand:
    digest = build_provider_intent_request_digest(
        request_id=request_id,
        provider_id="proxmox",
        resource_type="qemu",
        resource_id="110",
        incarnation_fingerprint=fingerprint,
        intent_kind=ProviderIntentKind.MONITORING_EXPECTATION,
        desired_value=value,
        expected_record_version=expected_version,
    )
    return ProviderIntentMutationCommand(
        request_id=request_id,
        request_digest=digest,
        provider_id="proxmox",
        resource_type="qemu",
        resource_id="110",
        incarnation_fingerprint=fingerprint,
        intent_kind=ProviderIntentKind.MONITORING_EXPECTATION,
        desired_value=value,
        expected_record_version=expected_version,
    )


def supersede_command(
    request_id: str,
    intent_id: str,
    expected_version: int,
) -> ProviderIntentSupersedeCommand:
    return ProviderIntentSupersedeCommand(
        request_id=request_id,
        request_digest=build_provider_intent_supersede_digest(
            request_id=request_id,
            intent_id=intent_id,
            expected_record_version=expected_version,
        ),
        intent_id=intent_id,
        expected_record_version=expected_version,
    )


def test_store_requires_a_durable_filesystem_path() -> None:
    with pytest.raises(ValueError, match="durable filesystem path"):
        ProviderIntentStore(":memory:")


def test_store_rejects_symbolic_link_path(tmp_path: Path) -> None:
    target = tmp_path / "target.db"
    target.touch()
    link = tmp_path / "provider_intents.db"
    link.symlink_to(target)
    with pytest.raises(ValueError, match="symbolic link"):
        ProviderIntentStore(link)


def test_store_corrects_existing_file_mode_before_open(tmp_path: Path) -> None:
    path = tmp_path / "provider_intents.db"
    path.touch(mode=0o644)
    path.chmod(0o644)
    ProviderIntentStore(path)
    assert path.stat().st_mode & 0o777 == 0o600


def test_schema_initialization_file_mode_and_restart_durability(
    tmp_path: Path,
) -> None:
    path = tmp_path / "provider_intents.db"
    store = ProviderIntentStore(path)
    created = store.put(command("create-1"), now=NOW)

    assert path.stat().st_mode & 0o777 == 0o600
    with sqlite3.connect(path) as connection:
        assert connection.execute(
            "SELECT schema_version FROM provider_intent_store_meta"
        ).fetchone()[0] == 1
        assert connection.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
        assert connection.execute("PRAGMA synchronous").fetchone()[0] == 2
        assert connection.execute("PRAGMA foreign_keys").fetchone()[0] == 0
        assert connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"

    reopened = ProviderIntentStore(path)
    assert reopened.get_current(created.record.intent_id) == created.record
    with reopened._connect() as connection:
        assert connection.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        assert connection.execute("PRAGMA synchronous").fetchone()[0] == 2
        assert connection.execute("PRAGMA busy_timeout").fetchone()[0] == 5000
        assert connection.execute("PRAGMA journal_mode").fetchone()[0] == "wal"


def test_update_preserves_immutable_history_and_atomic_audit(tmp_path: Path) -> None:
    store = ProviderIntentStore(tmp_path / "provider_intents.db")
    created = store.put(command("create-1"), now=NOW)
    updated = store.put(
        command(
            "update-1",
            value=ProviderIntentValue.STOPPED,
            expected_version=1,
        ),
        now=NOW + timedelta(seconds=1),
    )

    assert updated.record.record_version == 2
    assert [item.intent_value for item in store.history(created.record.intent_id)] == [
        ProviderIntentValue.RUNNING,
        ProviderIntentValue.STOPPED,
    ]
    assert [event.event.value for event in store.audit(created.record.intent_id)] == [
        "created",
        "updated",
    ]


def test_audit_failure_rolls_back_record_and_request(tmp_path: Path) -> None:
    path = tmp_path / "provider_intents.db"
    store = ProviderIntentStore(path)
    created = store.put(command("create-1"), now=NOW)
    with sqlite3.connect(path) as connection:
        connection.execute(
            "CREATE TRIGGER reject_audit BEFORE INSERT ON provider_intent_audit "
            "BEGIN SELECT RAISE(ABORT, 'audit rejected'); END"
        )
    with pytest.raises(ProviderIntentStoreCorruptionError):
        store.put(
            command("update-1", expected_version=1),
            now=NOW + timedelta(seconds=1),
        )
    assert store.history(created.record.intent_id) == (created.record,)
    with sqlite3.connect(path) as connection:
        assert connection.execute(
            "SELECT COUNT(*) FROM provider_intent_requests"
        ).fetchone()[0] == 1


def test_request_result_failure_rolls_back_record_and_audit(tmp_path: Path) -> None:
    path = tmp_path / "provider_intents.db"
    store = ProviderIntentStore(path)
    created = store.put(command("create-1"), now=NOW)
    with sqlite3.connect(path) as connection:
        connection.execute(
            "CREATE TRIGGER reject_request BEFORE INSERT "
            "ON provider_intent_requests "
            "BEGIN SELECT RAISE(ABORT, 'request rejected'); END"
        )
    with pytest.raises(ProviderIntentStoreCorruptionError):
        store.put(
            command("update-1", expected_version=1),
            now=NOW + timedelta(seconds=1),
        )
    assert store.history(created.record.intent_id) == (created.record,)
    assert len(store.audit(created.record.intent_id)) == 1


def test_expected_version_and_idempotency_conflicts(tmp_path: Path) -> None:
    store = ProviderIntentStore(tmp_path / "provider_intents.db")
    request = command("create-1")
    first = store.put(request, now=NOW)
    assert store.put(request, now=NOW + timedelta(seconds=1)) == first

    conflicting_reuse = command(
        "create-1",
        value=ProviderIntentValue.STOPPED,
        expected_version=1,
    )
    with pytest.raises(ProviderIntentStoreConflictError, match="different digest"):
        store.put(conflicting_reuse, now=NOW + timedelta(seconds=2))
    with pytest.raises(ProviderIntentStoreConflictError, match="stale"):
        store.put(
            command("stale-1", expected_version=0),
            now=NOW + timedelta(seconds=3),
        )


def test_idempotent_replay_survives_store_reopen(tmp_path: Path) -> None:
    path = tmp_path / "provider_intents.db"
    request = command("create-1")
    original = ProviderIntentStore(path).put(request, now=NOW)

    reopened = ProviderIntentStore(path)
    assert reopened.put(request, now=NOW + timedelta(seconds=1)) == original
    assert reopened.history(original.record.intent_id) == (original.record,)
    assert len(reopened.audit(original.record.intent_id)) == 1


def test_inconsistent_idempotency_evidence_fails_closed(tmp_path: Path) -> None:
    path = tmp_path / "provider_intents.db"
    store = ProviderIntentStore(path)
    request = command("create-1")
    store.put(request, now=NOW)
    with sqlite3.connect(path) as connection:
        connection.execute(
            "UPDATE provider_intent_audit SET event='updated' WHERE request_id=?",
            (request.request_id,),
        )

    with pytest.raises(ProviderIntentStoreCorruptionError, match="replay evidence"):
        store.put(request, now=NOW + timedelta(seconds=1))


def test_concurrent_same_version_updates_have_one_winner(tmp_path: Path) -> None:
    store = ProviderIntentStore(tmp_path / "provider_intents.db")
    store.put(command("create-1"), now=NOW)
    contenders = (
        command(
            "update-stopped",
            value=ProviderIntentValue.STOPPED,
            expected_version=1,
        ),
        command(
            "update-ignored",
            value=ProviderIntentValue.IGNORED,
            expected_version=1,
        ),
    )

    def attempt(item: ProviderIntentMutationCommand) -> str:
        try:
            return store.put(item, now=NOW + timedelta(seconds=1)).outcome
        except ProviderIntentStoreConflictError:
            return "conflict"

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(attempt, contenders))
    assert sorted(outcomes) == ["conflict", "updated"]


def test_explicit_supersession_is_cas_idempotent_and_terminal(tmp_path: Path) -> None:
    store = ProviderIntentStore(tmp_path / "provider_intents.db")
    created = store.put(command("create-1"), now=NOW)
    request = supersede_command("supersede-1", created.record.intent_id, 1)
    superseded = store.supersede(request, now=NOW + timedelta(seconds=1))

    assert superseded.record.lifecycle is ProviderIntentLifecycle.SUPERSEDED
    assert superseded.record.record_version == 2
    assert store.supersede(request, now=NOW + timedelta(seconds=2)) == superseded
    with pytest.raises(ProviderIntentStoreConflictError, match="superseded"):
        store.put(
            command("update-after", expected_version=2),
            now=NOW + timedelta(seconds=3),
        )
    with pytest.raises(ProviderIntentStoreConflictError):
        store.supersede(
            supersede_command("supersede-stale", created.record.intent_id, 1),
            now=NOW + timedelta(seconds=4),
        )


def test_same_coordinate_different_incarnations_are_independent(tmp_path: Path) -> None:
    store = ProviderIntentStore(tmp_path / "provider_intents.db")
    first = store.put(command("create-a", fingerprint=FINGERPRINT_A), now=NOW)
    second = store.put(
        command(
            "create-b",
            fingerprint=FINGERPRINT_B,
            value=ProviderIntentValue.IGNORED,
        ),
        now=NOW + timedelta(seconds=1),
    )

    assert first.record.intent_id != second.record.intent_id
    assert first.record.lifecycle is ProviderIntentLifecycle.ACTIVE
    assert second.record.lifecycle is ProviderIntentLifecycle.ACTIVE
    assert first.record.intent_value is ProviderIntentValue.RUNNING
    assert second.record.intent_value is ProviderIntentValue.IGNORED
    assert store.history(first.record.intent_id) == (first.record,)
    assert store.history(second.record.intent_id) == (second.record,)


def test_unsupported_schema_and_malformed_records_fail_closed(tmp_path: Path) -> None:
    path = tmp_path / "provider_intents.db"
    store = ProviderIntentStore(path)
    created = store.put(command("create-1"), now=NOW)
    with sqlite3.connect(path) as connection:
        connection.execute(
            "UPDATE provider_intent_store_meta SET schema_version=2"
        )
    with pytest.raises(ProviderIntentStoreSchemaError):
        ProviderIntentStore(path)

    with sqlite3.connect(path) as connection:
        connection.execute(
            "UPDATE provider_intent_store_meta SET schema_version=1"
        )
        connection.execute(
            "UPDATE provider_intent_records SET record_json='{}' "
            "WHERE intent_id=?",
            (created.record.intent_id,),
        )
    with pytest.raises(ProviderIntentStoreCorruptionError):
        store.get_current(created.record.intent_id)


def test_schema_with_missing_audit_foreign_key_fails_closed(tmp_path: Path) -> None:
    path = tmp_path / "provider_intents.db"
    ProviderIntentStore(path)
    with sqlite3.connect(path) as connection:
        connection.execute("DROP TABLE provider_intent_audit")
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
                UNIQUE (intent_id, record_version)
            )
            """
        )
    with pytest.raises(ProviderIntentStoreSchemaError, match="foreign keys"):
        ProviderIntentStore(path)


@pytest.mark.parametrize(
    ("field", "invalid_value"),
    (
        ("intent_value", "paused"),
        ("incarnation_fingerprint", "raw-native-identity"),
        ("incarnation_fingerprint", None),
    ),
)
def test_malformed_persisted_domain_state_fails_closed(
    tmp_path: Path,
    field: str,
    invalid_value: object,
) -> None:
    path = tmp_path / "provider_intents.db"
    store = ProviderIntentStore(path)
    created = store.put(command("create-1"), now=NOW)
    payload = created.record.model_dump(mode="json")
    payload[field] = invalid_value
    with sqlite3.connect(path) as connection:
        connection.execute(
            "UPDATE provider_intent_records SET record_json=? "
            "WHERE intent_id=? AND record_version=1",
            (json.dumps(payload), created.record.intent_id),
        )

    with pytest.raises(ProviderIntentStoreCorruptionError):
        store.get_current(created.record.intent_id)


def test_inconsistent_history_version_sequence_fails_closed(tmp_path: Path) -> None:
    path = tmp_path / "provider_intents.db"
    store = ProviderIntentStore(path)
    created = store.put(command("create-1"), now=NOW)
    store.put(
        command("update-1", expected_version=1),
        now=NOW + timedelta(seconds=1),
    )
    with sqlite3.connect(path) as connection:
        connection.execute("PRAGMA foreign_keys=OFF")
        connection.execute(
            "DELETE FROM provider_intent_records "
            "WHERE intent_id=? AND record_version=1",
            (created.record.intent_id,),
        )

    with pytest.raises(ProviderIntentStoreCorruptionError, match="version chain"):
        store.history(created.record.intent_id)


def test_corrupt_database_file_fails_closed(tmp_path: Path) -> None:
    path = tmp_path / "provider_intents.db"
    path.write_bytes(b"not a sqlite database")
    with pytest.raises(ProviderIntentStoreCorruptionError):
        ProviderIntentStore(path)


def test_store_has_no_forbidden_runtime_dependencies() -> None:
    source = Path(__file__).with_name("store.py").read_text(encoding="utf-8")
    for forbidden in (
        "providers.proxmox",
        "providers.resources",
        "provider_management",
        "provider_actions",
        "execution_candidates",
        "candidate_planning",
        "approval",
        "operator_intents",
        "operator_intent_selector",
        "operational_dispatch",
        "discovery",
        "registry",
        "handler",
        "acl",
    ):
        assert forbidden not in source.casefold()
