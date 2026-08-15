from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.models.provider_intents import (
    ProviderIntentKind,
    ProviderIntentLifecycle,
    ProviderIntentProvenance,
    build_provider_intent_id,
)
from app.provider_intents.legacy_import import (
    LegacyPolicyImportCommand,
    import_legacy_policy,
    load_legacy_policy_import,
)
from app.provider_intents.store import (
    ProviderIntentStore,
    ProviderIntentStoreConflictError,
    ProviderIntentStoreCorruptionError,
    ProviderIntentStoreError,
)

NOW = datetime(2026, 8, 15, tzinfo=UTC)


def write_policy(path: Path, guests: str) -> None:
    path.write_text(f"proxmox:\n  guests:\n{guests}", encoding="utf-8")


def test_import_is_deterministic_sorted_idempotent_and_non_authoritative(
    tmp_path: Path,
) -> None:
    source = tmp_path / "policies.yaml"
    store_path = tmp_path / "provider_intents.db"
    write_policy(
        source,
        '    "110":\n      expected: ignored\n'
        '    "109":\n      expected: running\n',
    )
    command = load_legacy_policy_import(source)
    assert [entry.resource_id for entry in command.entries] == ["109", "110"]

    first = import_legacy_policy(source, store_path, now=NOW)
    second = import_legacy_policy(source, store_path, now=NOW + timedelta(hours=1))
    assert first.outcome == "imported"
    assert second == first
    assert first.record_count == second.record_count == 2

    store = ProviderIntentStore(store_path)
    with sqlite3.connect(store_path) as connection:
        assert connection.execute(
            "SELECT COUNT(*) FROM provider_intent_records"
        ).fetchone()[0] == 2
        assert connection.execute(
            "SELECT COUNT(*) FROM provider_intent_audit"
        ).fetchone()[0] == 2
    for entry in command.entries:
        with store._connect() as connection:
            result = store._replay(
                connection, entry.source_reference, entry.source_reference
            )
        assert result is not None
        record = result.record
        assert record.lifecycle is ProviderIntentLifecycle.LEGACY_UNBOUND
        assert record.provenance is ProviderIntentProvenance.LEGACY_POLICY_IMPORT
        assert record.resource_type is None
        assert record.incarnation_fingerprint is None


def test_semantic_source_digest_is_canonical_and_scoped_to_imported_subset(
    tmp_path: Path,
) -> None:
    first = tmp_path / "first.yaml"
    second = tmp_path / "second.yaml"
    first.write_text(
        'docker:\n  containers: {}\nproxmox:\n  guests:\n'
        '    "110": {expected: stopped}\n'
        '    "109":\n      expected: running\n',
        encoding="utf-8",
    )
    second.write_text(
        'proxmox: {guests: {"109": {expected: running}, '
        '"110": {expected: stopped}}}\n'
        "docker:\n  containers: {}\n",
        encoding="utf-8",
    )
    canonical = load_legacy_policy_import(first)
    equivalent = load_legacy_policy_import(second)
    assert equivalent.source_policy_digest == canonical.source_policy_digest
    assert equivalent.import_id == canonical.import_id

    second.write_text(
        'proxmox:\n  guests:\n    "109":\n      expected: stopped\n'
        '    "110":\n      expected: stopped\n',
        encoding="utf-8",
    )
    changed = load_legacy_policy_import(second)
    assert changed.source_policy_digest != canonical.source_policy_digest

    second.write_text(
        'proxmox:\n  guests:\n    "109":\n      expected: running\n',
        encoding="utf-8",
    )
    removed = load_legacy_policy_import(second)
    assert removed.source_policy_digest != canonical.source_policy_digest

    second.write_text(
        'proxmox:\n  guests:\n    "110":\n      expected: stopped\n'
        '    "109":\n      expected: running\n'
        "obsidian:\n  minimum_note_count: 999\n",
        encoding="utf-8",
    )
    unrelated = load_legacy_policy_import(second)
    assert unrelated.source_policy_digest == canonical.source_policy_digest


def test_changed_source_preserves_history_and_removal_creates_no_tombstone(
    tmp_path: Path,
) -> None:
    source = tmp_path / "policies.yaml"
    store_path = tmp_path / "provider_intents.db"
    write_policy(
        source,
        '    "109":\n      expected: running\n'
        '    "110":\n      expected: stopped\n',
    )
    original = load_legacy_policy_import(source)
    first_batch = import_legacy_policy(source, store_path, now=NOW)
    write_policy(source, '    "109":\n      expected: stopped\n')
    changed = load_legacy_policy_import(source)
    second_batch = import_legacy_policy(
        source, store_path, now=NOW + timedelta(seconds=1)
    )

    store = ProviderIntentStore(store_path)
    first_109 = original.entries[0]
    with store._connect() as connection:
        initial = store._replay(
            connection, first_109.source_reference, first_109.source_reference
        )
    assert initial is not None
    assert [record.intent_value.value for record in store.history(initial.record.intent_id)] == [
        "running",
        "stopped",
    ]
    first_110 = original.entries[1]
    with store._connect() as connection:
        removed = store._replay(
            connection, first_110.source_reference, first_110.source_reference
        )
    assert removed is not None
    assert len(store.history(removed.record.intent_id)) == 1
    assert changed.import_id != original.import_id
    assert second_batch.import_id == changed.import_id

    write_policy(
        source,
        '    "109":\n      expected: running\n'
        '    "110":\n      expected: stopped\n',
    )
    assert import_legacy_policy(source, store_path) == first_batch


def test_empty_import_has_durable_completion_evidence(tmp_path: Path) -> None:
    source = tmp_path / "policies.yaml"
    source.write_text("{}\n", encoding="utf-8")
    store_path = tmp_path / "provider_intents.db"
    result = import_legacy_policy(source, store_path, now=NOW)
    assert result.record_count == 0
    with sqlite3.connect(store_path) as connection:
        assert connection.execute(
            "SELECT COUNT(*) FROM provider_intent_requests"
        ).fetchone()[0] == 1
        assert connection.execute(
            "SELECT COUNT(*) FROM provider_intent_records"
        ).fetchone()[0] == 0


@pytest.mark.parametrize(
    "content",
    (
        'proxmox:\n  guests:\n    "0109":\n      expected: running\n',
        'proxmox:\n  guests:\n    "109":\n      expected: paused\n',
        (
            'proxmox:\n  guests:\n    "109":\n      expected: running\n'
            '    "109":\n      expected: stopped\n'
        ),
        "proxmox: [\n",
        'proxmox:\n  guests:\n    109:\n      expected: running\n',
        (
            'proxmox:\n  guests:\n    "109":\n      expected: running\n'
            "      display: guest\n"
        ),
        "extra_section: {}\n",
        "defaults: &guest\n  expected: running\nproxmox:\n  guests: {}\n",
        (
            "defaults: &guest\n  expected: running\nproxmox:\n  guests:\n"
            '    "109": *guest\n'
        ),
    ),
)
def test_invalid_policy_or_vmid_fails_before_store_creation(
    tmp_path: Path, content: str
) -> None:
    source = tmp_path / "policies.yaml"
    source.write_text(content, encoding="utf-8")
    store_path = tmp_path / "provider_intents.db"
    with pytest.raises((TypeError, ValueError)):
        import_legacy_policy(source, store_path, now=NOW)
    assert not store_path.exists()


def test_symlink_source_and_store_are_rejected(tmp_path: Path) -> None:
    source = tmp_path / "source.yaml"
    source.write_text("{}\n", encoding="utf-8")
    source_link = tmp_path / "source-link.yaml"
    source_link.symlink_to(source)
    with pytest.raises(ValueError, match="non-symlink"):
        import_legacy_policy(source_link, tmp_path / "new.db")

    target = tmp_path / "target.db"
    target.touch()
    store_link = tmp_path / "store-link.db"
    store_link.symlink_to(target)
    with pytest.raises(ValueError, match="symbolic link"):
        import_legacy_policy(source, store_link)


@pytest.mark.parametrize(
    "trigger",
    (
        (
            "CREATE TRIGGER reject_first BEFORE INSERT ON provider_intent_records "
            "BEGIN SELECT RAISE(ABORT, 'rejected'); END"
        ),
        (
            "CREATE TRIGGER reject_middle BEFORE INSERT ON provider_intent_records "
            "WHEN NEW.record_json LIKE '%\"resource_id\":\"110\"%' "
            "BEGIN SELECT RAISE(ABORT, 'rejected'); END"
        ),
        (
            "CREATE TRIGGER reject_audit BEFORE INSERT ON provider_intent_audit "
            "BEGIN SELECT RAISE(ABORT, 'rejected'); END"
        ),
        (
            "CREATE TRIGGER reject_marker BEFORE INSERT ON provider_intent_requests "
            "WHEN NEW.result_json LIKE '%\"record_count\":%' "
            "BEGIN SELECT RAISE(ABORT, 'rejected'); END"
        ),
    ),
)
def test_batch_failure_rolls_back_records_audit_and_completion(
    tmp_path: Path, trigger: str
) -> None:
    source = tmp_path / "policies.yaml"
    write_policy(
        source,
        '    "109":\n      expected: running\n'
        '    "110":\n      expected: stopped\n',
    )
    store_path = tmp_path / "provider_intents.db"
    ProviderIntentStore(store_path)
    with sqlite3.connect(store_path) as connection:
        connection.execute(trigger)
    with pytest.raises(ProviderIntentStoreCorruptionError):
        import_legacy_policy(source, store_path, now=NOW)
    with sqlite3.connect(store_path) as connection:
        for table in (
            "provider_intent_records",
            "provider_intent_audit",
            "provider_intent_requests",
        ):
            assert connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] == 0


def test_import_identity_collision_fails_closed(tmp_path: Path) -> None:
    source = tmp_path / "policies.yaml"
    write_policy(source, '    "109":\n      expected: running\n')
    command = load_legacy_policy_import(source)
    store = ProviderIntentStore(tmp_path / "provider_intents.db")
    store.import_legacy_policy(command, now=NOW)
    conflicting = command.model_copy(
        update={
            "import_digest": (
                "provider-intent-legacy-policy-import-request-v1:" + "f" * 64
            )
        }
    )
    with pytest.raises(ProviderIntentStoreConflictError, match="different digest"):
        store.import_legacy_policy(conflicting, now=NOW)


def test_command_rejects_tampered_digest(tmp_path: Path) -> None:
    source = tmp_path / "policies.yaml"
    source.write_text("{}\n", encoding="utf-8")
    payload = load_legacy_policy_import(source).model_dump()
    payload["import_digest"] = "provider-intent-legacy-policy-import-request-v1:" + "0" * 64
    with pytest.raises(ValidationError, match="identity or digest"):
        LegacyPolicyImportCommand.model_validate(payload)


def test_cli_output_is_bounded_and_contains_no_policy_values(tmp_path: Path) -> None:
    spaced = tmp_path / "paths with spaces"
    spaced.mkdir()
    source = spaced / "policies file.yaml"
    write_policy(source, '    "109":\n      expected: running\n')
    script = Path(__file__).parents[4] / "scripts" / "atlas-provider-intent-shadow-import"
    result = subprocess.run(
        [sys.executable, str(script), "--source-policy", str(source), "--store", str(spaced / "store file.db")],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    output = json.loads(result.stdout)
    assert set(output) == {"import_id", "record_count", "source_policy_digest", "status"}
    assert "running" not in result.stdout
    assert (spaced / "store file.db").is_file()


@pytest.mark.parametrize("schema_version", (2, 999))
def test_unsupported_or_corrupt_store_fails_before_import(
    tmp_path: Path, schema_version: int
) -> None:
    source = tmp_path / "policies.yaml"
    source.write_text("{}\n", encoding="utf-8")
    store_path = tmp_path / "provider_intents.db"
    ProviderIntentStore(store_path)
    with sqlite3.connect(store_path) as connection:
        connection.execute(
            "UPDATE provider_intent_store_meta SET schema_version=?",
            (schema_version,),
        )
    with pytest.raises(ProviderIntentStoreError):
        import_legacy_policy(source, store_path)


def test_corrupt_store_fails_before_import(tmp_path: Path) -> None:
    source = tmp_path / "policies.yaml"
    source.write_text("{}\n", encoding="utf-8")
    store_path = tmp_path / "provider_intents.db"
    store_path.write_bytes(b"not sqlite")
    with pytest.raises(ProviderIntentStoreCorruptionError):
        import_legacy_policy(source, store_path)


def test_special_source_and_store_targets_are_rejected(tmp_path: Path) -> None:
    source_fifo = tmp_path / "source.fifo"
    os.mkfifo(source_fifo)
    with pytest.raises(ValueError, match="regular non-symlink"):
        import_legacy_policy(source_fifo, tmp_path / "store.db")

    source = tmp_path / "policies.yaml"
    source.write_text("{}\n", encoding="utf-8")
    store_fifo = tmp_path / "store.fifo"
    os.mkfifo(store_fifo)
    with pytest.raises(ValueError, match="regular file"):
        import_legacy_policy(source, store_fifo)


def test_completion_marker_corruption_fails_closed_after_reopen(tmp_path: Path) -> None:
    source = tmp_path / "policies.yaml"
    write_policy(source, '    "109":\n      expected: running\n')
    store_path = tmp_path / "provider_intents.db"
    result = import_legacy_policy(source, store_path, now=NOW)
    with sqlite3.connect(store_path) as connection:
        payload = json.loads(
            connection.execute(
                "SELECT result_json FROM provider_intent_requests WHERE request_id=?",
                (result.import_id,),
            ).fetchone()[0]
        )
        payload["record_count"] = 0
        connection.execute(
            "UPDATE provider_intent_requests SET result_json=? WHERE request_id=?",
            (json.dumps(payload), result.import_id),
        )
    with pytest.raises(ProviderIntentStoreCorruptionError, match="completion evidence"):
        import_legacy_policy(source, store_path, now=NOW)


def test_legacy_and_identity_bound_series_ids_are_separate(tmp_path: Path) -> None:
    source = tmp_path / "policies.yaml"
    write_policy(source, '    "110":\n      expected: running\n')
    legacy = load_legacy_policy_import(source).entries[0]
    legacy_id = build_provider_intent_id(
        provider_id="proxmox",
        resource_type=None,
        resource_id=legacy.resource_id,
        incarnation_fingerprint=None,
        intent_kind=ProviderIntentKind.MONITORING_EXPECTATION,
    )
    authoritative_id = build_provider_intent_id(
        provider_id="proxmox",
        resource_type="qemu",
        resource_id=legacy.resource_id,
        incarnation_fingerprint="provider-management-fingerprint-v1:" + "a" * 64,
        intent_kind=ProviderIntentKind.MONITORING_EXPECTATION,
    )
    assert legacy_id != authoritative_id


def test_import_module_has_no_runtime_authority_dependencies() -> None:
    source = Path(__file__).with_name("legacy_import.py").read_text(encoding="utf-8")
    for forbidden in (
        "providers.proxmox",
        "provider_actions",
        "execution_candidates",
        "approval",
        "operational_dispatch",
        "discovery",
        "selector",
        "execution_gate",
        "handler_registry",
        "httpx",
        "requests",
    ):
        assert forbidden not in source.casefold()
