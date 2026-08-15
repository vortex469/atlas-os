"""Read-only startup interlock for unresolved Atlas data restore state."""

from __future__ import annotations

import stat
from pathlib import Path

RESTORE_NAMESPACE = ".atlas-restore"
RECOVERY_GUIDANCE = (
    "Atlas data restore recovery is required; keep the data volume detached "
    "and run scripts/atlas-data-restore with the verified backup"
)


def assert_restore_state_clean(data_root: Path) -> None:
    namespace = data_root / RESTORE_NAMESPACE
    try:
        metadata = namespace.lstat()
    except FileNotFoundError:
        return
    except OSError as error:
        raise RuntimeError(RECOVERY_GUIDANCE) from error
    if not stat.S_ISDIR(metadata.st_mode) or namespace.is_symlink():
        raise RuntimeError(RECOVERY_GUIDANCE)
    try:
        has_evidence = next(namespace.iterdir(), None) is not None
    except OSError as error:
        raise RuntimeError(RECOVERY_GUIDANCE) from error
    if has_evidence:
        raise RuntimeError(RECOVERY_GUIDANCE)
