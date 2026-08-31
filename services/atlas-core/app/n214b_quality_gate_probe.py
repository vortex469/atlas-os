"""N21.4b quality gate proof helper.

Tiny pure helper for the N21.4b quality gate proof stage. It binds one
quality gate attempt's stable fields (gate identity and observed
verdict) to a single domain-separated SHA-256 fingerprint. The helper
is deterministic, performs no I/O and no clock reads, and grants no
authority: a quality gate proof is evidence only.
"""

from __future__ import annotations

import hashlib
import json

PROOF_DOMAIN = "atlas:n214b-quality-gate-proof:v1"

GATE_VERDICTS = ("passed", "failed")


def _require_nonblank_ascii(value: str, name: str) -> str:
    if not value or value != value.strip():
        raise ValueError(f"{name} must be non-blank ASCII text")
    if not value.isascii() or any(character < " " for character in value):
        raise ValueError(f"{name} must be printable ASCII text")
    return value


def build_quality_gate_proof(*, gate_id: str, observed_verdict: str) -> str:
    """Return the N21.4b quality gate proof for one exact gate attempt.

    The proof is the lowercase hex SHA-256 of the proof domain, a NUL
    separator, and the compact canonical-JSON (sorted keys) encoding of
    the exact gate-identity/observed-verdict pair. A quality gate proof
    is verdict-bound: the proof binds the observed verdict to the gate's
    identity, so a passed verdict and a failed verdict for the same gate
    yield different proofs. Repeated calls with the same inputs return
    the same proof; any other input returns a different proof.
    """
    gate_id = _require_nonblank_ascii(gate_id, "gate_id")
    if observed_verdict not in GATE_VERDICTS:
        raise ValueError(
            "observed_verdict must be one of: " + ", ".join(GATE_VERDICTS)
        )

    canonical = json.dumps(
        {
            "gate_id": gate_id,
            "observed_verdict": observed_verdict,
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(
        PROOF_DOMAIN.encode("ascii") + b"\0" + canonical
    ).hexdigest()
