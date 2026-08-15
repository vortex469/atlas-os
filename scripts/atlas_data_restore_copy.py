"""Copy a private verified backup into private runtime-readable staging."""

from __future__ import annotations

import os
import shutil
import stat
import sys
from pathlib import Path


def copy_private_backup(source: Path, destination: Path, uid: int, gid: int) -> None:
    source_metadata = source.lstat()
    if not stat.S_ISDIR(source_metadata.st_mode) or source.is_symlink():
        raise RuntimeError("backup source must be a real directory")
    if destination.exists() or destination.is_symlink():
        raise RuntimeError("backup staging destination already exists")
    destination.mkdir(mode=0o700)
    for path in source.rglob("*"):
        relative = path.relative_to(source)
        metadata = path.lstat()
        staged = destination / relative
        if stat.S_ISLNK(metadata.st_mode):
            raise RuntimeError("backup staging refuses symbolic links")
        if stat.S_ISDIR(metadata.st_mode):
            staged.mkdir(mode=0o700)
            os.chmod(staged, 0o700)
        elif stat.S_ISREG(metadata.st_mode) and metadata.st_nlink == 1:
            staged.parent.mkdir(parents=True, exist_ok=True)
            _copy_regular(path, staged)
        else:
            raise RuntimeError("backup staging refuses unsafe filesystem objects")
    for path in sorted(destination.rglob("*"), reverse=True):
        os.chown(path, uid, gid, follow_symlinks=False)
    os.chown(destination, uid, gid, follow_symlinks=False)


def _copy_regular(source: Path, destination: Path) -> None:
    source_descriptor = os.open(
        source,
        os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK,
    )
    try:
        metadata = os.fstat(source_descriptor)
        if not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1:
            raise RuntimeError("backup staging source changed during copy")
        destination_descriptor = os.open(
            destination,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
            0o600,
        )
        os.fchmod(destination_descriptor, 0o600)
        with os.fdopen(destination_descriptor, "wb") as output:
            with os.fdopen(os.dup(source_descriptor), "rb") as input_stream:
                shutil.copyfileobj(input_stream, output)
            output.flush()
            os.fsync(output.fileno())
    finally:
        os.close(source_descriptor)


if __name__ == "__main__":
    if len(sys.argv) != 5:
        raise SystemExit("usage: copy SOURCE DESTINATION UID GID")
    copy_private_backup(
        Path(sys.argv[1]), Path(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4])
    )
