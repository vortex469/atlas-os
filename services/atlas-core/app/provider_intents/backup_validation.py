"""Backup-only compatibility validation for P2c and P3 Provider Intent stores."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from app.provider_intents.legacy_import import (
    ActivatedProviderIntentImportCompletionError,
    ActivatedProviderIntentImportMismatchError,
    LegacyPolicyImportResult,
    load_legacy_policy_import,
    validate_activated_provider_intent_store,
)
from app.provider_intents.migration import _validate_p2c_store
from app.provider_intents.store import ProviderIntentStore


def validate_activated_provider_intent_backup_store(
    store_path: Path,
    source_policy_path: Path,
    expected_import_id: str,
) -> None:
    """Validate exact P2c compatibility or exact P3 schema without upgrading."""

    expected_import = load_legacy_policy_import(source_policy_path)
    if expected_import.import_id != expected_import_id:
        raise ActivatedProviderIntentImportMismatchError(
            "expected legacy import ID does not match validated policy"
        )
    if store_path.is_symlink() or not store_path.is_file():
        raise ValueError(
            "backup Provider Intent store must be a regular non-symlink file"
        )
    with sqlite3.connect(
        f"file:{store_path.resolve()}?mode=ro", uri=True
    ) as probe:
        version_row = probe.execute(
            "SELECT schema_version FROM provider_intent_store_meta WHERE singleton=1"
        ).fetchone()
    if version_row is None or version_row[0] not in {1, 2}:
        raise ValueError("backup Provider Intent schema is unsupported")
    if version_row[0] == 2:
        validate_activated_provider_intent_store(
            store_path, source_policy_path, expected_import_id
        )
        return

    connection = sqlite3.connect(
        f"file:{store_path.resolve()}?mode=ro", uri=True, isolation_level=None
    )
    connection.row_factory = sqlite3.Row
    try:
        connection.execute("BEGIN")
        _validate_p2c_store(connection)
        marker = connection.execute(
            "SELECT request_digest, result_json FROM provider_intent_requests "
            "WHERE request_id=?",
            (expected_import.import_id,),
        ).fetchone()
        if marker is None or marker["request_digest"] != expected_import.import_digest:
            raise ActivatedProviderIntentImportCompletionError(
                "expected legacy import completion evidence is missing"
            )
        result = LegacyPolicyImportResult.model_validate_json(marker["result_json"])
        ProviderIntentStore._validate_legacy_import_replay(
            connection, expected_import, result
        )
        connection.commit()
    finally:
        connection.close()
