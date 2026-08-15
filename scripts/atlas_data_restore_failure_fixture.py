"""Failure injection used only by the disposable data recovery gate."""

from __future__ import annotations

import os
import stat
import sys
from pathlib import Path

from atlas_data_restore_transaction import (
    RestoreTransactionError,
    execute_v3_restore,
)


class SimulatedCrash(BaseException):
    pass


def snapshot(root: Path) -> dict[str, tuple[str, bytes | None, int, int, int]]:
    result: dict[str, tuple[str, bytes | None, int, int, int]] = {}
    for path in root.rglob("*"):
        if ".atlas-restore" in path.parts:
            continue
        metadata = path.lstat()
        relative = path.relative_to(root).as_posix()
        if stat.S_ISDIR(metadata.st_mode):
            result[relative] = (
                "directory", None, metadata.st_mode & 0o777,
                metadata.st_uid, metadata.st_gid,
            )
        elif stat.S_ISREG(metadata.st_mode):
            result[relative] = (
                "file", path.read_bytes(), metadata.st_mode & 0o777,
                metadata.st_uid, metadata.st_gid,
            )
        else:
            raise RuntimeError("disposable target contains an unsafe object")
    return result


def inject(mode: str) -> None:
    before = snapshot(Path("/target"))

    def failure_hook(event: str, index: int | None) -> None:
        if event == "installation_artifact" and index == 0:
            if mode == "handled":
                raise RuntimeError("disposable handled failure")
            raise SimulatedCrash

    try:
        execute_v3_restore(
            Path("/staging/backup"),
            Path("/target"),
            runtime_uid=os.getuid(),
            runtime_gid=os.getgid(),
            failure_hook=failure_hook,
        )
    except RestoreTransactionError:
        if mode != "handled":
            raise
        if (Path("/target") / ".atlas-restore").exists():
            raise RuntimeError("handled failure left transaction evidence")
        if snapshot(Path("/target")) != before:
            raise RuntimeError("handled failure did not restore the exact old target")
    except SimulatedCrash:
        if mode != "crash":
            raise
        if not (Path("/target") / ".atlas-restore" / "journal.json").is_file():
            raise RuntimeError("crash did not leave durable journal evidence")
    else:
        raise RuntimeError("failure injection unexpectedly completed")


if __name__ == "__main__":
    inject(sys.argv[1])
