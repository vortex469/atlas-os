#!/usr/bin/env python3

import argparse
import hashlib
import json
import os
import re
import shutil
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path, PurePosixPath


DATABASES = ("action_history.db", "provider_intelligence.db")
RUNTIME_FILES = ("config/policies.yaml",)
MANIFEST_NAME = "manifest.json"
FORMAT_VERSION = 2
SUPPORTED_FORMAT_VERSIONS = {1, FORMAT_VERSION}
BACKUP_NAME_PATTERN = re.compile(
    r"^atlas-data-(?P<timestamp>\d{8}T\d{6}Z)$"
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def safe_relative_path(value: object) -> Path:
    if not isinstance(value, str) or not value:
        raise RuntimeError("runtime file path is invalid")

    relative = PurePosixPath(value)
    if relative.is_absolute() or ".." in relative.parts:
        raise RuntimeError(f"unsafe runtime file path: {value}")
    if any(part in {"", "."} for part in relative.parts):
        raise RuntimeError(f"unsafe runtime file path: {value}")

    return Path(*relative.parts)


def integrity(path: Path) -> str:
    connection = sqlite3.connect(
        f"file:{path}?mode=ro&immutable=1",
        uri=True,
    )
    try:
        return str(connection.execute("PRAGMA integrity_check").fetchone()[0])
    finally:
        connection.close()


def sqlite_backup(source: Path, destination: Path) -> None:
    source_connection = sqlite3.connect(
        f"file:{source}?mode=ro",
        uri=True,
    )
    destination_connection = sqlite3.connect(destination)
    try:
        source_connection.backup(destination_connection)
        destination_connection.execute("PRAGMA journal_mode=DELETE")
    finally:
        destination_connection.close()
        source_connection.close()


def create_backup(source: Path, destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    if any(destination.iterdir()):
        raise RuntimeError(f"backup destination is not empty: {destination}")
    database_records: list[dict[str, object]] = []
    runtime_file_records: list[dict[str, object]] = []

    for filename in DATABASES:
        source_path = source / filename
        if not source_path.is_file():
            raise RuntimeError(f"required database not found: {source_path}")

        destination_path = destination / filename
        sqlite_backup(source_path, destination_path)
        result = integrity(destination_path)
        if result != "ok":
            raise RuntimeError(
                f"backup integrity check failed for {filename}: {result}"
            )
        database_records.append(
            {
                "filename": filename,
                "sha256": sha256(destination_path),
                "size": destination_path.stat().st_size,
            }
        )

    for filename in RUNTIME_FILES:
        source_path = source / safe_relative_path(filename)
        if not source_path.is_file():
            continue

        destination_path = destination / safe_relative_path(filename)
        destination_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source_path, destination_path)
        runtime_file_records.append(
            {
                "path": filename,
                "sha256": sha256(destination_path),
                "size": destination_path.stat().st_size,
            }
        )

    manifest = {
        "format_version": FORMAT_VERSION,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "databases": database_records,
        "files": runtime_file_records,
    }
    manifest_path = destination / MANIFEST_NAME
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def apply_owner(path: Path, uid: int, gid: int) -> None:
    if uid < 0 or gid < 0:
        raise RuntimeError("output owner uid and gid must be non-negative")

    for current, directories, filenames in os.walk(path):
        current_path = Path(current)
        os.chown(current_path, uid, gid)
        for name in directories:
            os.chown(current_path / name, uid, gid)
        for name in filenames:
            os.chown(current_path / name, uid, gid)


def verify_backup(backup: Path) -> dict[str, object]:
    manifest_path = backup / MANIFEST_NAME
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    format_version = manifest.get("format_version")
    if format_version not in SUPPORTED_FORMAT_VERSIONS:
        raise RuntimeError("unsupported backup format version")

    records = manifest.get("databases")
    if not isinstance(records, list):
        raise RuntimeError("backup manifest has no database records")

    filenames = {
        record.get("filename")
        for record in records
        if isinstance(record, dict)
    }
    if filenames != set(DATABASES):
        raise RuntimeError("backup manifest database set is invalid")

    file_records = manifest.get("files", [])
    if format_version == 1 and "files" not in manifest:
        file_records = []
    if not isinstance(file_records, list):
        raise RuntimeError("backup manifest file records are invalid")

    expected_paths = {Path(filename) for filename in DATABASES}
    expected_paths.add(Path(MANIFEST_NAME))
    runtime_paths: set[Path] = set()

    for record in file_records:
        if not isinstance(record, dict):
            raise RuntimeError("backup manifest file record is invalid")
        relative_path = safe_relative_path(record.get("path"))
        if relative_path.as_posix() not in RUNTIME_FILES:
            raise RuntimeError(f"unexpected runtime file path: {relative_path}")
        runtime_paths.add(relative_path)
        expected_paths.add(relative_path)

    actual_paths = {
        path.relative_to(backup)
        for path in backup.rglob("*")
        if path.is_file()
    }
    if actual_paths != expected_paths:
        unexpected = sorted(path.as_posix() for path in actual_paths - expected_paths)
        missing = sorted(path.as_posix() for path in expected_paths - actual_paths)
        raise RuntimeError(
            f"backup file set is invalid; unexpected={unexpected}, "
            f"missing={missing}"
        )

    for record in records:
        if not isinstance(record, dict):
            raise RuntimeError("backup manifest record is invalid")
        filename = record["filename"]
        if filename not in DATABASES:
            raise RuntimeError(f"unexpected database filename: {filename}")
        path = backup / filename
        if not path.is_file():
            raise RuntimeError(f"backup database not found: {filename}")
        if path.stat().st_size != record.get("size"):
            raise RuntimeError(f"backup size mismatch: {filename}")
        if sha256(path) != record.get("sha256"):
            raise RuntimeError(f"backup checksum mismatch: {filename}")
        result = integrity(path)
        if result != "ok":
            raise RuntimeError(
                f"backup integrity check failed for {filename}: {result}"
            )

    for record in file_records:
        relative_path = safe_relative_path(record.get("path"))
        if relative_path not in runtime_paths:
            raise RuntimeError(f"backup runtime file not registered: {relative_path}")
        path = backup / relative_path
        if not path.is_file():
            raise RuntimeError(f"backup runtime file not found: {relative_path}")
        if path.stat().st_size != record.get("size"):
            raise RuntimeError(f"backup runtime file size mismatch: {relative_path}")
        if sha256(path) != record.get("sha256"):
            raise RuntimeError(f"backup runtime file checksum mismatch: {relative_path}")

    return manifest


def atomic_restore_file(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = target.with_name(f".{target.name}.restore")
    if temporary_path.exists():
        temporary_path.unlink()
    shutil.copyfile(source, temporary_path)
    os.chmod(temporary_path, 0o600)
    os.replace(temporary_path, target)


def restore_backup(backup: Path, target: Path) -> None:
    manifest = verify_backup(backup)
    target.mkdir(parents=True, exist_ok=True)

    for filename in DATABASES:
        temporary_path = target / f".{filename}.restore"
        if temporary_path.exists():
            temporary_path.unlink()
        sqlite_backup(backup / filename, temporary_path)
        result = integrity(temporary_path)
        if result != "ok":
            raise RuntimeError(
                f"restored database integrity check failed for "
                f"{filename}: {result}"
            )
        os.replace(temporary_path, target / filename)
        for suffix in ("-wal", "-shm"):
            journal = target / f"{filename}{suffix}"
            if journal.exists():
                journal.unlink()

    for record in manifest.get("files", []):
        relative_path = safe_relative_path(record.get("path"))
        atomic_restore_file(backup / relative_path, target / relative_path)


def prune_backups(
    backup_root: Path,
    retention_days: int,
    minimum_count: int,
    *,
    dry_run: bool,
) -> None:
    if retention_days < 1:
        raise ValueError("retention days must be at least 1")
    if minimum_count < 1:
        raise ValueError("minimum count must be at least 1")
    if not backup_root.is_dir():
        raise RuntimeError(f"backup root not found: {backup_root}")

    backups: list[tuple[datetime, Path]] = []
    for path in backup_root.iterdir():
        if not path.is_dir():
            continue
        match = BACKUP_NAME_PATTERN.fullmatch(path.name)
        if match is None:
            continue
        timestamp = datetime.strptime(
            match.group("timestamp"),
            "%Y%m%dT%H%M%SZ",
        ).replace(tzinfo=timezone.utc)
        backups.append((timestamp, path))

    backups.sort(reverse=True)
    cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)
    candidates = [
        path
        for timestamp, path in backups[minimum_count:]
        if timestamp < cutoff
    ]

    for path in candidates:
        verify_backup(path)
        if dry_run:
            print(f"Would remove expired backup: {path}")
        else:
            shutil.rmtree(path)
            print(f"Removed expired backup: {path}")

    print(
        f"Backup retention complete: total={len(backups)} "
        f"expired={len(candidates)} minimum_kept={minimum_count}"
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)

    backup_parser = subparsers.add_parser("backup")
    backup_parser.add_argument("source", type=Path)
    backup_parser.add_argument("destination", type=Path)
    backup_parser.add_argument("--output-owner-uid", type=int)
    backup_parser.add_argument("--output-owner-gid", type=int)

    verify_parser = subparsers.add_parser("verify")
    verify_parser.add_argument("backup", type=Path)

    chown_parser = subparsers.add_parser("chown")
    chown_parser.add_argument("path", type=Path)
    chown_parser.add_argument("uid", type=int)
    chown_parser.add_argument("gid", type=int)

    restore_parser = subparsers.add_parser("restore")
    restore_parser.add_argument("backup", type=Path)
    restore_parser.add_argument("target", type=Path)

    prune_parser = subparsers.add_parser("prune")
    prune_parser.add_argument("backup_root", type=Path)
    prune_parser.add_argument(
        "--retention-days",
        type=int,
        default=30,
    )
    prune_parser.add_argument(
        "--minimum-count",
        type=int,
        default=7,
    )
    prune_parser.add_argument("--dry-run", action="store_true")

    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.command == "backup":
        create_backup(args.source, args.destination)
        if args.output_owner_uid is not None or args.output_owner_gid is not None:
            if args.output_owner_uid is None or args.output_owner_gid is None:
                raise RuntimeError(
                    "both --output-owner-uid and --output-owner-gid are required"
                )
            apply_owner(args.destination, args.output_owner_uid, args.output_owner_gid)
    elif args.command == "verify":
        manifest = verify_backup(args.backup)
        file_count = len(manifest.get("files", []))
        print(
            f"Backup verified: {len(manifest['databases'])} databases, "
            f"{file_count} runtime files, "
            f"created {manifest['created_at']}"
        )
    elif args.command == "chown":
        apply_owner(args.path, args.uid, args.gid)
    elif args.command == "restore":
        restore_backup(args.backup, args.target)
        print("Backup restored and verified")
    else:
        prune_backups(
            args.backup_root,
            args.retention_days,
            args.minimum_count,
            dry_run=args.dry_run,
        )


if __name__ == "__main__":
    main()
