"""Disposable proof of guarded v1/v2 legacy-partial compatibility."""

from __future__ import annotations

import hashlib
import json
import runpy
import sqlite3
import tempfile
from pathlib import Path


def _backup(root: Path, version: int) -> Path:
    backup = root / f"v{version}"
    backup.mkdir()
    records = []
    for name in ("action_history.db", "provider_intelligence.db"):
        path = backup / name
        with sqlite3.connect(path) as connection:
            connection.execute("CREATE TABLE evidence (value TEXT NOT NULL)")
            connection.execute("INSERT INTO evidence VALUES ('bounded')")
        records.append(
            {
                "filename": name,
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "size": path.stat().st_size,
            }
        )
    manifest: dict[str, object] = {
        "format_version": version,
        "created_at": "2026-01-01T00:00:00+00:00",
        "databases": records,
    }
    if version == 2:
        manifest["files"] = []
    (backup / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    return backup


def prove(tool_path: Path) -> None:
    tool = runpy.run_path(str(tool_path))
    verify_backup = tool["verify_backup"]
    restore_backup = tool["restore_backup"]
    with tempfile.TemporaryDirectory(prefix="atlas-legacy-evidence-") as value:
        root = Path(value)
        for version in (1, 2):
            backup = _backup(root, version)
            manifest = verify_backup(backup)
            if manifest["format_version"] != version:
                raise RuntimeError("legacy backup version changed during verification")
            target = root / f"target-v{version}"
            try:
                restore_backup(backup, target)
            except RuntimeError as error:
                if "--allow-legacy-partial-new-lineage" not in str(error):
                    raise
            else:
                raise RuntimeError("legacy restore succeeded without acknowledgement")
            restore_backup(
                backup,
                target,
                allow_legacy_partial_new_lineage=True,
            )
            if {path.name for path in target.iterdir()} != {
                "action_history.db",
                "provider_intelligence.db",
            }:
                raise RuntimeError("legacy restore fabricated unexpected state")
        populated = root / "populated"
        populated.mkdir()
        conflict = populated / "operational_dispatch.db-wal"
        conflict.write_bytes(b"bounded-conflict")
        try:
            restore_backup(
                root / "v2",
                populated,
                allow_legacy_partial_new_lineage=True,
            )
        except RuntimeError as error:
            if "operational_dispatch.db-wal" not in str(error):
                raise
        else:
            raise RuntimeError("legacy restore overlaid populated managed state")
        if conflict.read_bytes() != b"bounded-conflict":
            raise RuntimeError("legacy refusal mutated populated state")


if __name__ == "__main__":
    import sys

    prove(Path(sys.argv[1]))
    print("Legacy partial recovery evidence passed")
