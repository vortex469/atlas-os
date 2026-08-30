"""N19.0 readiness probe helper.

Tiny pure helper for the N19.0 readiness probe stage. It binds one
readiness probe attempt's stable fields (target, required capability,
and observed verdict) to a single domain-separated SHA-256 fingerprint.
The helper is deterministic, performs no I/O and no clock reads, and
grants no authority: a readiness probe receipt is evidence only.
"""

from __future__ import annotations

import hashlib
import json

PROBE_DOMAIN = "atlas:n190-readiness-probe-receipt:v1"

PROBE_VERDICTS = ("ready", "not_ready")


def _require_nonblank_ascii(value: str, name: str) -> str:
    if not value or value != value.strip():
        raise ValueError(f"{name} must be non-blank ASCII text")
    if not value.isascii() or any(character < " " for character in value):
        raise ValueError(f"{name} must be printable ASCII text")
    return value


def build_readiness_probe_receipt(
    *,
    target: str,
    required_capability: str,
    observed_verdict: str,
) -> str:
    """Return the N19.0 readiness probe receipt for one exact attempt.

    The receipt is the lowercase hex SHA-256 of the probe domain, a NUL
    separator, and the compact canonical-JSON (sorted keys) encoding of
    the exact target/required-capability/observed-verdict triple. A
    readiness probe is verdict-bound: the receipt binds the observed
    verdict to the target's declared required capability, so a ready
    verdict and a not_ready verdict for the same target yield different
    receipts. Repeated calls with the same inputs return the same
    receipt; any other input returns a different receipt.
    """
    target = _require_nonblank_ascii(target, "target")
    required_capability = _require_nonblank_ascii(
        required_capability, "required_capability"
    )
    if observed_verdict not in PROBE_VERDICTS:
        raise ValueError(
            "observed_verdict must be one of: " + ", ".join(PROBE_VERDICTS)
        )

    canonical = json.dumps(
        {
            "observed_verdict": observed_verdict,
            "required_capability": required_capability,
            "target": target,
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(
        PROBE_DOMAIN.encode("ascii") + b"\0" + canonical
    ).hexdigest()
