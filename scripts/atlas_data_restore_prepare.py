"""Prepare only the Atlas data root and managed private parent directories."""

from __future__ import annotations

import os
import stat
import sys
from pathlib import Path


def prepare_target(target: Path, uid: int, gid: int) -> None:
    metadata = target.lstat()
    if not stat.S_ISDIR(metadata.st_mode) or target.is_symlink():
        raise RuntimeError("restore target must be a real directory")
    existing_parents: list[Path] = []
    for name in ("config", "secrets"):
        directory = target / name
        if not directory.exists() and not directory.is_symlink():
            continue
        metadata = directory.lstat()
        if not stat.S_ISDIR(metadata.st_mode) or directory.is_symlink():
            raise RuntimeError(f"managed restore parent is unsafe: {name}")
        existing_parents.append(directory)
    os.chown(target, uid, gid)
    for directory in existing_parents:
        os.chmod(directory, 0o700)
        os.chown(directory, uid, gid)


if __name__ == "__main__":
    if len(sys.argv) != 4:
        raise SystemExit("usage: prepare TARGET UID GID")
    prepare_target(Path(sys.argv[1]), int(sys.argv[2]), int(sys.argv[3]))
