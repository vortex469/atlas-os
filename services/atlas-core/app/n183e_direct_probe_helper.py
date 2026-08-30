"""N18.3e direct probe helper.

Tiny pure helper for the N18.3e direct probe stage. It binds one direct
probe attempt's stable fields (target and outcome) to a single
domain-separated SHA-256 fingerprint. The helper is deterministic,
performs no I/O and no clock reads, and grants no authority: a probe
receipt is evidence only.
"""

from __future__ import annotations

import hashlib
import json

PROBE_DOMAIN = "atlas:n183e-direct-probe-receipt:v1"

PROBE_OUTCOMES = ("reached", "unreachable")


def _require_nonblank_ascii(value: str, name: str) -> str:
    if not value or value != value.strip():
        raise ValueError(f"{name} must be non-blank ASCII text")
    if not value.isascii() or any(character < " " for character in value):
        raise ValueError(f"{name} must be printable ASCII text")
    return value


def build_direct_probe_receipt(*, target: str, outcome: str) -> str:
    """Return the N18.3e direct probe receipt for one exact probe attempt.

    The receipt is the lowercase hex SHA-256 of the probe domain, a NUL
    separator, and the compact canonical-JSON (sorted keys) encoding of
    the exact target/outcome pair. Repeated calls with the same inputs
    return the same receipt; any other input returns a different receipt.
    """
    target = _require_nonblank_ascii(target, "target")
    if outcome not in PROBE_OUTCOMES:
        raise ValueError(
            "outcome must be one of: " + ", ".join(PROBE_OUTCOMES)
        )

    canonical = json.dumps(
        {
            "outcome": outcome,
            "target": target,
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(
        PROBE_DOMAIN.encode("ascii") + b"\0" + canonical
    ).hexdigest()
