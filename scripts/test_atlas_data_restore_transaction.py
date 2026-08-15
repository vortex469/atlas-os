"""Failure-injection tests for the pure Atlas backup-v3 restore transaction."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from scripts.atlas_data_backup_models import (
    MANAGED_PATH_ORDER,
    AtlasCoreBackupV3Manifest,
    InventoryDisposition,
)
from scripts.atlas_data_restore_transaction import (
    JOURNAL_NAME,
    TRANSACTION_NAMESPACE,
    RestoreAction,
    RestoreJournalError,
    RestoreRecoveryRequiredError,
    RestoreTransactionError,
    build_restore_plan,
    execute_v3_restore,
    recover_v3_restore,
    verify_v3_target,
)
from scripts.test_atlas_data_tool import (
    TOOL,
    _activate_provider_intents,
    _close,
    _source,
)

create_backup = TOOL["create_backup"]
verify_backup = TOOL["verify_backup"]
ProviderIntentActivation = TOOL["ProviderIntentActivation"]


class SimulatedCrash(BaseException):
    """Bypass handled rollback to leave durable crash evidence."""


def _fixture(
    tmp_path: Path, *, audit: bool = False
) -> tuple[Path, Path, AtlasCoreBackupV3Manifest]:
    source = tmp_path / "source"
    connections = _source(source, audit=audit)
    backup = tmp_path / "backup"
    create_backup(source, backup, operator_auth_initialized=audit)
    _close(connections)
    manifest = AtlasCoreBackupV3Manifest.from_dict(verify_backup(backup))
    target = tmp_path / "target"
    target.mkdir()
    return backup, target, manifest


def _activated_fixture(
    tmp_path: Path,
) -> tuple[Path, Path, AtlasCoreBackupV3Manifest, str]:
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
    _close(connections)
    manifest = AtlasCoreBackupV3Manifest.from_dict(
        verify_backup(backup, expected_legacy_import_id=import_id)
    )
    target = tmp_path / "target"
    target.mkdir()
    return backup, target, manifest, import_id


def _populate_old_generation(target: Path) -> dict[str, tuple[bytes, int]]:
    paths = [path.value for path in MANAGED_PATH_ORDER]
    sqlite_paths = [path for path in paths if path.endswith(".db")]
    paths.extend(
        f"{path}{suffix}"
        for path in sqlite_paths
        for suffix in ("-wal", "-shm")
    )
    snapshot: dict[str, tuple[bytes, int]] = {}
    for index, relative in enumerate(paths):
        path = target / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        content = f"old:{index}:{relative}".encode()
        path.write_bytes(content)
        mode = 0o640 if index % 2 else 0o600
        path.chmod(mode)
        snapshot[relative] = (content, mode)
    return snapshot


def _managed_snapshot(target: Path) -> dict[str, tuple[bytes, int]]:
    managed = {item.value for item in MANAGED_PATH_ORDER}
    result: dict[str, tuple[bytes, int]] = {}
    for path in target.rglob("*"):
        if path.is_file() and TRANSACTION_NAMESPACE not in path.parts:
            relative = path.relative_to(target).as_posix()
            if relative in managed or relative.endswith(("-wal", "-shm")):
                result[relative] = (
                    path.read_bytes(), path.stat().st_mode & 0o777,
                )
    return result


def test_activated_restore_installs_authority_and_removes_sidecars(
    tmp_path: Path,
) -> None:
    backup, target, manifest, import_id = _activated_fixture(tmp_path)
    (target / "provider_intents.db").write_bytes(b"old")
    (target / "provider_intents.db-wal").write_bytes(b"old-wal")
    (target / "provider_intents.db-shm").write_bytes(b"old-shm")
    execute_v3_restore(
        backup,
        target,
        runtime_uid=os.getuid(),
        runtime_gid=os.getgid(),
        expected_legacy_import_id=import_id,
    )
    verify_v3_target(
        target,
        manifest,
        runtime_uid=os.getuid(),
        runtime_gid=os.getgid(),
        expected_legacy_import_id=import_id,
    )
    assert (target / "provider_intents.db").read_bytes() == (
        backup / "provider_intents.db"
    ).read_bytes()
    assert not (target / "provider_intents.db-wal").exists()
    assert not (target / "provider_intents.db-shm").exists()
    with pytest.raises(RuntimeError, match="application validation"):
        verify_v3_target(
            target,
            manifest,
            runtime_uid=os.getuid(),
            runtime_gid=os.getgid(),
            expected_legacy_import_id=(
                "provider-intent-legacy-policy-import-v1:" + "f" * 64
            ),
        )


def test_activated_restore_rolls_back_old_database_and_sidecars(
    tmp_path: Path,
) -> None:
    backup, target, _, import_id = _activated_fixture(tmp_path)
    old = _populate_old_generation(target)

    def fail_after_install(event: str, _index: int | None) -> None:
        if event == "installation_completed":
            raise RuntimeError("injected")

    with pytest.raises(RestoreTransactionError, match="rolled back"):
        execute_v3_restore(
            backup,
            target,
            runtime_uid=os.getuid(),
            runtime_gid=os.getgid(),
            expected_legacy_import_id=import_id,
            failure_hook=fail_after_install,
        )
    assert _managed_snapshot(target) == old


@pytest.mark.parametrize(
    ("failure_event", "failure_index"),
    (
        ("quarantine_artifact", 9),
        ("installation_artifact", 7),
        ("target_verified_journal_fsynced", None),
    ),
)
def test_activated_precommit_failures_restore_exact_old_generation(
    tmp_path: Path,
    failure_event: str,
    failure_index: int | None,
) -> None:
    backup, target, _, import_id = _activated_fixture(tmp_path)
    old = _populate_old_generation(target)

    def fail(event: str, index: int | None) -> None:
        if event == failure_event and index == failure_index:
            raise RuntimeError("injected")

    with pytest.raises(RestoreTransactionError, match="rolled back"):
        execute_v3_restore(
            backup,
            target,
            runtime_uid=os.getuid(),
            runtime_gid=os.getgid(),
            expected_legacy_import_id=import_id,
            failure_hook=fail,
        )
    assert _managed_snapshot(target) == old


@pytest.mark.parametrize(
    ("crash_event", "recovery_result", "keeps_new_generation"),
    (
        ("quarantine_artifact", "rolled_back", False),
        ("installation_artifact", "rolled_back", False),
        ("target_verified_journal_fsynced", "rolled_back", False),
        ("committed_journal_fsynced", "committed_finalized", True),
    ),
)
def test_activated_crash_recovery_respects_commit_durability(
    tmp_path: Path,
    crash_event: str,
    recovery_result: str,
    keeps_new_generation: bool,
) -> None:
    backup, target, manifest, import_id = _activated_fixture(tmp_path)
    old = _populate_old_generation(target)

    def crash(event: str, index: int | None) -> None:
        matches_loop_event = event == crash_event and index in {0, 9}
        if ("artifact" not in crash_event and event == crash_event) or matches_loop_event:
            raise SimulatedCrash

    with pytest.raises(SimulatedCrash):
        execute_v3_restore(
            backup,
            target,
            runtime_uid=os.getuid(),
            runtime_gid=os.getgid(),
            expected_legacy_import_id=import_id,
            failure_hook=crash,
        )
    assert recover_v3_restore(
        target,
        expected_legacy_import_id=import_id,
    ) == recovery_result
    if keeps_new_generation:
        verify_v3_target(
            target,
            manifest,
            runtime_uid=os.getuid(),
            runtime_gid=os.getgid(),
            expected_legacy_import_id=import_id,
        )
    else:
        assert _managed_snapshot(target) == old


@pytest.mark.parametrize("audit", (False, True))
def test_restore_plan_is_exact_for_both_audit_branches(
    tmp_path: Path, audit: bool
) -> None:
    _, _, manifest = _fixture(tmp_path, audit=audit)
    plan = build_restore_plan(manifest)
    assert len(plan) == 24
    assert tuple(item.path for item in plan[:10]) == tuple(
        path.value for path in MANAGED_PATH_ORDER
    )
    actions = {item.path: item.action for item in plan}
    for required in (
        "action_history.db", "provider_intelligence.db", "operational_dispatch.db",
        "operator_intents.db", "config/policies.yaml",
        "config/provider-connections.yaml", "secrets/provider-connections.yaml",
    ):
        assert actions[required] is RestoreAction.INSTALL
    assert actions["operator_security_audit.db"] is (
        RestoreAction.INSTALL if audit else RestoreAction.ABSENT
    )
    assert actions["operator_sessions.db"] is RestoreAction.ABSENT
    assert actions["provider_intents.db"] is RestoreAction.ABSENT
    assert all(item.action is RestoreAction.ABSENT for item in plan[10:])


@pytest.mark.parametrize("audit", (False, True))
def test_successful_restore_is_complete_private_and_preserves_unmanaged_state(
    tmp_path: Path, audit: bool
) -> None:
    backup, target, manifest = _fixture(tmp_path, audit=audit)
    _populate_old_generation(target)
    sentinel = target / "cache" / "unmanaged.marker"
    sentinel.parent.mkdir()
    sentinel.write_bytes(b"preserve")
    execute_v3_restore(
        backup, target, runtime_uid=os.getuid(), runtime_gid=os.getgid(),
        transaction_id="a" * 32,
    )
    verify_v3_target(
        target, manifest, runtime_uid=os.getuid(), runtime_gid=os.getgid()
    )
    assert sentinel.read_bytes() == b"preserve"
    assert not (target / TRANSACTION_NAMESPACE).exists()
    assert not (target / "operator_sessions.db").exists()
    assert not (target / "provider_intents.db").exists()
    assert (target / "operator_security_audit.db").exists() is audit
    assert not list(target.glob("*.db-wal"))
    assert not list(target.glob("*.db-shm"))
    assert (target / "config").stat().st_mode & 0o777 == 0o700
    assert (target / "secrets").stat().st_mode & 0o777 == 0o700
    for entry in manifest.inventory:
        if entry.disposition is InventoryDisposition.REQUIRED_PRESENT:
            metadata = (target / entry.path.value).stat()
            assert metadata.st_mode & 0o777 == 0o600
            assert (metadata.st_uid, metadata.st_gid) == (os.getuid(), os.getgid())


@pytest.mark.parametrize(
    ("event", "index"),
    (
        ("staging_artifact", 0),
        ("prepared_journal_fsynced", None),
        ("quarantine_artifact", 0),
        ("quarantine_completed", None),
        ("installation_artifact", 0),
        ("installation_completed", None),
        ("target_verification_begins", None),
        ("target_verified_journal_fsynced", None),
    ),
)
def test_handled_failure_rolls_back_exact_old_generation(
    tmp_path: Path, event: str, index: int | None
) -> None:
    backup, target, _ = _fixture(tmp_path)
    expected = _populate_old_generation(target)
    sentinel = target / "history" / "sentinel"
    sentinel.parent.mkdir()
    sentinel.write_bytes(b"unmanaged")

    def fail(name: str, item: int | None) -> None:
        if name == event and item == index:
            raise RuntimeError("injected handled failure")

    expected_error = RuntimeError if event == "staging_artifact" else RestoreTransactionError
    with pytest.raises(expected_error):
        execute_v3_restore(
            backup, target, runtime_uid=os.getuid(), runtime_gid=os.getgid(),
            transaction_id="b" * 32, failure_hook=fail,
        )
    assert _managed_snapshot(target) == expected
    assert (target / "config").stat().st_mode & 0o777 == 0o755
    assert (target / "secrets").stat().st_mode & 0o777 == 0o755
    assert sentinel.read_bytes() == b"unmanaged"
    assert not (target / TRANSACTION_NAMESPACE).exists()


@pytest.mark.parametrize(
    ("event", "index"),
    (
        ("prepared_journal_fsynced", None),
        ("quarantine_artifact", 0),
        ("quarantine_completed", None),
        ("installation_artifact", 0),
        ("installation_completed", None),
        ("target_verification_begins", None),
        ("target_verified_journal_fsynced", None),
    ),
)
def test_precommit_crash_recovery_is_exact_and_idempotent(
    tmp_path: Path, event: str, index: int | None
) -> None:
    backup, target, _ = _fixture(tmp_path)
    expected = _populate_old_generation(target)

    def crash(name: str, item: int | None) -> None:
        if name == event and item == index:
            raise SimulatedCrash

    with pytest.raises(SimulatedCrash):
        execute_v3_restore(
            backup, target, runtime_uid=os.getuid(), runtime_gid=os.getgid(),
            transaction_id="c" * 32, failure_hook=crash,
        )
    assert (target / TRANSACTION_NAMESPACE / JOURNAL_NAME).is_file()
    assert recover_v3_restore(target) == "rolled_back"
    assert _managed_snapshot(target) == expected
    assert recover_v3_restore(target) == "no_transaction"


@pytest.mark.parametrize(
    ("event", "index"),
    (("quarantine_artifact", 12), ("installation_artifact", 3)),
)
def test_mid_loop_crash_recovers_in_a_new_process_context(
    tmp_path: Path, event: str, index: int
) -> None:
    backup, target, _ = _fixture(tmp_path)
    expected = _populate_old_generation(target)

    def crash(name: str, item: int | None) -> None:
        if name == event and item == index:
            raise SimulatedCrash

    with pytest.raises(SimulatedCrash):
        execute_v3_restore(
            backup, target, runtime_uid=os.getuid(), runtime_gid=os.getgid(),
            transaction_id="9" * 32, failure_hook=crash,
        )
    assert recover_v3_restore(target) == "rolled_back"
    assert _managed_snapshot(target) == expected


@pytest.mark.parametrize("event", ("committed_journal_fsynced", "cleanup_begins"))
def test_committed_crash_finalizes_without_rollback(
    tmp_path: Path, event: str
) -> None:
    backup, target, manifest = _fixture(tmp_path)
    old = _populate_old_generation(target)

    def crash(name: str, _item: int | None) -> None:
        if name == event:
            raise SimulatedCrash

    with pytest.raises(SimulatedCrash):
        execute_v3_restore(
            backup, target, runtime_uid=os.getuid(), runtime_gid=os.getgid(),
            transaction_id="d" * 32, failure_hook=crash,
        )
    assert recover_v3_restore(target) == "committed_finalized"
    verify_v3_target(
        target, manifest, runtime_uid=os.getuid(), runtime_gid=os.getgid()
    )
    assert _managed_snapshot(target) != old
    assert recover_v3_restore(target) == "no_transaction"


def test_target_verifier_rejects_mixed_generation(tmp_path: Path) -> None:
    backup, target, manifest = _fixture(tmp_path)
    execute_v3_restore(
        backup, target, runtime_uid=os.getuid(), runtime_gid=os.getgid(),
        transaction_id="e" * 32,
    )
    (target / "operator_sessions.db-wal").write_bytes(b"stale")
    with pytest.raises(RestoreTransactionError, match="must be absent"):
        verify_v3_target(
            target, manifest, runtime_uid=os.getuid(), runtime_gid=os.getgid()
        )


def test_target_verifier_independently_detects_installed_byte_corruption(
    tmp_path: Path,
) -> None:
    backup, target, manifest = _fixture(tmp_path)
    execute_v3_restore(
        backup, target, runtime_uid=os.getuid(), runtime_gid=os.getgid(),
        transaction_id="4" * 32,
    )
    (target / "config" / "policies.yaml").write_bytes(b"changed: true\n")
    with pytest.raises(RestoreTransactionError, match="metadata is invalid"):
        verify_v3_target(
            target, manifest, runtime_uid=os.getuid(), runtime_gid=os.getgid()
        )


def test_rollback_restores_original_absence_and_removes_new_parents(
    tmp_path: Path,
) -> None:
    backup, target, _ = _fixture(tmp_path)

    def fail(name: str, _item: int | None) -> None:
        if name == "installation_completed":
            raise RuntimeError("verification unavailable")

    with pytest.raises(RestoreTransactionError, match="rolled back"):
        execute_v3_restore(
            backup, target, runtime_uid=os.getuid(), runtime_gid=os.getgid(),
            transaction_id="6" * 32, failure_hook=fail,
        )
    assert list(target.iterdir()) == []


def test_existing_managed_parents_preserve_unrelated_files_and_metadata(
    tmp_path: Path,
) -> None:
    backup, target, _ = _fixture(tmp_path)
    expected = _populate_old_generation(target)
    sentinels = []
    for name in ("config", "secrets"):
        directory = target / name
        directory.chmod(0o750)
        sentinel = directory / "unrelated.sentinel"
        sentinel.write_bytes(name.encode())
        sentinels.append(sentinel)

    def fail(name: str, _item: int | None) -> None:
        if name == "installation_completed":
            raise RuntimeError("force rollback")

    with pytest.raises(RestoreTransactionError, match="rolled back"):
        execute_v3_restore(
            backup, target, runtime_uid=os.getuid(), runtime_gid=os.getgid(),
            transaction_id="0" * 32, failure_hook=fail,
        )
    assert _managed_snapshot(target) == expected
    assert [path.read_bytes() for path in sentinels] == [b"config", b"secrets"]
    assert all(path.parent.stat().st_mode & 0o777 == 0o750 for path in sentinels)


def test_target_verification_failure_rolls_back_exactly(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    backup, target, _ = _fixture(tmp_path)
    expected = _populate_old_generation(target)
    import scripts.atlas_data_restore_transaction as transaction_module

    def fail_verification(*_args: object, **_kwargs: object) -> None:
        raise RestoreTransactionError("injected target validation failure")

    monkeypatch.setattr(transaction_module, "verify_v3_target", fail_verification)
    with pytest.raises(RestoreTransactionError, match="rolled back"):
        execute_v3_restore(
            backup, target, runtime_uid=os.getuid(), runtime_gid=os.getgid(),
            transaction_id="7" * 32,
        )
    assert _managed_snapshot(target) == expected
    assert not (target / TRANSACTION_NAMESPACE).exists()


@pytest.mark.parametrize(
    "mutation",
    ("malformed", "schema", "phase", "absolute", "traversal", "duplicate", "digest"),
)
def test_corrupt_journal_fails_closed(tmp_path: Path, mutation: str) -> None:
    backup, target, _ = _fixture(tmp_path)

    def crash(name: str, _item: int | None) -> None:
        if name == "prepared_journal_fsynced":
            raise SimulatedCrash

    with pytest.raises(SimulatedCrash):
        execute_v3_restore(
            backup, target, runtime_uid=os.getuid(), runtime_gid=os.getgid(),
            transaction_id="f" * 32, failure_hook=crash,
        )
    journal_path = target / TRANSACTION_NAMESPACE / JOURNAL_NAME
    if mutation == "malformed":
        journal_path.write_text("{", encoding="utf-8")
    else:
        value = json.loads(journal_path.read_text(encoding="utf-8"))
        if mutation == "schema":
            value["version"] = 99
        elif mutation == "phase":
            value["phase"] = "unknown"
        elif mutation == "absolute":
            value["operations"][0]["path"] = "/etc/passwd"
        elif mutation == "traversal":
            value["operations"][0]["path"] = "../escape"
        elif mutation == "duplicate":
            value["operations"][1] = value["operations"][0]
        else:
            value["manifest_digest"] = "0" * 64
        journal_path.write_text(json.dumps(value), encoding="utf-8")
    with pytest.raises((RestoreJournalError, RestoreTransactionError)):
        recover_v3_restore(target)
    assert journal_path.exists()


def test_dangling_journal_symlink_is_unresolved_evidence(tmp_path: Path) -> None:
    _, target, _ = _fixture(tmp_path)
    namespace = target / TRANSACTION_NAMESPACE
    namespace.mkdir(mode=0o700)
    (namespace / JOURNAL_NAME).symlink_to(tmp_path / "missing")
    with pytest.raises(RestoreJournalError, match="unsafe"):
        recover_v3_restore(target)
    assert (namespace / JOURNAL_NAME).is_symlink()


def test_unjournaled_transaction_evidence_requires_recovery(tmp_path: Path) -> None:
    _, target, _ = _fixture(tmp_path)
    namespace = target / TRANSACTION_NAMESPACE
    namespace.mkdir(mode=0o700)
    evidence = namespace / "orphan"
    evidence.write_bytes(b"retain")
    with pytest.raises(RestoreRecoveryRequiredError, match="without a journal"):
        recover_v3_restore(target)
    assert evidence.read_bytes() == b"retain"


def test_target_path_with_symlinked_ancestor_fails_closed(tmp_path: Path) -> None:
    backup, target, _ = _fixture(tmp_path)
    alias = tmp_path / "alias"
    alias.symlink_to(target.parent, target_is_directory=True)
    with pytest.raises(RestoreTransactionError, match="traverse a symlink"):
        execute_v3_restore(
            backup, alias / target.name,
            runtime_uid=os.getuid(), runtime_gid=os.getgid(),
        )


def test_recovery_rejects_replaced_target_inode(tmp_path: Path) -> None:
    backup, target, _ = _fixture(tmp_path)

    def crash(name: str, _item: int | None) -> None:
        if name == "prepared_journal_fsynced":
            raise SimulatedCrash

    with pytest.raises(SimulatedCrash):
        execute_v3_restore(
            backup, target, runtime_uid=os.getuid(), runtime_gid=os.getgid(),
            transaction_id="2" * 32, failure_hook=crash,
        )
    displaced = tmp_path / "displaced-target"
    target.rename(displaced)
    target.mkdir()
    (displaced / TRANSACTION_NAMESPACE).rename(target / TRANSACTION_NAMESPACE)
    with pytest.raises(RestoreJournalError, match="target binding"):
        recover_v3_restore(target)
    assert (target / TRANSACTION_NAMESPACE / JOURNAL_NAME).exists()


def test_managed_and_transaction_symlinks_fail_closed(tmp_path: Path) -> None:
    backup, target, _ = _fixture(tmp_path)
    outside = tmp_path / "outside"
    outside.write_bytes(b"outside")
    (target / "operator_sessions.db").symlink_to(outside)
    with pytest.raises(RestoreTransactionError, match="regular file"):
        execute_v3_restore(
            backup, target, runtime_uid=os.getuid(), runtime_gid=os.getgid(),
            transaction_id="1" * 32,
        )
    assert outside.read_bytes() == b"outside"
    assert not (target / TRANSACTION_NAMESPACE).exists()

    (target / "operator_sessions.db").unlink()
    transaction_outside = tmp_path / "transaction-outside"
    transaction_outside.mkdir()
    (target / TRANSACTION_NAMESPACE).symlink_to(transaction_outside)
    with pytest.raises(RestoreTransactionError, match="unsafe"):
        execute_v3_restore(
            backup, target, runtime_uid=os.getuid(), runtime_gid=os.getgid(),
            transaction_id="2" * 32,
        )
    assert list(transaction_outside.iterdir()) == []


def test_hard_linked_managed_file_fails_closed(tmp_path: Path) -> None:
    backup, target, _ = _fixture(tmp_path)
    managed = target / "operator_sessions.db"
    managed.write_bytes(b"old")
    outside_link = tmp_path / "outside-link"
    os.link(managed, outside_link)
    with pytest.raises(RestoreTransactionError, match="hard links"):
        execute_v3_restore(
            backup, target, runtime_uid=os.getuid(), runtime_gid=os.getgid(),
            transaction_id="3" * 32,
        )
    assert outside_link.read_bytes() == b"old"
    assert managed.read_bytes() == b"old"


def test_cleanup_failure_after_commit_preserves_new_generation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    backup, target, manifest = _fixture(tmp_path)
    import scripts.atlas_data_restore_transaction as transaction_module

    original = transaction_module._remove_transaction_evidence

    def fail_cleanup(*_args: object) -> None:
        raise OSError("cleanup unavailable")

    monkeypatch.setattr(transaction_module, "_remove_transaction_evidence", fail_cleanup)
    with pytest.raises(OSError, match="cleanup unavailable"):
        execute_v3_restore(
            backup, target, runtime_uid=os.getuid(), runtime_gid=os.getgid(),
            transaction_id="3" * 32,
        )
    monkeypatch.setattr(transaction_module, "_remove_transaction_evidence", original)
    assert recover_v3_restore(target) == "committed_finalized"
    verify_v3_target(
        target, manifest, runtime_uid=os.getuid(), runtime_gid=os.getgid()
    )


def test_partially_removed_committed_evidence_recovers_without_rollback(
    tmp_path: Path,
) -> None:
    backup, target, manifest = _fixture(tmp_path)

    def crash(name: str, _item: int | None) -> None:
        if name == "cleanup_begins":
            raise SimulatedCrash

    with pytest.raises(SimulatedCrash):
        execute_v3_restore(
            backup, target, runtime_uid=os.getuid(), runtime_gid=os.getgid(),
            transaction_id="a" * 32, failure_hook=crash,
        )
    transaction = target / TRANSACTION_NAMESPACE / ("a" * 32)
    for path in sorted(transaction.rglob("*"), reverse=True)[:2]:
        if path.is_file():
            path.unlink()
    assert recover_v3_restore(target) == "committed_finalized"
    verify_v3_target(target, manifest, runtime_uid=os.getuid(), runtime_gid=os.getgid())


def test_staging_rejects_corruption_without_touching_target(tmp_path: Path) -> None:
    backup, target, _ = _fixture(tmp_path)
    expected = _populate_old_generation(target)
    (backup / "operator_intents.db").write_bytes(b"not sqlite")
    with pytest.raises(RuntimeError):
        execute_v3_restore(
            backup, target, runtime_uid=os.getuid(), runtime_gid=os.getgid(),
            transaction_id="4" * 32,
        )
    assert _managed_snapshot(target) == expected
    assert not (target / TRANSACTION_NAMESPACE).exists()


def test_target_drift_before_quarantine_requires_recovery(tmp_path: Path) -> None:
    backup, target, _ = _fixture(tmp_path)
    _populate_old_generation(target)

    def mutate(name: str, _item: int | None) -> None:
        if name == "prepared_journal_fsynced":
            (target / "action_history.db").write_bytes(b"external drift")

    with pytest.raises(RestoreRecoveryRequiredError):
        execute_v3_restore(
            backup, target, runtime_uid=os.getuid(), runtime_gid=os.getgid(),
            transaction_id="7" * 32, failure_hook=mutate,
        )
    assert (target / TRANSACTION_NAMESPACE / JOURNAL_NAME).exists()


def test_missing_rollback_artifact_fails_recovery_without_guessing(
    tmp_path: Path,
) -> None:
    backup, target, _ = _fixture(tmp_path)
    _populate_old_generation(target)

    def crash(name: str, index: int | None) -> None:
        if name == "installation_artifact" and index == 0:
            raise SimulatedCrash

    with pytest.raises(SimulatedCrash):
        execute_v3_restore(
            backup, target, runtime_uid=os.getuid(), runtime_gid=os.getgid(),
            transaction_id="5" * 32, failure_hook=crash,
        )
    rollback = (
        target / TRANSACTION_NAMESPACE / ("5" * 32) / "rollback"
        / "action_history.db"
    )
    rollback.unlink()
    with pytest.raises(RestoreRecoveryRequiredError):
        recover_v3_restore(target)
    assert (target / TRANSACTION_NAMESPACE / JOURNAL_NAME).exists()


def test_unexpected_transaction_content_preserves_evidence(tmp_path: Path) -> None:
    backup, target, _ = _fixture(tmp_path)

    def crash(name: str, _item: int | None) -> None:
        if name == "prepared_journal_fsynced":
            raise SimulatedCrash

    with pytest.raises(SimulatedCrash):
        execute_v3_restore(
            backup, target, runtime_uid=os.getuid(), runtime_gid=os.getgid(),
            transaction_id="e" * 32, failure_hook=crash,
        )
    transaction = target / TRANSACTION_NAMESPACE / ("e" * 32)
    unexpected = transaction / "unexpected"
    unexpected.write_bytes(b"retain")
    with pytest.raises(RestoreJournalError, match="unexpected evidence"):
        recover_v3_restore(target)
    assert unexpected.read_bytes() == b"retain"


def test_interrupted_rollback_recovery_can_be_retried(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    backup, target, _ = _fixture(tmp_path)
    expected = _populate_old_generation(target)

    def crash(name: str, index: int | None) -> None:
        if name == "installation_artifact" and index == 0:
            raise SimulatedCrash

    with pytest.raises(SimulatedCrash):
        execute_v3_restore(
            backup, target, runtime_uid=os.getuid(), runtime_gid=os.getgid(),
            transaction_id="8" * 32, failure_hook=crash,
        )
    original_replace = os.replace
    rollback_moves = 0

    def fail_second_rollback_move(source: object, destination: object) -> None:
        nonlocal rollback_moves
        if f"{TRANSACTION_NAMESPACE}/{('8' * 32)}/rollback" in str(source):
            rollback_moves += 1
            if rollback_moves == 2:
                raise OSError("simulated recovery interruption")
        original_replace(source, destination)

    monkeypatch.setattr(os, "replace", fail_second_rollback_move)
    with pytest.raises(RestoreRecoveryRequiredError):
        recover_v3_restore(target)
    monkeypatch.setattr(os, "replace", original_replace)
    assert recover_v3_restore(target) == "rolled_back"
    assert _managed_snapshot(target) == expected
    assert recover_v3_restore(target) == "no_transaction"


def test_production_restore_adopts_v3_transactionally(tmp_path: Path) -> None:
    backup, target, _ = _fixture(tmp_path)
    restore_backup = TOOL["restore_backup"]
    restore_backup(backup, target)
    assert not (target / TRANSACTION_NAMESPACE).exists()
    assert not (target / "operator_sessions.db").exists()
    assert not (target / "provider_intents.db").exists()
