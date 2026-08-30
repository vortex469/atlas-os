"""N17 smoke helper.

Tiny pure helper for the N17 smoke stage. It binds one smoke attempt's
stable fields (stage label and result) to a single domain-separated
SHA-256 fingerprint. The helper is deterministic, performs no I/O and no
clock reads, and grants no authority: a smoke receipt is evidence only.
"""

from __future__ import annotations

import hashlib
import json

SMOKE_DOMAIN = "atlas:n17-smoke-receipt:v1"

SMOKE_RESULTS = ("ok", "fail")


def _require_nonblank_ascii(value: str, name: str) -> str:
    if not value or value != value.strip():
        raise ValueError(f"{name} must be non-blank ASCII text")
    if not value.isascii() or any(character < " " for character in value):
        raise ValueError(f"{name} must be printable ASCII text")
    return value


def build_smoke_receipt(*, stage: str, result: str) -> str:
    """Return the N17 smoke receipt for one exact smoke attempt.

    The receipt is the lowercase hex SHA-256 of the smoke domain, a NUL
    separator, and the compact canonical-JSON (sorted keys) encoding of
    the exact stage/result pair. Repeated calls with the same inputs
    return the same receipt; any other input returns a different receipt.
    """
    stage = _require_nonblank_ascii(stage, "stage")
    if result not in SMOKE_RESULTS:
        raise ValueError(
            "result must be one of: " + ", ".join(SMOKE_RESULTS)
        )

    canonical = json.dumps(
        {
            "result": result,
            "stage": stage,
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(
        SMOKE_DOMAIN.encode("ascii") + b"\0" + canonical
    ).hexdigest()
