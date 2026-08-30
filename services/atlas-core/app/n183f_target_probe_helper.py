"""N18.3f target-aware probe helper.

Tiny pure helper for the N18.3f target-aware probe stage. It binds one
target-aware probe attempt's stable fields (target, expected outcome,
and observed outcome) to a single domain-separated SHA-256 fingerprint.
The helper is deterministic, performs no I/O and no clock reads, and
grants no authority: a target-aware probe receipt is evidence only.
"""

from __future__ import annotations

import hashlib
import json

PROBE_DOMAIN = "atlas:n183f-target-aware-probe-receipt:v1"

PROBE_OUTCOMES = ("reached", "unreachable")


def _require_nonblank_ascii(value: str, name: str) -> str:
    if not value or value != value.strip():
        raise ValueError(f"{name} must be non-blank ASCII text")
    if not value.isascii() or any(character < " " for character in value):
        raise ValueError(f"{name} must be printable ASCII text")
    return value


def build_target_aware_probe_receipt(
    *,
    target: str,
    expected_outcome: str,
    observed_outcome: str,
) -> str:
    """Return the N18.3f target-aware probe receipt for one exact attempt.

    The receipt is the lowercase hex SHA-256 of the probe domain, a NUL
    separator, and the compact canonical-JSON (sorted keys) encoding of
    the exact target/expected/observed triple. A probe is target-aware
    because the receipt binds the observed outcome to the target's
    declared expected outcome: a matching pair and a mismatching pair
    yield different receipts. Repeated calls with the same inputs
    return the same receipt; any other input returns a different
    receipt.
    """
    target = _require_nonblank_ascii(target, "target")
    if expected_outcome not in PROBE_OUTCOMES:
        raise ValueError(
            "expected_outcome must be one of: " + ", ".join(PROBE_OUTCOMES)
        )
    if observed_outcome not in PROBE_OUTCOMES:
        raise ValueError(
            "observed_outcome must be one of: " + ", ".join(PROBE_OUTCOMES)
        )

    canonical = json.dumps(
        {
            "expected_outcome": expected_outcome,
            "observed_outcome": observed_outcome,
            "target": target,
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(
        PROBE_DOMAIN.encode("ascii") + b"\0" + canonical
    ).hexdigest()
