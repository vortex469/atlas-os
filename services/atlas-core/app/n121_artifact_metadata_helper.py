"""N12.1 artifact metadata proof helper.

Tiny pure helper for the N12.1 metadata proof stage. It binds one
artifact's stable metadata (artifact id, version, content digest) to a
single domain-separated SHA-256 fingerprint. The helper is deterministic,
performs no I/O and no clock reads, and grants no authority: a proof is
evidence only.
"""

from __future__ import annotations

import hashlib
import json
import re

PROOF_DOMAIN = "atlas:n121-artifact-metadata-proof:v1"

_SHA256_HEX_RE = re.compile(r"^[0-9a-f]{64}$")


def _require_nonblank_ascii(value: str, name: str) -> str:
    if not value or value != value.strip():
        raise ValueError(f"{name} must be non-blank ASCII text")
    if not value.isascii() or any(character < " " for character in value):
        raise ValueError(f"{name} must be printable ASCII text")
    return value


def build_artifact_metadata_proof(
    *,
    artifact_id: str,
    artifact_version: str,
    content_digest: str,
) -> str:
    """Return the N12.1 metadata proof for one exact artifact identity.

    The proof is the lowercase hex SHA-256 of the proof domain, a NUL
    separator, and the compact canonical-JSON (sorted keys) encoding of
    the exact metadata triple. Repeated calls with the same inputs return
    the same proof; any other metadata returns a different proof.
    """
    artifact_id = _require_nonblank_ascii(artifact_id, "artifact_id")
    artifact_version = _require_nonblank_ascii(artifact_version, "artifact_version")
    if not _SHA256_HEX_RE.fullmatch(content_digest):
        raise ValueError(
            "content_digest must be a 64-character lowercase SHA-256 hex digest"
        )

    canonical = json.dumps(
        {
            "artifact_id": artifact_id,
            "artifact_version": artifact_version,
            "content_digest": content_digest,
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(
        PROOF_DOMAIN.encode("ascii") + b"\0" + canonical
    ).hexdigest()
