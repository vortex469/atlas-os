"""Atlas Core backup-v3 inventory contract tests."""

from __future__ import annotations

import ast
import json
from dataclasses import replace
from datetime import UTC, datetime
from itertools import combinations
from pathlib import Path
from runpy import run_path

import pytest

from scripts.atlas_data_backup_models import (
    BACKUP_DIRECTORY_MODE,
    LEGACY_V1_REQUIRED_DATABASES,
    LEGACY_V2_REQUIRED_DATABASES,
    LEGACY_V2_RUNTIME_FILES,
    MANAGED_PATH_ORDER,
    PRIVATE_FILE_MODE,
    V3_FORMAT_VERSION,
    V3_SCHEMA,
    AbsenceReason,
    ArtifactMetadata,
    AtlasCoreBackupV3Manifest,
    BackupCompleteness,
    ContentKind,
    InventoryDisposition,
    InventoryRole,
    ManagedInventoryEntry,
    ManagedPath,
    ProviderIntentActivation,
    build_v3_manifest,
    classify_backup_format,
    classify_legacy_inventory,
)

NOW = datetime(2026, 8, 15, tzinfo=UTC)


def artifacts(*, provider_intents: bool = False, security_audit: bool = False):
    paths = set(MANAGED_PATH_ORDER[:7])
    if security_audit:
        paths.add(ManagedPath.OPERATOR_SECURITY_AUDIT)
    if provider_intents:
        paths.add(ManagedPath.PROVIDER_INTENTS)
    return {
        path: ArtifactMetadata(sha256=f"{index:064x}", size=index)
        for index, path in enumerate(sorted(paths, key=lambda item: item.value), start=1)
    }


def manifest(
    *,
    activation: ProviderIntentActivation = ProviderIntentActivation.NOT_ACTIVATED,
    security_audit: bool = False,
) -> AtlasCoreBackupV3Manifest:
    return build_v3_manifest(
        created_at=NOW,
        artifacts=artifacts(
            provider_intents=activation is ProviderIntentActivation.ACTIVATED,
            security_audit=security_audit,
        ),
        operator_security_audit_present=security_audit,
        provider_intent_activation=activation,
    )


def test_v3_identity_inventory_order_and_modes_are_exact() -> None:
    value = manifest()
    encoded = value.to_dict()
    assert encoded["schema"] == V3_SCHEMA == "atlas-core-data-backup-v3"
    assert encoded["format_version"] == V3_FORMAT_VERSION == 3
    assert tuple(entry.path for entry in value.inventory) == MANAGED_PATH_ORDER
    assert [entry["path"] for entry in encoded["inventory"]] == [
        path.value for path in MANAGED_PATH_ORDER
    ]
    assert BACKUP_DIRECTORY_MODE == 0o700
    assert value.backup_directory_mode == 0o700
    assert PRIVATE_FILE_MODE == 0o600
    assert {entry.mode for entry in value.inventory} == {0o600}


@pytest.mark.parametrize("entries", ["duplicate", "missing", "reordered"])
def test_manifest_requires_exact_canonical_inventory(entries: str) -> None:
    value = manifest()
    changed = list(value.inventory)
    if entries == "duplicate":
        changed[-1] = changed[0]
    elif entries == "missing":
        changed.pop()
    else:
        changed[0], changed[1] = changed[1], changed[0]
    with pytest.raises(ValueError, match="every managed path exactly once"):
        replace(value, inventory=tuple(changed))


@pytest.mark.parametrize(
    ("field", "invalid"),
    (
        ("path", "action_history.db-wal"),
        ("path", "../../unknown.db"),
        ("role", "arbitrary"),
        ("content_kind", "binary"),
        ("disposition", "optional"),
    ),
)
def test_entry_rejects_unknown_paths_roles_kinds_and_dispositions(
    field: str,
    invalid: str,
) -> None:
    with pytest.raises(TypeError, match="closed enum"):
        replace(manifest().inventory[0], **{field: invalid})


def test_required_store_cannot_be_absent() -> None:
    value = manifest()
    first = value.inventory[0]
    with pytest.raises(ValueError, match="cannot be absent"):
        replace(
            first,
            disposition=InventoryDisposition.APPROVED_ABSENT,
            artifact=None,
            absence_reason=AbsenceReason.OPERATOR_AUTH_NOT_INITIALIZED,
        )


@pytest.mark.parametrize(
    ("path", "wrong_role"),
    (
        (ManagedPath.OPERATIONAL_DISPATCH, InventoryRole.AUTHORITY),
        (ManagedPath.PROVIDER_INTELLIGENCE, InventoryRole.HISTORY),
        (ManagedPath.POLICIES, InventoryRole.AUDIT),
        (ManagedPath.PROVIDER_CONNECTIONS, InventoryRole.HISTORY),
        (ManagedPath.PROVIDER_SECRETS, InventoryRole.EPHEMERAL_SECURITY),
    ),
)
def test_known_paths_reject_otherwise_valid_wrong_roles(
    path: ManagedPath,
    wrong_role: InventoryRole,
) -> None:
    entry = next(item for item in manifest().inventory if item.path is path)
    with pytest.raises(ValueError, match="role or content kind"):
        replace(entry, role=wrong_role)


def test_arbitrary_absence_reason_is_rejected() -> None:
    audit = manifest().inventory[7]
    with pytest.raises(ValueError, match="controlled reason"):
        replace(audit, absence_reason="missing")


def test_operator_sessions_are_excluded_and_invalidate_on_restore() -> None:
    value = manifest()
    sessions = value.inventory[8]
    assert sessions.path is ManagedPath.OPERATOR_SESSIONS
    assert sessions.role is InventoryRole.EPHEMERAL_SECURITY
    assert sessions.disposition is InventoryDisposition.INVALIDATE_ON_RESTORE
    assert sessions.artifact is None
    with pytest.raises(ValueError, match="operator sessions"):
        ManagedInventoryEntry(
            path=ManagedPath.OPERATOR_SESSIONS,
            role=InventoryRole.EPHEMERAL_SECURITY,
            content_kind=ContentKind.SQLITE,
            disposition=InventoryDisposition.REQUIRED_PRESENT,
            artifact=ArtifactMetadata("a" * 64, 1),
            mode=0o600,
        )


def test_provider_intents_pre_activation_is_explicitly_absent() -> None:
    value = manifest()
    entry = value.inventory[9]
    assert value.provider_intent_activation is ProviderIntentActivation.NOT_ACTIVATED
    assert entry.role is InventoryRole.PRE_ACTIVATION
    assert entry.disposition is InventoryDisposition.APPROVED_ABSENT
    assert entry.absence_reason is AbsenceReason.PROVIDER_INTENT_STORE_NOT_ACTIVATED
    assert entry.artifact is None


def test_pre_activation_rejects_provider_intent_file_metadata() -> None:
    with pytest.raises(ValueError, match="activation state"):
        build_v3_manifest(
            created_at=NOW,
            artifacts=artifacts(provider_intents=True),
            operator_security_audit_present=False,
            provider_intent_activation=ProviderIntentActivation.NOT_ACTIVATED,
        )


def test_activated_provider_intents_are_authoritative_and_required() -> None:
    value = manifest(activation=ProviderIntentActivation.ACTIVATED)
    entry = value.inventory[9]
    assert entry.role is InventoryRole.AUTHORITY
    assert entry.disposition is InventoryDisposition.REQUIRED_PRESENT
    assert entry.artifact is not None
    with pytest.raises(ValueError, match="activation state"):
        build_v3_manifest(
            created_at=NOW,
            artifacts=artifacts(),
            operator_security_audit_present=False,
            provider_intent_activation=ProviderIntentActivation.ACTIVATED,
        )


def test_manifest_and_provider_intent_entry_activation_cannot_disagree() -> None:
    inactive = manifest()
    active = manifest(activation=ProviderIntentActivation.ACTIVATED)
    with pytest.raises(ValueError, match="contradicts activation"):
        replace(inactive, inventory=(*inactive.inventory[:9], active.inventory[9]))
    with pytest.raises(ValueError, match="contradicts activation"):
        replace(
            active,
            inventory=(*active.inventory[:9], inactive.inventory[9]),
        )


def test_security_audit_has_only_controlled_present_or_absent_states() -> None:
    absent = manifest().inventory[7]
    assert absent.disposition is InventoryDisposition.APPROVED_ABSENT
    assert absent.absence_reason is AbsenceReason.OPERATOR_AUTH_NOT_INITIALIZED
    present = manifest(security_audit=True).inventory[7]
    assert present.disposition is InventoryDisposition.REQUIRED_PRESENT
    assert present.artifact is not None
    with pytest.raises(ValueError, match="absence reason"):
        replace(
            absent,
            absence_reason=AbsenceReason.PROVIDER_INTENT_STORE_NOT_ACTIVATED,
        )


@pytest.mark.parametrize("mode", (0o644, 0o400, 0o777))
def test_managed_artifact_mode_cannot_be_caller_weakened_or_changed(mode: int) -> None:
    with pytest.raises(ValueError, match="mode 0600"):
        replace(manifest().inventory[0], mode=mode)


@pytest.mark.parametrize(
    "checksum",
    ("a" * 63, "A" * 64, "sha256:" + "a" * 64, "g" * 64),
)
def test_artifact_checksum_must_be_canonical_sha256(checksum: str) -> None:
    with pytest.raises(ValueError, match="64 lowercase hex"):
        ArtifactMetadata(checksum, 1)


@pytest.mark.parametrize("size", (-1, 1.5, True))
def test_artifact_size_must_be_a_non_negative_integer(size: object) -> None:
    with pytest.raises(ValueError, match="non-negative integer"):
        ArtifactMetadata("a" * 64, size)  # type: ignore[arg-type]


def test_absent_and_excluded_entries_cannot_carry_artifact_metadata() -> None:
    value = manifest()
    for entry in (value.inventory[7], value.inventory[8], value.inventory[9]):
        with pytest.raises(ValueError):
            replace(entry, artifact=ArtifactMetadata("a" * 64, 1))


def test_legacy_v1_v2_contracts_remain_partial_and_unchanged() -> None:
    assert LEGACY_V1_REQUIRED_DATABASES == {
        "action_history.db",
        "provider_intelligence.db",
    }
    assert LEGACY_V2_REQUIRED_DATABASES == LEGACY_V1_REQUIRED_DATABASES
    assert LEGACY_V2_RUNTIME_FILES == {
        "config/policies.yaml",
        "config/provider-connections.yaml",
        "secrets/provider-connections.yaml",
    }
    assert classify_backup_format(1) is BackupCompleteness.LEGACY_PARTIAL
    assert classify_backup_format(2) is BackupCompleteness.LEGACY_PARTIAL
    assert classify_backup_format(3) is BackupCompleteness.COMPLETE


def test_v1_is_database_only_and_v2_accepts_zero_to_three_runtime_files() -> None:
    assert classify_legacy_inventory(
        format_version=1,
        databases=LEGACY_V1_REQUIRED_DATABASES,
        runtime_files=frozenset(),
    ) is BackupCompleteness.LEGACY_PARTIAL
    runtime_paths = tuple(LEGACY_V2_RUNTIME_FILES)
    for count in range(4):
        for subset in combinations(runtime_paths, count):
            assert classify_legacy_inventory(
                format_version=2,
                databases=LEGACY_V2_REQUIRED_DATABASES,
                runtime_files=frozenset(subset),
            ) is BackupCompleteness.LEGACY_PARTIAL
    with pytest.raises(ValueError, match="v1 backup cannot"):
        classify_legacy_inventory(
            format_version=1,
            databases=LEGACY_V1_REQUIRED_DATABASES,
            runtime_files=frozenset({ManagedPath.POLICIES.value}),
        )
    with pytest.raises(ValueError, match="runtime file set"):
        classify_legacy_inventory(
            format_version=2,
            databases=LEGACY_V2_REQUIRED_DATABASES,
            runtime_files=frozenset({"unknown.yaml"}),
        )


def test_production_tool_writes_v3_and_retains_legacy_verification() -> None:
    tool = run_path(str(Path(__file__).with_name("atlas-data-tool.py")))
    assert tool["FORMAT_VERSION"] == 3
    assert tool["SUPPORTED_FORMAT_VERSIONS"] == {1, 2, 3}
    assert frozenset(tool["DATABASES"]) == LEGACY_V2_REQUIRED_DATABASES
    assert frozenset(tool["RUNTIME_FILES"]) == LEGACY_V2_RUNTIME_FILES


def test_manifest_construction_and_serialization_are_deterministic() -> None:
    forward = artifacts()
    reverse = dict(reversed(tuple(forward.items())))
    first = build_v3_manifest(
        created_at=NOW,
        artifacts=forward,
        operator_security_audit_present=False,
        provider_intent_activation=ProviderIntentActivation.NOT_ACTIVATED,
    )
    second = build_v3_manifest(
        created_at=NOW,
        artifacts=reverse,
        operator_security_audit_present=False,
        provider_intent_activation=ProviderIntentActivation.NOT_ACTIVATED,
    )
    assert first == second
    assert json.dumps(first.to_dict(), separators=(",", ":")) == json.dumps(
        second.to_dict(), separators=(",", ":")
    )


def test_contract_module_has_only_standard_library_imports() -> None:
    source = Path(__file__).with_name("atlas_data_backup_models.py").read_text(
        encoding="utf-8"
    )
    imported_roots: set[str] = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            imported_roots.update(alias.name.split(".", 1)[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            imported_roots.add(node.module.split(".", 1)[0])
    assert imported_roots <= {
        "__future__",
        "collections",
        "dataclasses",
        "datetime",
        "enum",
        "re",
        "types",
        "typing",
    }


def test_contract_construction_has_no_filesystem_or_database_side_effect(
    tmp_path,
) -> None:
    before = tuple(tmp_path.iterdir())
    manifest()
    assert tuple(tmp_path.iterdir()) == before == ()
