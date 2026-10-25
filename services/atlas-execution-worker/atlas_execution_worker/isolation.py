"""Observed local isolation metadata; not a remote or cryptographic attestation."""
from __future__ import annotations

import ctypes
import os
import re
from pathlib import Path

from app.execution.worker_contracts import WorkerAttestation


class IsolationUnavailable(RuntimeError):
    """The worker cannot substantiate its required execution isolation."""


def from_observations(*, uid: int, gid: int, readonly: bool, status: str, no_new_privileges: bool | None = None) -> WorkerAttestation:
    fields = {}
    for line in status.splitlines():
        name, separator, value = line.partition(':')
        if separator and name in {'NoNewPrivs','CapEff'}:
            if name in fields:
                raise IsolationUnavailable('ambiguous isolation observation')
            fields[name] = value.strip()
    capabilities = fields.get('CapEff', '')
    reported = fields.get('NoNewPrivs')
    observed = reported == '1' if reported is not None else no_new_privileges
    if reported is not None and no_new_privileges is not None and (reported == '1') != no_new_privileges:
        raise IsolationUnavailable('conflicting privilege observations')
    if uid != 10001 or gid != 10001 or not readonly or observed is not True:
        raise IsolationUnavailable('required execution isolation unavailable')
    if not re.fullmatch(r'[0-9a-fA-F]{1,32}', capabilities) or int(capabilities, 16) != 0:
        raise IsolationUnavailable('required execution capabilities unavailable')
    result = WorkerAttestation(uid, readonly, True, capabilities, 'atlas-workspace-observed')
    result.validate()
    return result


def _no_new_privileges() -> bool | None:
    # Read-only Linux query. runsc can omit this field from /proc/self/status.
    try:
        library = ctypes.CDLL(None, use_errno=True)
        library.prctl.restype = ctypes.c_int
        library.prctl.argtypes = [ctypes.c_int, ctypes.c_ulong, ctypes.c_ulong, ctypes.c_ulong, ctypes.c_ulong]
        value = library.prctl(39, 0, 0, 0, 0)  # PR_GET_NO_NEW_PRIVS
        return bool(value) if value in (0, 1) else None
    except (AttributeError, OSError):
        return None


def observe_attestation() -> WorkerAttestation:
    try:
        return from_observations(uid=os.geteuid(), gid=os.getegid(), readonly=bool(os.statvfs('/').f_flag & os.ST_RDONLY), status=Path('/proc/self/status').read_text(), no_new_privileges=_no_new_privileges())
    except (OSError, ValueError) as exc:
        raise IsolationUnavailable('execution isolation observation unavailable') from exc
