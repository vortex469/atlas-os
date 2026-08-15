"""Pure contracts for Atlas Core data-backup inventory formats."""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from types import MappingProxyType
from typing import ClassVar

V3_SCHEMA = "atlas-core-data-backup-v3"
V3_FORMAT_VERSION = 3
BACKUP_DIRECTORY_MODE = 0o700
PRIVATE_FILE_MODE = 0o600
_SHA256_PATTERN = re.compile(r"^[a-f0-9]{64}$")


class BackupCompleteness(StrEnum):
    LEGACY_PARTIAL = "legacy_partial"
    COMPLETE = "complete"


class ManagedPath(StrEnum):
    ACTION_HISTORY = "action_history.db"
    PROVIDER_INTELLIGENCE = "provider_intelligence.db"
    OPERATIONAL_DISPATCH = "operational_dispatch.db"
    OPERATOR_INTENTS = "operator_intents.db"
    POLICIES = "config/policies.yaml"
    PROVIDER_CONNECTIONS = "config/provider-connections.yaml"
    PROVIDER_SECRETS = "secrets/provider-connections.yaml"
    OPERATOR_SECURITY_AUDIT = "operator_security_audit.db"
    OPERATOR_SESSIONS = "operator_sessions.db"
    PROVIDER_INTENTS = "provider_intents.db"


MANAGED_PATH_ORDER = tuple(ManagedPath)


class InventoryRole(StrEnum):
    AUTHORITY = "authority"
    SAFETY_LEDGER = "safety_ledger"
    AUDIT = "audit"
    HISTORY = "history"
    DERIVED_HISTORY = "derived_history"
    EPHEMERAL_SECURITY = "ephemeral_security"
    PRE_ACTIVATION = "pre_activation"


class ContentKind(StrEnum):
    SQLITE = "sqlite"
    YAML = "yaml"


class InventoryDisposition(StrEnum):
    REQUIRED_PRESENT = "required_present"
    APPROVED_ABSENT = "approved_absent"
    INVALIDATE_ON_RESTORE = "invalidate_on_restore"


class AbsenceReason(StrEnum):
    OPERATOR_AUTH_NOT_INITIALIZED = "operator_auth_not_initialized"
    PROVIDER_INTENT_STORE_NOT_ACTIVATED = (
        "provider_intent_store_not_activated"
    )


class ProviderIntentActivation(StrEnum):
    NOT_ACTIVATED = "not_activated"
    ACTIVATED = "activated"


@dataclass(frozen=True, slots=True)
class ArtifactMetadata:
    sha256: str
    size: int

    def __post_init__(self) -> None:
        if not isinstance(self.sha256, str) or not _SHA256_PATTERN.fullmatch(
            self.sha256
        ):
            raise ValueError("artifact checksum must be 64 lowercase hex characters")
        if not isinstance(self.size, int) or isinstance(self.size, bool) or self.size < 0:
            raise ValueError("artifact size must be a non-negative integer")


@dataclass(frozen=True, slots=True)
class ManagedInventoryEntry:
    path: ManagedPath
    role: InventoryRole
    content_kind: ContentKind
    disposition: InventoryDisposition
    mode: int
    absence_reason: AbsenceReason | None = None
    artifact: ArtifactMetadata | None = None

    def __post_init__(self) -> None:
        for value, expected_type, label in (
            (self.path, ManagedPath, "managed path"),
            (self.role, InventoryRole, "inventory role"),
            (self.content_kind, ContentKind, "content kind"),
            (self.disposition, InventoryDisposition, "inventory disposition"),
        ):
            if not isinstance(value, expected_type):
                raise TypeError(f"{label} must use its closed enum")
        if self.mode != PRIVATE_FILE_MODE:
            raise ValueError("managed backup artifacts must require mode 0600")
        if self.disposition is InventoryDisposition.REQUIRED_PRESENT:
            if self.absence_reason is not None or self.artifact is None:
                raise ValueError(
                    "present inventory entries require artifact metadata and no absence reason"
                )
        elif self.disposition is InventoryDisposition.APPROVED_ABSENT:
            if not isinstance(self.absence_reason, AbsenceReason) or self.artifact is not None:
                raise ValueError(
                    "absent inventory entries require a controlled reason and no artifact"
                )
        elif self.absence_reason is not None or self.artifact is not None:
            raise ValueError(
                "invalidate-on-restore entries cannot carry an artifact or absence reason"
            )
        _validate_entry_shape(self)

    def to_dict(self) -> dict[str, object]:
        value: dict[str, object] = {
            "path": self.path.value,
            "role": self.role.value,
            "content_kind": self.content_kind.value,
            "disposition": self.disposition.value,
            "mode": self.mode,
        }
        if self.absence_reason is not None:
            value["absence_reason"] = self.absence_reason.value
        if self.artifact is not None:
            value["sha256"] = self.artifact.sha256
            value["size"] = self.artifact.size
        return value


_BASE_SPEC = MappingProxyType(
    {
        ManagedPath.ACTION_HISTORY: (InventoryRole.HISTORY, ContentKind.SQLITE),
        ManagedPath.PROVIDER_INTELLIGENCE: (
            InventoryRole.DERIVED_HISTORY,
            ContentKind.SQLITE,
        ),
        ManagedPath.OPERATIONAL_DISPATCH: (
            InventoryRole.SAFETY_LEDGER,
            ContentKind.SQLITE,
        ),
        ManagedPath.OPERATOR_INTENTS: (
            InventoryRole.AUTHORITY,
            ContentKind.SQLITE,
        ),
        ManagedPath.POLICIES: (InventoryRole.AUTHORITY, ContentKind.YAML),
        ManagedPath.PROVIDER_CONNECTIONS: (
            InventoryRole.AUTHORITY,
            ContentKind.YAML,
        ),
        ManagedPath.PROVIDER_SECRETS: (
            InventoryRole.AUTHORITY,
            ContentKind.YAML,
        ),
        ManagedPath.OPERATOR_SECURITY_AUDIT: (
            InventoryRole.AUDIT,
            ContentKind.SQLITE,
        ),
        ManagedPath.OPERATOR_SESSIONS: (
            InventoryRole.EPHEMERAL_SECURITY,
            ContentKind.SQLITE,
        ),
    }
)


def _validate_entry_shape(entry: ManagedInventoryEntry) -> None:
    if entry.path is ManagedPath.PROVIDER_INTENTS:
        if entry.content_kind is not ContentKind.SQLITE:
            raise ValueError("provider intent inventory must be SQLite")
        valid_shapes = {
            (
                InventoryRole.PRE_ACTIVATION,
                InventoryDisposition.APPROVED_ABSENT,
                AbsenceReason.PROVIDER_INTENT_STORE_NOT_ACTIVATED,
            ),
            (
                InventoryRole.AUTHORITY,
                InventoryDisposition.REQUIRED_PRESENT,
                None,
            ),
        }
        if (entry.role, entry.disposition, entry.absence_reason) not in valid_shapes:
            raise ValueError("provider intent inventory shape is invalid")
        return

    role, content_kind = _BASE_SPEC[entry.path]
    if entry.role is not role or entry.content_kind is not content_kind:
        raise ValueError("managed inventory role or content kind is invalid")
    if entry.path is ManagedPath.OPERATOR_SESSIONS:
        if entry.disposition is not InventoryDisposition.INVALIDATE_ON_RESTORE:
            raise ValueError("operator sessions must be invalidated on restore")
        return
    if entry.path is ManagedPath.OPERATOR_SECURITY_AUDIT:
        if entry.disposition is InventoryDisposition.APPROVED_ABSENT:
            if entry.absence_reason is not AbsenceReason.OPERATOR_AUTH_NOT_INITIALIZED:
                raise ValueError("operator security audit absence reason is invalid")
        elif entry.disposition is not InventoryDisposition.REQUIRED_PRESENT:
            raise ValueError("operator security audit disposition is invalid")
        return
    if entry.disposition is not InventoryDisposition.REQUIRED_PRESENT:
        raise ValueError("required managed inventory path cannot be absent")


@dataclass(frozen=True, slots=True)
class AtlasCoreBackupV3Manifest:
    created_at: str
    provider_intent_activation: ProviderIntentActivation
    inventory: tuple[ManagedInventoryEntry, ...]
    schema: ClassVar[str] = V3_SCHEMA
    format_version: ClassVar[int] = V3_FORMAT_VERSION
    backup_directory_mode: ClassVar[int] = BACKUP_DIRECTORY_MODE

    def __post_init__(self) -> None:
        if not isinstance(self.provider_intent_activation, ProviderIntentActivation):
            raise TypeError("provider intent activation must use its closed enum")
        _validate_created_at(self.created_at)
        paths = tuple(entry.path for entry in self.inventory)
        if paths != MANAGED_PATH_ORDER:
            raise ValueError(
                "v3 inventory must contain every managed path exactly once in canonical order"
            )
        for entry in self.inventory:
            _validate_entry_contract(entry, self.provider_intent_activation)

    @property
    def completeness(self) -> BackupCompleteness:
        return BackupCompleteness.COMPLETE

    def to_dict(self) -> dict[str, object]:
        return {
            "schema": self.schema,
            "format_version": self.format_version,
            "created_at": self.created_at,
            "backup_directory_mode": self.backup_directory_mode,
            "provider_intent_activation": self.provider_intent_activation.value,
            "inventory": [entry.to_dict() for entry in self.inventory],
        }


def build_v3_manifest(
    *,
    created_at: datetime,
    artifacts: Mapping[ManagedPath, ArtifactMetadata],
    operator_security_audit_present: bool,
    provider_intent_activation: ProviderIntentActivation,
) -> AtlasCoreBackupV3Manifest:
    if not isinstance(provider_intent_activation, ProviderIntentActivation):
        raise TypeError("provider intent activation must use its closed enum")
    if not isinstance(operator_security_audit_present, bool):
        raise TypeError("operator security audit presence must be boolean")
    if any(not isinstance(path, ManagedPath) for path in artifacts):
        raise TypeError("artifact paths must use the closed managed-path enum")

    expected_artifacts = set(MANAGED_PATH_ORDER[:7])
    if operator_security_audit_present:
        expected_artifacts.add(ManagedPath.OPERATOR_SECURITY_AUDIT)
    if provider_intent_activation is ProviderIntentActivation.ACTIVATED:
        expected_artifacts.add(ManagedPath.PROVIDER_INTENTS)
    if set(artifacts) != expected_artifacts:
        raise ValueError("v3 artifact set does not match its explicit activation state")

    entries: list[ManagedInventoryEntry] = []
    for path in MANAGED_PATH_ORDER:
        if path is ManagedPath.OPERATOR_SESSIONS:
            entries.append(
                ManagedInventoryEntry(
                    path=path,
                    role=InventoryRole.EPHEMERAL_SECURITY,
                    content_kind=ContentKind.SQLITE,
                    disposition=InventoryDisposition.INVALIDATE_ON_RESTORE,
                    mode=PRIVATE_FILE_MODE,
                )
            )
            continue
        if path is ManagedPath.OPERATOR_SECURITY_AUDIT and not operator_security_audit_present:
            entries.append(
                ManagedInventoryEntry(
                    path=path,
                    role=InventoryRole.AUDIT,
                    content_kind=ContentKind.SQLITE,
                    disposition=InventoryDisposition.APPROVED_ABSENT,
                    absence_reason=AbsenceReason.OPERATOR_AUTH_NOT_INITIALIZED,
                    mode=PRIVATE_FILE_MODE,
                )
            )
            continue
        if (
            path is ManagedPath.PROVIDER_INTENTS
            and provider_intent_activation is ProviderIntentActivation.NOT_ACTIVATED
        ):
            entries.append(
                ManagedInventoryEntry(
                    path=path,
                    role=InventoryRole.PRE_ACTIVATION,
                    content_kind=ContentKind.SQLITE,
                    disposition=InventoryDisposition.APPROVED_ABSENT,
                    absence_reason=(
                        AbsenceReason.PROVIDER_INTENT_STORE_NOT_ACTIVATED
                    ),
                    mode=PRIVATE_FILE_MODE,
                )
            )
            continue
        role, content_kind = (
            (InventoryRole.AUTHORITY, ContentKind.SQLITE)
            if path is ManagedPath.PROVIDER_INTENTS
            else _BASE_SPEC[path]
        )
        entries.append(
            ManagedInventoryEntry(
                path=path,
                role=role,
                content_kind=content_kind,
                disposition=InventoryDisposition.REQUIRED_PRESENT,
                artifact=artifacts[path],
                mode=PRIVATE_FILE_MODE,
            )
        )
    return AtlasCoreBackupV3Manifest(
        created_at=_canonical_timestamp(created_at),
        provider_intent_activation=provider_intent_activation,
        inventory=tuple(entries),
    )


def _validate_entry_contract(
    entry: ManagedInventoryEntry,
    activation: ProviderIntentActivation,
) -> None:
    if entry.path is ManagedPath.PROVIDER_INTENTS:
        expected = (
            (
                InventoryRole.PRE_ACTIVATION,
                InventoryDisposition.APPROVED_ABSENT,
                AbsenceReason.PROVIDER_INTENT_STORE_NOT_ACTIVATED,
            )
            if activation is ProviderIntentActivation.NOT_ACTIVATED
            else (
                InventoryRole.AUTHORITY,
                InventoryDisposition.REQUIRED_PRESENT,
                None,
            )
        )
        if (entry.role, entry.disposition, entry.absence_reason) != expected:
            raise ValueError("provider intent inventory contradicts activation state")


def _canonical_timestamp(value: datetime) -> str:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("backup timestamp must be timezone-aware")
    return value.astimezone(UTC).isoformat()


def _validate_created_at(value: str) -> None:
    if not isinstance(value, str):
        raise TypeError("backup timestamp must be a string")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as error:
        raise ValueError("backup timestamp is invalid") from error
    if parsed.tzinfo is None or parsed.utcoffset() is None or value != parsed.astimezone(UTC).isoformat():
        raise ValueError("backup timestamp must be canonical UTC")


LEGACY_V1_REQUIRED_DATABASES = frozenset(
    {ManagedPath.ACTION_HISTORY.value, ManagedPath.PROVIDER_INTELLIGENCE.value}
)
LEGACY_V2_REQUIRED_DATABASES = LEGACY_V1_REQUIRED_DATABASES
LEGACY_V2_RUNTIME_FILES = frozenset(
    {
        ManagedPath.POLICIES.value,
        ManagedPath.PROVIDER_CONNECTIONS.value,
        ManagedPath.PROVIDER_SECRETS.value,
    }
)


def classify_backup_format(format_version: int) -> BackupCompleteness:
    if format_version in {1, 2}:
        return BackupCompleteness.LEGACY_PARTIAL
    if format_version == V3_FORMAT_VERSION:
        return BackupCompleteness.COMPLETE
    raise ValueError("unsupported backup format version")


def classify_legacy_inventory(
    *,
    format_version: int,
    databases: frozenset[str],
    runtime_files: frozenset[str],
) -> BackupCompleteness:
    if databases != LEGACY_V1_REQUIRED_DATABASES:
        raise ValueError("legacy backup database set is invalid")
    if format_version == 1:
        if runtime_files:
            raise ValueError("v1 backup cannot represent runtime files")
    elif format_version == 2:
        if not runtime_files <= LEGACY_V2_RUNTIME_FILES:
            raise ValueError("v2 backup runtime file set is invalid")
    else:
        raise ValueError("legacy backup format version must be 1 or 2")
    return BackupCompleteness.LEGACY_PARTIAL
