import hashlib
import json

import pytest

from app.n121_artifact_metadata_helper import (
    PROOF_DOMAIN,
    build_artifact_metadata_proof,
)

ARTIFACT_ID = "artifact:home-assistant:2026.8.3"
ARTIFACT_VERSION = "2026.8.3"
CONTENT_DIGEST = "34b55477f84fc03fa4b31c57ffc8213ba884b61791f3e6adb8f484fb67d0771a"


def _expected_proof() -> str:
    canonical = json.dumps(
        {
            "artifact_id": ARTIFACT_ID,
            "artifact_version": ARTIFACT_VERSION,
            "content_digest": CONTENT_DIGEST,
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(
        PROOF_DOMAIN.encode("ascii") + b"\0" + canonical
    ).hexdigest()


def test_proof_is_deterministic() -> None:
    first = build_artifact_metadata_proof(
        artifact_id=ARTIFACT_ID,
        artifact_version=ARTIFACT_VERSION,
        content_digest=CONTENT_DIGEST,
    )
    second = build_artifact_metadata_proof(
        artifact_id=ARTIFACT_ID,
        artifact_version=ARTIFACT_VERSION,
        content_digest=CONTENT_DIGEST,
    )

    assert first == second
    assert first == _expected_proof()


def test_proof_is_lowercase_sha256_hex() -> None:
    proof = build_artifact_metadata_proof(
        artifact_id=ARTIFACT_ID,
        artifact_version=ARTIFACT_VERSION,
        content_digest=CONTENT_DIGEST,
    )

    assert len(proof) == 64
    assert all(character in "0123456789abcdef" for character in proof)


def test_proof_changes_when_any_metadata_changes() -> None:
    baseline = build_artifact_metadata_proof(
        artifact_id=ARTIFACT_ID,
        artifact_version=ARTIFACT_VERSION,
        content_digest=CONTENT_DIGEST,
    )

    changed_id = build_artifact_metadata_proof(
        artifact_id="artifact:nginx:1.27.0",
        artifact_version=ARTIFACT_VERSION,
        content_digest=CONTENT_DIGEST,
    )
    changed_version = build_artifact_metadata_proof(
        artifact_id=ARTIFACT_ID,
        artifact_version="2026.8.4",
        content_digest=CONTENT_DIGEST,
    )
    changed_digest = build_artifact_metadata_proof(
        artifact_id=ARTIFACT_ID,
        artifact_version=ARTIFACT_VERSION,
        content_digest="0" * 64,
    )

    assert changed_id != baseline
    assert changed_version != baseline
    assert changed_digest != baseline


@pytest.mark.parametrize(
    "artifact_id",
    ["", "  ", "artifact:\u00e9"],
)
def test_rejects_invalid_artifact_id(artifact_id: str) -> None:
    with pytest.raises(ValueError):
        build_artifact_metadata_proof(
            artifact_id=artifact_id,
            artifact_version=ARTIFACT_VERSION,
            content_digest=CONTENT_DIGEST,
        )


@pytest.mark.parametrize(
    "artifact_version",
    ["", "  ", "2026.8.3\n"],
)
def test_rejects_invalid_artifact_version(artifact_version: str) -> None:
    with pytest.raises(ValueError):
        build_artifact_metadata_proof(
            artifact_id=ARTIFACT_ID,
            artifact_version=artifact_version,
            content_digest=CONTENT_DIGEST,
        )


@pytest.mark.parametrize(
    "content_digest",
    [
        "",
        "34b55477",
        "34b55477" * 8 + "0" * 8,  # 72 chars, too long
        "34B55477" + "f" * 56,  # uppercase
        "g" * 64,  # not hexadecimal
        "0" * 64 + "\n",  # trailing newline
    ],
)
def test_rejects_invalid_content_digest(content_digest: str) -> None:
    with pytest.raises(ValueError):
        build_artifact_metadata_proof(
            artifact_id=ARTIFACT_ID,
            artifact_version=ARTIFACT_VERSION,
            content_digest=content_digest,
        )
