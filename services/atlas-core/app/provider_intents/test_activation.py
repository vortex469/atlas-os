from __future__ import annotations

import os
import sqlite3
from pathlib import Path

import pytest

from app.config.settings import ProviderIntentActivation, ProviderIntentSettings
from app.provider_intents.activation import (
    ProviderIntentActivationError,
    validate_provider_intent_activation,
)
from app.provider_intents.legacy_import import (
    import_legacy_policy,
    load_legacy_policy_import,
)
from app.provider_intents.read_compatibility import P2cProviderIntentReadStore


def _activated(database: Path, import_id: str) -> ProviderIntentSettings:
    return ProviderIntentSettings(
        activation=ProviderIntentActivation.ACTIVATED,
        database=str(database),
        expected_legacy_import_id=import_id,
    )


def test_inactive_validation_checks_only_configured_path(tmp_path: Path) -> None:
    unrelated = tmp_path / "elsewhere.db"
    unrelated.touch()
    configured = tmp_path / "managed.db"
    settings = ProviderIntentSettings(database=str(configured))
    assert validate_provider_intent_activation(settings) is None
    assert not configured.exists()

    configured.touch()
    with pytest.raises(ProviderIntentActivationError, match="contradicts"):
        validate_provider_intent_activation(settings)
    assert configured.exists()


def test_activated_validation_requires_existing_store_without_creating(
    tmp_path: Path,
) -> None:
    database = tmp_path / "missing.db"
    policy = tmp_path / "policies.yaml"
    policy.write_text("{}\n", encoding="utf-8")
    with pytest.raises(ProviderIntentActivationError):
        validate_provider_intent_activation(
            _activated(
                database,
                "provider-intent-legacy-policy-import-v1:" + "a" * 64,
            ),
            policy_path=policy,
        )
    assert not database.exists()


def test_activated_validation_rejects_symlink_and_special_store(tmp_path: Path) -> None:
    policy = tmp_path / "policies.yaml"
    policy.write_text("{}\n", encoding="utf-8")
    import_id = "provider-intent-legacy-policy-import-v1:" + "a" * 64
    target = tmp_path / "target.db"
    target.touch()
    link = tmp_path / "link.db"
    link.symlink_to(target)
    fifo = tmp_path / "store.fifo"
    os.mkfifo(fifo)
    for path in (link, fifo):
        with pytest.raises(ProviderIntentActivationError):
            validate_provider_intent_activation(
                _activated(path, import_id),
                policy_path=policy,
            )


def test_activated_validation_requires_exact_completed_import_and_accepts_empty(
    tmp_path: Path,
) -> None:
    database = tmp_path / "provider_intents.db"
    policy = tmp_path / "policies.yaml"
    policy.write_text("{}\n", encoding="utf-8")
    completed = import_legacy_policy(policy, database)
    store = validate_provider_intent_activation(
        _activated(database, completed.import_id),
        policy_path=policy,
    )
    assert store is not None
    assert store.get_import_completion(load_legacy_policy_import(policy)) == completed

    with pytest.raises(ProviderIntentActivationError, match="does not match"):
        validate_provider_intent_activation(
            _activated(
                database,
                "provider-intent-legacy-policy-import-v1:" + "f" * 64,
            ),
            policy_path=policy,
        )


def test_activated_p2c_store_remains_readable_without_migration(
    tmp_path: Path,
) -> None:
    database = tmp_path / "provider_intents.db"
    policy = tmp_path / "policies.yaml"
    policy.write_text(
        'proxmox:\n  guests:\n    "110":\n      expected: running\n',
        encoding="utf-8",
    )
    completed = import_legacy_policy(policy, database)
    with sqlite3.connect(database) as connection:
        connection.execute("DROP TABLE provider_intent_operation_audit")
        connection.execute("DROP TABLE provider_intent_operations")
        connection.execute("DROP TABLE provider_intent_active_coordinates")
        connection.execute(
            "UPDATE provider_intent_store_meta SET schema_version=1"
        )

    store = validate_provider_intent_activation(
        _activated(database, completed.import_id),
        policy_path=policy,
    )

    assert store is not None
    assert len(store.read_snapshot().legacy_unbound_records) == 1
    assert not hasattr(store, "mutate_coordinate")
    with sqlite3.connect(database) as connection:
        assert connection.execute(
            "SELECT schema_version FROM provider_intent_store_meta"
        ).fetchone()[0] == 1


def test_activated_p2c_store_checks_integrity_on_open_and_snapshot(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database = tmp_path / "provider_intents.db"
    policy = tmp_path / "policies.yaml"
    policy.write_text("{}\n", encoding="utf-8")
    completed = import_legacy_policy(policy, database)
    with sqlite3.connect(database) as connection:
        connection.execute("DROP TABLE provider_intent_operation_audit")
        connection.execute("DROP TABLE provider_intent_operations")
        connection.execute("DROP TABLE provider_intent_active_coordinates")
        connection.execute(
            "UPDATE provider_intent_store_meta SET schema_version=1"
        )

    integrity_checks = 0
    validate_integrity = P2cProviderIntentReadStore._validate_integrity

    def count_integrity_checks(connection: sqlite3.Connection) -> None:
        nonlocal integrity_checks
        integrity_checks += 1
        validate_integrity(connection)

    monkeypatch.setattr(
        P2cProviderIntentReadStore,
        "_validate_integrity",
        staticmethod(count_integrity_checks),
    )
    store = validate_provider_intent_activation(
        _activated(database, completed.import_id),
        policy_path=policy,
    )
    assert store is not None
    assert integrity_checks == 1

    store.read_snapshot()
    assert integrity_checks == 2


def test_activated_validation_rejects_corrupt_receipt(tmp_path: Path) -> None:
    database = tmp_path / "provider_intents.db"
    policy = tmp_path / "policies.yaml"
    policy.write_text("{}\n", encoding="utf-8")
    completed = import_legacy_policy(policy, database)
    with sqlite3.connect(database) as connection:
        connection.execute(
            "UPDATE provider_intent_requests SET result_json='{}' WHERE request_id=?",
            (completed.import_id,),
        )
    with pytest.raises(ProviderIntentActivationError):
        validate_provider_intent_activation(
            _activated(database, completed.import_id),
            policy_path=policy,
        )


def test_another_valid_import_does_not_satisfy_configured_receipt(
    tmp_path: Path,
) -> None:
    database = tmp_path / "provider_intents.db"
    first = tmp_path / "first.yaml"
    second = tmp_path / "second.yaml"
    first.write_text("{}\n", encoding="utf-8")
    second.write_text(
        'proxmox:\n  guests:\n    "110":\n      expected: running\n',
        encoding="utf-8",
    )
    first_completion = import_legacy_policy(first, database)
    import_legacy_policy(second, database)
    with pytest.raises(ProviderIntentActivationError, match="does not match"):
        validate_provider_intent_activation(
            _activated(database, first_completion.import_id),
            policy_path=second,
        )


def test_activated_validation_rejects_unsupported_or_corrupt_store(
    tmp_path: Path,
) -> None:
    policy = tmp_path / "policies.yaml"
    policy.write_text("{}\n", encoding="utf-8")
    database = tmp_path / "provider_intents.db"
    completion = import_legacy_policy(policy, database)
    with sqlite3.connect(database) as connection:
        connection.execute(
            "UPDATE provider_intent_store_meta SET schema_version=999"
        )
    with pytest.raises(ProviderIntentActivationError):
        validate_provider_intent_activation(
            _activated(database, completion.import_id),
            policy_path=policy,
        )

    database.unlink()
    database.write_bytes(b"not sqlite")
    with pytest.raises(ProviderIntentActivationError):
        validate_provider_intent_activation(
            _activated(database, completion.import_id),
            policy_path=policy,
        )


def test_activation_helper_has_no_production_wiring() -> None:
    main = Path(__file__).parents[1] / "main.py"
    source = main.read_text(encoding="utf-8")
    assert source.index("assert_restore_state_clean(") < source.index(
        "validate_configuration()"
    )
    assert source.index("validate_configuration()") < source.index(
        "validate_provider_intent_activation("
    )
    assert source.index("validate_provider_intent_activation(") < source.index(
        "development_fixture_enabled_and_validated()"
    )
    assert source.index("validate_provider_intent_activation(") < source.index(
        "load_provider_registry()"
    )
