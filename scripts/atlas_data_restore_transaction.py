"""Pure transactional restore engine for complete Atlas Core backup v3 sets.

This module is intentionally not wired into the production restore wrapper yet.
It operates only on an already verified backup, an explicit target directory,
and explicit runtime ownership.
"""

from __future__ import annotations

import json
import os
import re
import runpy
import shutil
import stat
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from enum import StrEnum
from hashlib import sha256
from pathlib import Path, PurePosixPath
from typing import Any
from uuid import uuid4

try:
    from atlas_data_backup_models import (
        MANAGED_PATH_ORDER,
        PRIVATE_FILE_MODE,
        ArtifactMetadata,
        AtlasCoreBackupV3Manifest,
        ContentKind,
        InventoryDisposition,
        ManagedPath,
        ProviderIntentActivation,
    )
except ModuleNotFoundError:
    from scripts.atlas_data_backup_models import (
        MANAGED_PATH_ORDER,
        PRIVATE_FILE_MODE,
        ArtifactMetadata,
        AtlasCoreBackupV3Manifest,
        ContentKind,
        InventoryDisposition,
        ManagedPath,
        ProviderIntentActivation,
    )

JOURNAL_SCHEMA = "atlas-core-data-restore-journal-v1"
JOURNAL_VERSION = 1
TRANSACTION_NAMESPACE = ".atlas-restore"
JOURNAL_NAME = "journal.json"
TRANSACTION_ID_PATTERN = re.compile(r"^[a-f0-9]{32}$")
PRIVATE_DIRECTORY_MODE = 0o700


class RestorePhase(StrEnum):
    PREPARED = "prepared"
    OLD_GENERATION_QUARANTINED = "old_generation_quarantined"
    NEW_GENERATION_INSTALLED = "new_generation_installed"
    TARGET_VERIFIED = "target_verified"
    COMMITTED = "committed"


_PHASE_ORDER = tuple(RestorePhase)


class RestoreAction(StrEnum):
    INSTALL = "install"
    ABSENT = "absent"


class RestoreTransactionError(RuntimeError):
    """Base failure for v3 transactional restore."""


class RestoreRecoveryRequiredError(RestoreTransactionError):
    """Raised when rollback cannot be proven and evidence must be retained."""


class RestoreJournalError(RestoreRecoveryRequiredError):
    """Raised when durable transaction evidence is invalid."""


FailureHook = Callable[[str, int | None], None]


@dataclass(frozen=True, slots=True)
class FileState:
    exists: bool
    sha256: str | None = None
    size: int | None = None
    mode: int | None = None
    uid: int | None = None
    gid: int | None = None

    def __post_init__(self) -> None:
        values = (self.sha256, self.size, self.mode, self.uid, self.gid)
        if self.exists:
            if (
                not isinstance(self.sha256, str)
                or not re.fullmatch(r"[a-f0-9]{64}", self.sha256)
                or not all(isinstance(value, int) for value in values[1:])
            ):
                raise RestoreJournalError("existing file state metadata is invalid")
            if (
                self.size < 0  # type: ignore[operator]
                or not 0 <= self.mode <= 0o777  # type: ignore[operator]
                or self.uid < 0  # type: ignore[operator]
                or self.gid < 0  # type: ignore[operator]
            ):
                raise RestoreJournalError("existing file state values are invalid")
        elif any(value is not None for value in values):
            raise RestoreJournalError("absent file state cannot carry metadata")

    def to_dict(self) -> dict[str, object]:
        value: dict[str, object] = {"exists": self.exists}
        if self.exists:
            value.update(
                sha256=self.sha256,
                size=self.size,
                mode=self.mode,
                uid=self.uid,
                gid=self.gid,
            )
        return value

    @classmethod
    def from_dict(cls, value: object) -> FileState:
        if not isinstance(value, dict):
            raise RestoreJournalError("file state must be an object")
        expected = (
            {"exists", "sha256", "size", "mode", "uid", "gid"}
            if value.get("exists") is True
            else {"exists"}
        )
        if set(value) != expected or not isinstance(value.get("exists"), bool):
            raise RestoreJournalError("file state fields are invalid")
        return cls(**value)  # type: ignore[arg-type]


@dataclass(frozen=True, slots=True)
class DirectoryState:
    path: str
    exists: bool
    mode: int | None = None
    uid: int | None = None
    gid: int | None = None

    def __post_init__(self) -> None:
        _validate_relative_path(self.path, allowed={"config", "secrets"})
        metadata = (self.mode, self.uid, self.gid)
        if self.exists and not all(isinstance(value, int) for value in metadata):
            raise RestoreJournalError("directory state metadata is invalid")
        if self.exists and (
            not 0 <= self.mode <= 0o777  # type: ignore[operator]
            or self.uid < 0  # type: ignore[operator]
            or self.gid < 0  # type: ignore[operator]
        ):
            raise RestoreJournalError("directory state values are invalid")
        if not self.exists and any(value is not None for value in metadata):
            raise RestoreJournalError("absent directory state cannot carry metadata")

    def to_dict(self) -> dict[str, object]:
        value: dict[str, object] = {"path": self.path, "exists": self.exists}
        if self.exists:
            value.update(mode=self.mode, uid=self.uid, gid=self.gid)
        return value

    @classmethod
    def from_dict(cls, value: object) -> DirectoryState:
        if not isinstance(value, dict):
            raise RestoreJournalError("directory state must be an object")
        expected = (
            {"path", "exists", "mode", "uid", "gid"}
            if value.get("exists") is True
            else {"path", "exists"}
        )
        if set(value) != expected or not isinstance(value.get("exists"), bool):
            raise RestoreJournalError("directory state fields are invalid")
        return cls(**value)  # type: ignore[arg-type]


@dataclass(frozen=True, slots=True)
class RestoreOperation:
    path: str
    action: RestoreAction
    artifact: ArtifactMetadata | None
    original: FileState

    def __post_init__(self) -> None:
        _validate_relative_path(self.path, allowed=_MANAGED_TRANSACTION_PATHS)
        if not isinstance(self.action, RestoreAction):
            raise RestoreJournalError("restore action must use its closed enum")
        if (self.action is RestoreAction.INSTALL) != (self.artifact is not None):
            raise RestoreJournalError("install action and artifact metadata disagree")

    def to_dict(self) -> dict[str, object]:
        value: dict[str, object] = {
            "path": self.path,
            "action": self.action.value,
            "original": self.original.to_dict(),
        }
        if self.artifact is not None:
            value["artifact"] = {
                "sha256": self.artifact.sha256,
                "size": self.artifact.size,
            }
        return value

    @classmethod
    def from_dict(cls, value: object) -> RestoreOperation:
        if not isinstance(value, dict):
            raise RestoreJournalError("restore operation must be an object")
        common = {"path", "action", "original"}
        if set(value) not in {frozenset(common), frozenset(common | {"artifact"})}:
            raise RestoreJournalError("restore operation fields are invalid")
        try:
            action = RestoreAction(value["action"])
            artifact_value = value.get("artifact")
            artifact = None
            if artifact_value is not None:
                if not isinstance(artifact_value, dict) or set(artifact_value) != {
                    "sha256", "size",
                }:
                    raise RestoreJournalError("restore artifact metadata is invalid")
                artifact = ArtifactMetadata(**artifact_value)  # type: ignore[arg-type]
            return cls(
                path=value["path"],  # type: ignore[arg-type]
                action=action,
                artifact=artifact,
                original=FileState.from_dict(value["original"]),
            )
        except (TypeError, ValueError) as error:
            raise RestoreJournalError("restore operation values are invalid") from error


@dataclass(frozen=True, slots=True)
class RestoreJournal:
    transaction_id: str
    target_path: str
    target_device: int
    target_inode: int
    runtime_uid: int
    runtime_gid: int
    phase: RestorePhase
    manifest: AtlasCoreBackupV3Manifest
    manifest_digest: str
    operations: tuple[RestoreOperation, ...]
    directories: tuple[DirectoryState, ...]

    def __post_init__(self) -> None:
        if not TRANSACTION_ID_PATTERN.fullmatch(self.transaction_id):
            raise RestoreJournalError("transaction ID is invalid")
        if not Path(self.target_path).is_absolute():
            raise RestoreJournalError("journal target binding must be absolute")
        if (
            not isinstance(self.target_device, int)
            or isinstance(self.target_device, bool)
            or self.target_device < 0
            or not isinstance(self.target_inode, int)
            or isinstance(self.target_inode, bool)
            or self.target_inode <= 0
        ):
            raise RestoreJournalError("journal target identity is invalid")
        _validate_runtime_identity(self.runtime_uid, self.runtime_gid)
        if not isinstance(self.phase, RestorePhase):
            raise RestoreJournalError("journal phase is invalid")
        if self.manifest.provider_intent_activation is not ProviderIntentActivation.NOT_ACTIVATED:
            raise RestoreJournalError("P2b-3a requires pre-activation Provider Intent state")
        if self.manifest_digest != _manifest_digest(self.manifest):
            raise RestoreJournalError("journal manifest digest is invalid")
        expected_paths = tuple(operation.path for operation in self.operations)
        if expected_paths != tuple(_MANAGED_TRANSACTION_PATHS):
            raise RestoreJournalError("journal operation plan is not canonical")
        if tuple(item.path for item in self.directories) != ("config", "secrets"):
            raise RestoreJournalError("journal directory inventory is not canonical")
        plan = build_restore_plan(self.manifest)
        for operation, planned in zip(self.operations, plan, strict=True):
            if operation.path != planned.path or operation.action is not planned.action:
                raise RestoreJournalError("journal operations contradict the manifest")
            if operation.artifact != planned.artifact:
                raise RestoreJournalError("journal artifact metadata contradicts the manifest")

    def to_dict(self) -> dict[str, object]:
        return {
            "schema": JOURNAL_SCHEMA,
            "version": JOURNAL_VERSION,
            "transaction_id": self.transaction_id,
            "target_path": self.target_path,
            "target_device": self.target_device,
            "target_inode": self.target_inode,
            "runtime_uid": self.runtime_uid,
            "runtime_gid": self.runtime_gid,
            "phase": self.phase.value,
            "manifest": self.manifest.to_dict(),
            "manifest_digest": self.manifest_digest,
            "operations": [item.to_dict() for item in self.operations],
            "directories": [item.to_dict() for item in self.directories],
        }

    @classmethod
    def from_dict(cls, value: object) -> RestoreJournal:
        fields = {
            "schema", "version", "transaction_id", "target_path", "target_device",
            "target_inode", "runtime_uid", "runtime_gid", "phase", "manifest",
            "manifest_digest", "operations", "directories",
        }
        if not isinstance(value, dict) or set(value) != fields:
            raise RestoreJournalError("restore journal fields are invalid")
        if value["schema"] != JOURNAL_SCHEMA or value["version"] != JOURNAL_VERSION:
            raise RestoreJournalError("restore journal identity is unsupported")
        if not isinstance(value["operations"], list) or not isinstance(
            value["directories"], list
        ):
            raise RestoreJournalError("restore journal inventories are invalid")
        try:
            return cls(
                transaction_id=value["transaction_id"],  # type: ignore[arg-type]
                target_path=value["target_path"],  # type: ignore[arg-type]
                target_device=value["target_device"],  # type: ignore[arg-type]
                target_inode=value["target_inode"],  # type: ignore[arg-type]
                runtime_uid=value["runtime_uid"],  # type: ignore[arg-type]
                runtime_gid=value["runtime_gid"],  # type: ignore[arg-type]
                phase=RestorePhase(value["phase"]),
                manifest=AtlasCoreBackupV3Manifest.from_dict(value["manifest"]),
                manifest_digest=value["manifest_digest"],  # type: ignore[arg-type]
                operations=tuple(
                    RestoreOperation.from_dict(item) for item in value["operations"]
                ),
                directories=tuple(
                    DirectoryState.from_dict(item) for item in value["directories"]
                ),
            )
        except (TypeError, ValueError) as error:
            raise RestoreJournalError("restore journal values are invalid") from error


@dataclass(frozen=True, slots=True)
class PlannedOperation:
    path: str
    action: RestoreAction
    artifact: ArtifactMetadata | None


_SQLITE_PATHS = tuple(
    path.value
    for path in MANAGED_PATH_ORDER
    if path not in {
        ManagedPath.POLICIES,
        ManagedPath.PROVIDER_CONNECTIONS,
        ManagedPath.PROVIDER_SECRETS,
    }
)
_MANAGED_TRANSACTION_PATHS = tuple(
    [path.value for path in MANAGED_PATH_ORDER]
    + [f"{path}{suffix}" for path in _SQLITE_PATHS for suffix in ("-wal", "-shm")]
)


def build_restore_plan(
    manifest: AtlasCoreBackupV3Manifest,
) -> tuple[PlannedOperation, ...]:
    manifest = _normalize_manifest(manifest)
    if manifest.provider_intent_activation is not ProviderIntentActivation.NOT_ACTIVATED:
        raise RestoreTransactionError("P2b-3a cannot restore activated Provider Intent state")
    entries = {entry.path.value: entry for entry in manifest.inventory}
    plan: list[PlannedOperation] = []
    for relative_path in _MANAGED_TRANSACTION_PATHS:
        entry = entries.get(relative_path)
        install = (
            entry is not None
            and entry.disposition is InventoryDisposition.REQUIRED_PRESENT
        )
        plan.append(
            PlannedOperation(
                path=relative_path,
                action=RestoreAction.INSTALL if install else RestoreAction.ABSENT,
                artifact=entry.artifact if install else None,
            )
        )
    return tuple(plan)


def execute_v3_restore(
    backup: Path,
    target: Path,
    *,
    runtime_uid: int,
    runtime_gid: int,
    transaction_id: str | None = None,
    failure_hook: FailureHook | None = None,
) -> None:
    tool = _tool_functions()
    manifest_data = tool["verify_backup"](backup)
    manifest = AtlasCoreBackupV3Manifest.from_dict(manifest_data)
    _validate_runtime_identity(runtime_uid, runtime_gid)
    target = _validate_target_root(target)
    namespace = _namespace(target)
    if (namespace / JOURNAL_NAME).exists() or (namespace / JOURNAL_NAME).is_symlink():
        raise RestoreRecoveryRequiredError("an unresolved restore journal exists")
    if namespace.exists() or namespace.is_symlink():
        _assert_private_directory(namespace, runtime_uid, runtime_gid)
        if any(namespace.iterdir()):
            raise RestoreRecoveryRequiredError(
                "restore namespace contains unjournaled transaction evidence"
            )
    transaction_id = transaction_id or uuid4().hex
    if not TRANSACTION_ID_PATTERN.fullmatch(transaction_id):
        raise RestoreTransactionError("transaction ID is invalid")
    transaction = namespace / transaction_id
    if transaction.exists() or transaction.is_symlink():
        raise RestoreRecoveryRequiredError("restore transaction path already exists")
    stage = transaction / "stage"
    rollback = transaction / "rollback"
    try:
        _create_private_directory(namespace, runtime_uid, runtime_gid)
        _create_private_directory(transaction, runtime_uid, runtime_gid)
        _create_private_directory(stage, runtime_uid, runtime_gid)
        _create_private_directory(rollback, runtime_uid, runtime_gid)
        plan = build_restore_plan(manifest)
        _stage(
            backup, target, stage, plan, manifest, runtime_uid, runtime_gid,
            tool, failure_hook,
        )
        operations = tuple(
            RestoreOperation(
                path=item.path,
                action=item.action,
                artifact=item.artifact,
                original=_capture_file_state(_safe_target_path(target, item.path)),
            )
            for item in plan
        )
        directories = tuple(
            _capture_directory_state(target, name) for name in ("config", "secrets")
        )
        target_stat = target.stat()
        journal = RestoreJournal(
            transaction_id=transaction_id,
            target_path=str(target),
            target_device=target_stat.st_dev,
            target_inode=target_stat.st_ino,
            runtime_uid=runtime_uid,
            runtime_gid=runtime_gid,
            phase=RestorePhase.PREPARED,
            manifest=manifest,
            manifest_digest=_manifest_digest(manifest),
            operations=operations,
            directories=directories,
        )
        _write_journal(namespace, journal)
    except BaseException:
        if not (namespace / JOURNAL_NAME).exists():
            _cleanup_unjournaled_transaction(transaction, namespace)
        raise

    try:
        _emit(failure_hook, "prepared_journal_fsynced", None)
        _quarantine(target, rollback, journal, failure_hook)
        journal = _transition(namespace, journal, RestorePhase.OLD_GENERATION_QUARANTINED)
        _emit(failure_hook, "quarantine_completed", None)
        _install(target, stage, journal, runtime_uid, runtime_gid, failure_hook)
        journal = _transition(namespace, journal, RestorePhase.NEW_GENERATION_INSTALLED)
        _emit(failure_hook, "installation_completed", None)
        _emit(failure_hook, "target_verification_begins", None)
        verify_v3_target(
            target, manifest, runtime_uid=runtime_uid, runtime_gid=runtime_gid,
            active_transaction_id=transaction_id,
        )
        journal = _transition(namespace, journal, RestorePhase.TARGET_VERIFIED)
        _emit(failure_hook, "target_verified_journal_fsynced", None)
        journal = _transition(namespace, journal, RestorePhase.COMMITTED)
        _emit(failure_hook, "committed_journal_fsynced", None)
    except Exception as error:
        if journal.phase is RestorePhase.COMMITTED:
            raise RestoreTransactionError(
                "v3 restore committed but cleanup/finalization is incomplete"
            ) from error
        try:
            _rollback(target, namespace, journal)
        except Exception as rollback_error:
            raise RestoreRecoveryRequiredError(
                "restore failed and exact rollback could not be proven"
            ) from rollback_error
        raise RestoreTransactionError("v3 restore transaction rolled back") from error

    _emit(failure_hook, "cleanup_begins", None)
    _cleanup_committed(target, namespace, journal)


def recover_v3_restore(target: Path) -> str:
    target = _validate_target_root(target)
    namespace = _namespace(target)
    journal_path = namespace / JOURNAL_NAME
    if not journal_path.exists() and not journal_path.is_symlink():
        if (namespace.exists() or namespace.is_symlink()) and (
            namespace.is_symlink()
            or not namespace.is_dir()
            or any(namespace.iterdir())
        ):
            raise RestoreRecoveryRequiredError(
                "restore namespace contains evidence without a journal"
            )
        return "no_transaction"
    journal = _load_journal(target)
    if journal.phase is RestorePhase.COMMITTED:
        verify_v3_target(
            target,
            journal.manifest,
            runtime_uid=journal.runtime_uid,
            runtime_gid=journal.runtime_gid,
            active_transaction_id=journal.transaction_id,
        )
        _cleanup_committed(target, namespace, journal)
        return "committed_finalized"
    try:
        _rollback(target, namespace, journal)
    except RestoreRecoveryRequiredError:
        raise
    except Exception as error:
        raise RestoreRecoveryRequiredError(
            "crash rollback did not complete; transaction evidence is retained"
        ) from error
    return "rolled_back"


def verify_v3_target(
    target: Path,
    manifest: AtlasCoreBackupV3Manifest,
    *,
    runtime_uid: int,
    runtime_gid: int,
    active_transaction_id: str | None = None,
) -> None:
    manifest = _normalize_manifest(manifest)
    target = _validate_target_root(target)
    _validate_runtime_identity(runtime_uid, runtime_gid)
    namespace = _namespace(target)
    journal_path = namespace / JOURNAL_NAME
    if journal_path.exists() or journal_path.is_symlink():
        journal = _load_journal(target)
        if active_transaction_id != journal.transaction_id:
            raise RestoreTransactionError("target has unresolved restore state")
    elif namespace.exists() or namespace.is_symlink():
        _assert_private_directory(namespace, runtime_uid, runtime_gid)
        if any(namespace.iterdir()):
            raise RestoreTransactionError("target has unjournaled restore state")
    tool = _tool_functions()
    for relative in ("config", "secrets"):
        directory = _safe_target_path(target, relative)
        if (
            not directory.is_dir()
            or directory.is_symlink()
            or directory.stat().st_mode & 0o777 != PRIVATE_DIRECTORY_MODE
            or directory.stat().st_uid != runtime_uid
            or directory.stat().st_gid != runtime_gid
        ):
            raise RestoreTransactionError(
                f"managed target directory is invalid: {relative}"
            )
    entries = {entry.path.value: entry for entry in manifest.inventory}
    for operation in build_restore_plan(manifest):
        path = _safe_target_path(target, operation.path)
        if operation.action is RestoreAction.ABSENT:
            if path.exists() or path.is_symlink():
                raise RestoreTransactionError(
                    f"managed target path must be absent: {operation.path}"
                )
            continue
        entry = entries[operation.path]
        if not path.is_file() or path.is_symlink():
            raise RestoreTransactionError(
                f"managed target artifact is invalid: {operation.path}"
            )
        metadata = path.stat()
        if (
            metadata.st_mode & 0o777 != PRIVATE_FILE_MODE
            or metadata.st_uid != runtime_uid
            or metadata.st_gid != runtime_gid
            or operation.artifact is None
            or metadata.st_size != operation.artifact.size
            or _sha256(path) != operation.artifact.sha256
        ):
            raise RestoreTransactionError(
                f"managed target metadata is invalid: {operation.path}"
            )
        managed_path = ManagedPath(operation.path)
        if entry.content_kind is ContentKind.SQLITE:
            if tool["integrity"](path) != "ok":
                raise RestoreTransactionError(
                    f"managed target SQLite integrity failed: {operation.path}"
                )
            tool["validate_sqlite_application"](path, managed_path)
        else:
            tool["validate_runtime_file"](path, operation.path, PRIVATE_FILE_MODE)


def _stage(
    backup: Path,
    target: Path,
    stage: Path,
    plan: tuple[PlannedOperation, ...],
    manifest: AtlasCoreBackupV3Manifest,
    uid: int,
    gid: int,
    tool: Mapping[str, Any],
    hook: FailureHook | None,
) -> None:
    entries = {entry.path.value: entry for entry in manifest.inventory}
    index = 0
    for operation in plan:
        if operation.action is not RestoreAction.INSTALL:
            continue
        source = _safe_backup_path(backup, operation.path)
        destination = _safe_transaction_path(stage, operation.path)
        _ensure_private_parents(stage, destination.parent, uid, gid)
        if not source.is_file() or source.is_symlink():
            raise RestoreTransactionError(f"backup artifact is unsafe: {operation.path}")
        if destination.exists() or destination.is_symlink():
            raise RestoreTransactionError(
                f"staged artifact path already exists: {operation.path}"
            )
        shutil.copyfile(source, destination, follow_symlinks=False)
        os.chmod(destination, PRIVATE_FILE_MODE)
        os.chown(destination, uid, gid)
        _fsync_file(destination)
        artifact = operation.artifact
        if (
            artifact is None
            or destination.stat().st_size != artifact.size
            or _sha256(destination) != artifact.sha256
        ):
            raise RestoreTransactionError(f"staged artifact mismatch: {operation.path}")
        entry = entries[operation.path]
        if entry.content_kind is ContentKind.SQLITE:
            if tool["integrity"](destination) != "ok":
                raise RestoreTransactionError(
                    f"staged SQLite integrity failed: {operation.path}"
                )
            tool["validate_sqlite_application"](
                destination, ManagedPath(operation.path)
            )
        else:
            tool["validate_runtime_file"](
                destination, operation.path, PRIVATE_FILE_MODE
            )
        _fsync_directory(destination.parent)
        _emit(hook, "staging_artifact", index)
        index += 1


def _quarantine(
    target: Path,
    rollback: Path,
    journal: RestoreJournal,
    hook: FailureHook | None,
) -> None:
    for index, operation in enumerate(journal.operations):
        final = _safe_target_path(target, operation.path)
        if not operation.original.exists:
            continue
        _verify_file_state(final, operation.original, operation.path)
        _assert_regular_file(final, operation.path)
        _fsync_file(final)
        rollback_path = _safe_transaction_path(rollback, operation.path)
        _ensure_private_parents(
            rollback,
            rollback_path.parent,
            journal.runtime_uid,
            journal.runtime_gid,
        )
        os.replace(final, rollback_path)
        _fsync_directory(final.parent)
        _fsync_directory(rollback_path.parent)
        _verify_file_state(rollback_path, operation.original, operation.path)
        _emit(hook, "quarantine_artifact", index)


def _install(
    target: Path,
    stage: Path,
    journal: RestoreJournal,
    uid: int,
    gid: int,
    hook: FailureHook | None,
) -> None:
    index = 0
    for operation in journal.operations:
        if operation.action is not RestoreAction.INSTALL:
            continue
        source = _safe_transaction_path(stage, operation.path)
        final = _safe_target_path(target, operation.path)
        _ensure_target_parents(target, final.parent, uid, gid)
        _assert_regular_file(source, operation.path)
        if final.exists() or final.is_symlink():
            raise RestoreTransactionError(f"managed target was not quarantined: {operation.path}")
        os.replace(source, final)
        _fsync_directory(source.parent)
        _fsync_directory(final.parent)
        _emit(hook, "installation_artifact", index)
        index += 1


def _rollback(target: Path, namespace: Path, journal: RestoreJournal) -> None:
    rollback = namespace / journal.transaction_id / "rollback"
    for operation in reversed(journal.operations):
        final = _safe_target_path(target, operation.path)
        rollback_path = _safe_transaction_path(rollback, operation.path)
        if operation.original.exists:
            if rollback_path.exists() or rollback_path.is_symlink():
                _assert_regular_file(rollback_path, operation.path)
                if final.exists() or final.is_symlink():
                    _unlink_regular(final, operation.path)
                _ensure_target_parents(
                    target, final.parent,
                    _required_int(operation.original.uid),
                    _required_int(operation.original.gid),
                )
                os.replace(rollback_path, final)
                os.chmod(final, _required_int(operation.original.mode))
                os.chown(
                    final,
                    _required_int(operation.original.uid),
                    _required_int(operation.original.gid),
                )
                _fsync_file(final)
                _fsync_directory(final.parent)
            else:
                _verify_file_state(final, operation.original, operation.path)
        elif final.exists() or final.is_symlink():
            _unlink_regular(final, operation.path)
            _fsync_directory(final.parent)
    _restore_directory_absence(target, journal.directories)
    for operation in journal.operations:
        _verify_file_state(
            _safe_target_path(target, operation.path), operation.original, operation.path
        )
    _remove_transaction_evidence(namespace, journal)


def _cleanup_committed(
    target: Path,
    namespace: Path,
    journal: RestoreJournal,
) -> None:
    if journal.phase is not RestorePhase.COMMITTED:
        raise RestoreTransactionError("only committed restore state can be finalized")
    verify_v3_target(
        target,
        journal.manifest,
        runtime_uid=journal.runtime_uid,
        runtime_gid=journal.runtime_gid,
        active_transaction_id=journal.transaction_id,
    )
    _remove_transaction_evidence(namespace, journal)


def _remove_transaction_evidence(namespace: Path, journal: RestoreJournal) -> None:
    transaction = _safe_transaction_path(namespace, journal.transaction_id)
    _remove_tree(transaction)
    _fsync_directory(namespace)
    journal_path = namespace / JOURNAL_NAME
    if journal_path.exists():
        journal_path.unlink()
        _fsync_directory(namespace)
    if namespace.exists() and not any(namespace.iterdir()):
        namespace.rmdir()
        _fsync_directory(namespace.parent)


def _transition(
    namespace: Path,
    journal: RestoreJournal,
    phase: RestorePhase,
) -> RestoreJournal:
    current = _PHASE_ORDER.index(journal.phase)
    if current + 1 >= len(_PHASE_ORDER) or _PHASE_ORDER[current + 1] is not phase:
        raise RestoreJournalError("restore journal phase transition is invalid")
    changed = RestoreJournal(
        transaction_id=journal.transaction_id,
        target_path=journal.target_path,
        target_device=journal.target_device,
        target_inode=journal.target_inode,
        runtime_uid=journal.runtime_uid,
        runtime_gid=journal.runtime_gid,
        phase=phase,
        manifest=journal.manifest,
        manifest_digest=journal.manifest_digest,
        operations=journal.operations,
        directories=journal.directories,
    )
    _write_journal(namespace, changed)
    return changed


def _write_journal(namespace: Path, journal: RestoreJournal) -> None:
    _assert_private_directory(namespace)
    temporary = namespace / f".{JOURNAL_NAME}.tmp"
    if temporary.exists() or temporary.is_symlink():
        raise RestoreJournalError("unexpected restore journal temporary file")
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        os.fchmod(descriptor, PRIVATE_FILE_MODE)
        os.fchown(descriptor, journal.runtime_uid, journal.runtime_gid)
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump(journal.to_dict(), stream, sort_keys=True, separators=(",", ":"))
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, namespace / JOURNAL_NAME)
        _fsync_directory(namespace)
    finally:
        if temporary.exists():
            temporary.unlink()


def _load_journal(target: Path) -> RestoreJournal:
    namespace = _namespace(target)
    _assert_private_directory(namespace)
    journal_path = namespace / JOURNAL_NAME
    if not journal_path.is_file() or journal_path.is_symlink():
        raise RestoreJournalError("restore journal path is unsafe")
    try:
        journal = RestoreJournal.from_dict(
            json.loads(journal_path.read_text(encoding="utf-8"))
        )
    except (json.JSONDecodeError, OSError) as error:
        raise RestoreJournalError("restore journal cannot be decoded") from error
    journal_metadata = journal_path.stat()
    if (
        journal_metadata.st_mode & 0o777 != PRIVATE_FILE_MODE
        or journal_metadata.st_uid != journal.runtime_uid
        or journal_metadata.st_gid != journal.runtime_gid
    ):
        raise RestoreJournalError("restore journal ownership or mode is invalid")
    metadata = target.stat()
    if (
        str(target) != journal.target_path
        or metadata.st_dev != journal.target_device
        or metadata.st_ino != journal.target_inode
    ):
        raise RestoreJournalError("restore journal target binding is invalid")
    transaction = _safe_transaction_path(namespace, journal.transaction_id)
    _assert_private_directory(namespace, journal.runtime_uid, journal.runtime_gid)
    if transaction.exists() or transaction.is_symlink():
        _assert_private_directory(
            transaction, journal.runtime_uid, journal.runtime_gid
        )
    elif journal.phase is not RestorePhase.COMMITTED:
        raise RestoreJournalError("restore transaction directory is missing")
    if transaction.exists():
        _validate_transaction_contents(transaction, journal)
    return journal


def _capture_file_state(path: Path) -> FileState:
    if not path.exists() and not path.is_symlink():
        return FileState(exists=False)
    _assert_regular_file(path, path.name)
    metadata = path.stat()
    return FileState(
        exists=True,
        sha256=_sha256(path),
        size=metadata.st_size,
        mode=metadata.st_mode & 0o777,
        uid=metadata.st_uid,
        gid=metadata.st_gid,
    )


def _capture_directory_state(target: Path, relative: str) -> DirectoryState:
    path = _safe_target_path(target, relative)
    if not path.exists() and not path.is_symlink():
        return DirectoryState(path=relative, exists=False)
    if path.is_symlink() or not path.is_dir():
        raise RestoreTransactionError(f"managed parent directory is unsafe: {relative}")
    metadata = path.stat()
    return DirectoryState(
        path=relative,
        exists=True,
        mode=metadata.st_mode & 0o777,
        uid=metadata.st_uid,
        gid=metadata.st_gid,
    )


def _verify_file_state(path: Path, expected: FileState, label: str) -> None:
    if not expected.exists:
        if path.exists() or path.is_symlink():
            raise RestoreRecoveryRequiredError(f"rollback absence mismatch: {label}")
        return
    _assert_regular_file(path, label)
    metadata = path.stat()
    if (
        metadata.st_size != expected.size
        or metadata.st_mode & 0o777 != expected.mode
        or metadata.st_uid != expected.uid
        or metadata.st_gid != expected.gid
        or _sha256(path) != expected.sha256
    ):
        raise RestoreRecoveryRequiredError(f"rollback file mismatch: {label}")


def _restore_directory_absence(
    target: Path,
    states: tuple[DirectoryState, ...],
) -> None:
    for state_value in reversed(states):
        path = _safe_target_path(target, state_value.path)
        if state_value.exists:
            if not path.is_dir() or path.is_symlink():
                raise RestoreRecoveryRequiredError(
                    f"rollback directory mismatch: {state_value.path}"
                )
            os.chmod(path, _required_int(state_value.mode))
            os.chown(
                path,
                _required_int(state_value.uid),
                _required_int(state_value.gid),
            )
            _fsync_directory(path)
            _fsync_directory(path.parent)
            metadata = path.stat()
            if (
                metadata.st_mode & 0o777 != state_value.mode
                or metadata.st_uid != state_value.uid
                or metadata.st_gid != state_value.gid
            ):
                raise RestoreRecoveryRequiredError(
                    f"rollback directory metadata mismatch: {state_value.path}"
                )
        elif path.exists():
            try:
                path.rmdir()
            except OSError as error:
                raise RestoreRecoveryRequiredError(
                    f"new restore directory is not empty: {state_value.path}"
                ) from error
            _fsync_directory(path.parent)


def _manifest_digest(manifest: AtlasCoreBackupV3Manifest) -> str:
    encoded = json.dumps(
        manifest.to_dict(), sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return sha256(encoded).hexdigest()


def _sha256(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _validate_relative_path(value: str, *, allowed: set[str] | tuple[str, ...]) -> None:
    if not isinstance(value, str) or not value:
        raise RestoreJournalError("journal path is invalid")
    relative = PurePosixPath(value)
    if (
        relative.is_absolute()
        or ".." in relative.parts
        or any(part in {"", "."} for part in relative.parts)
        or value not in allowed
    ):
        raise RestoreJournalError("journal path is unsafe or unmanaged")


def _safe_target_path(root: Path, relative: str) -> Path:
    _validate_relative_path(relative, allowed=_MANAGED_TRANSACTION_PATHS + ("config", "secrets"))
    return _safe_descendant(root, relative)


def _safe_backup_path(root: Path, relative: str) -> Path:
    _validate_relative_path(relative, allowed=tuple(path.value for path in MANAGED_PATH_ORDER))
    return _safe_descendant(root, relative)


def _safe_transaction_path(root: Path, relative: str) -> Path:
    if not isinstance(relative, str) or not relative:
        raise RestoreJournalError("transaction path is invalid")
    parsed = PurePosixPath(relative)
    if parsed.is_absolute() or ".." in parsed.parts or any(
        part in {"", "."} for part in parsed.parts
    ):
        raise RestoreJournalError("transaction path is unsafe")
    return _safe_descendant(root, relative)


def _safe_descendant(root: Path, relative: str) -> Path:
    if root.is_symlink():
        raise RestoreTransactionError("filesystem root cannot be a symlink")
    candidate = root.joinpath(*PurePosixPath(relative).parts)
    current = root
    for part in PurePosixPath(relative).parts[:-1]:
        current = current / part
        if current.is_symlink():
            raise RestoreTransactionError("filesystem path traverses a symlink")
    return candidate


def _validate_target_root(target: Path) -> Path:
    target = target.absolute()
    if not target.is_dir() or target.is_symlink():
        raise RestoreTransactionError("restore target must be a real directory")
    if target.resolve(strict=True) != target:
        raise RestoreTransactionError("restore target path cannot traverse a symlink")
    return target


def _validate_transaction_contents(
    transaction: Path, journal: RestoreJournal
) -> None:
    allowed_files = {
        f"{area}/{operation.path}"
        for area in ("stage", "rollback")
        for operation in journal.operations
    }
    allowed_directories = {"stage", "rollback"}
    for file_path in allowed_files:
        parent = PurePosixPath(file_path).parent
        while str(parent) != ".":
            allowed_directories.add(parent.as_posix())
            parent = parent.parent
    for path in transaction.rglob("*"):
        relative = path.relative_to(transaction).as_posix()
        metadata = path.lstat()
        if stat.S_ISLNK(metadata.st_mode) or not (
            stat.S_ISDIR(metadata.st_mode) or stat.S_ISREG(metadata.st_mode)
        ):
            raise RestoreJournalError("restore transaction contains an unsafe object")
        allowed = allowed_directories if stat.S_ISDIR(metadata.st_mode) else allowed_files
        if relative not in allowed:
            raise RestoreJournalError("restore transaction contains unexpected evidence")


def _namespace(target: Path) -> Path:
    return target / TRANSACTION_NAMESPACE


def _create_private_directory(path: Path, uid: int, gid: int) -> None:
    if path.exists() or path.is_symlink():
        _assert_private_directory(path, uid, gid)
        return
    path.mkdir(mode=PRIVATE_DIRECTORY_MODE)
    os.chmod(path, PRIVATE_DIRECTORY_MODE)
    os.chown(path, uid, gid)
    _fsync_directory(path.parent)


def _assert_private_directory(
    path: Path,
    uid: int | None = None,
    gid: int | None = None,
) -> None:
    if (
        not path.is_dir()
        or path.is_symlink()
        or path.stat().st_mode & 0o777 != PRIVATE_DIRECTORY_MODE
        or (uid is not None and path.stat().st_uid != uid)
        or (gid is not None and path.stat().st_gid != gid)
    ):
        raise RestoreTransactionError(f"restore transaction directory is unsafe: {path}")


def _ensure_private_parents(root: Path, parent: Path, uid: int, gid: int) -> None:
    relative = parent.relative_to(root)
    current = root
    for part in relative.parts:
        current = current / part
        _create_private_directory(current, uid, gid)


def _ensure_target_parents(root: Path, parent: Path, uid: int, gid: int) -> None:
    relative = parent.relative_to(root)
    current = root
    for part in relative.parts:
        current = current / part
        if current.exists() or current.is_symlink():
            if not current.is_dir() or current.is_symlink():
                raise RestoreTransactionError("managed target parent is unsafe")
        else:
            _create_private_directory(current, uid, gid)
        os.chmod(current, PRIVATE_DIRECTORY_MODE)
        os.chown(current, uid, gid)
        _fsync_directory(current)
        _fsync_directory(current.parent)


def _assert_regular_file(path: Path, label: str) -> None:
    try:
        metadata = path.lstat()
    except FileNotFoundError as error:
        raise RestoreTransactionError(f"managed file is missing: {label}") from error
    if not stat.S_ISREG(metadata.st_mode):
        raise RestoreTransactionError(f"managed path is not a regular file: {label}")
    if metadata.st_nlink != 1:
        raise RestoreTransactionError(f"managed path has unexpected hard links: {label}")


def _unlink_regular(path: Path, label: str) -> None:
    _assert_regular_file(path, label)
    path.unlink()


def _remove_tree(path: Path) -> None:
    if not path.exists() and not path.is_symlink():
        return
    if path.is_symlink() or not path.is_dir():
        raise RestoreTransactionError("restore cleanup path is unsafe")
    for entry in os.scandir(path):
        child = Path(entry.path)
        if entry.is_symlink():
            raise RestoreTransactionError("restore cleanup encountered a symlink")
        if entry.is_dir(follow_symlinks=False):
            _remove_tree(child)
        elif entry.is_file(follow_symlinks=False):
            child.unlink()
        else:
            raise RestoreTransactionError("restore cleanup encountered a special file")
    path.rmdir()
    _fsync_directory(path.parent)


def _cleanup_unjournaled_transaction(transaction: Path, namespace: Path) -> None:
    if transaction.exists():
        _remove_tree(transaction)
    if (
        namespace.exists()
        and namespace.is_dir()
        and not namespace.is_symlink()
        and not any(namespace.iterdir())
    ):
        namespace.rmdir()
        _fsync_directory(namespace.parent)


def _fsync_file(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _emit(hook: FailureHook | None, event: str, index: int | None) -> None:
    if hook is not None:
        hook(event, index)


def _validate_runtime_identity(uid: int, gid: int) -> None:
    if (
        not isinstance(uid, int)
        or isinstance(uid, bool)
        or uid < 0
        or not isinstance(gid, int)
        or isinstance(gid, bool)
        or gid < 0
    ):
        raise ValueError("runtime UID and GID must be non-negative integers")


def _required_int(value: int | None) -> int:
    if value is None:
        raise RestoreJournalError("required journal integer is missing")
    return value


def _normalize_manifest(value: object) -> AtlasCoreBackupV3Manifest:
    if isinstance(value, AtlasCoreBackupV3Manifest):
        return value
    serializer = getattr(value, "to_dict", None)
    if not callable(serializer):
        raise TypeError("restore planning requires a v3 manifest")
    return AtlasCoreBackupV3Manifest.from_dict(serializer())


def _tool_functions() -> Mapping[str, Any]:
    return runpy.run_path(str(Path(__file__).with_name("atlas-data-tool.py")))
