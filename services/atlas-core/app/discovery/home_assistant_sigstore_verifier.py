"""Offline verification of the single reviewed Home Assistant 2026.8.3 bundle.

This internal proof module owns every identity, artifact, and policy input. It
performs no acquisition, evidence construction, registration, or wiring.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

_BUNDLE_MEDIA_TYPE = "application/vnd.dev.sigstore.bundle.v0.3+json"
_DSSE_PAYLOAD_TYPE = "application/vnd.in-toto+json"
_STATEMENT_TYPE = "https://in-toto.io/Statement/v1"
_PREDICATE_TYPE = "https://sigstore.dev/cosign/sign/v1"
_RELEASE = "2026.8.3"
_IMAGE_DIGEST = (
    "sha256:14931c6b13756317849f46da1d01b45937a1150db66c081cfe529d48215943fe"
)
_ISSUER = "https://token.actions.githubusercontent.com"
_IDENTITY = "https://github.com/home-assistant/core/.github/workflows/builder.yml@refs/tags/2026.8.3"
_REPOSITORY = "home-assistant/core"
_REF = "refs/tags/2026.8.3"
_WORKFLOW_NAME = "Build images"
_WORKFLOW_SHA = "759e4658f40b3ccb671d418b8a0ed95224bf4561"
_TRUSTED_ROOT_PATH = (
    Path(__file__).parent / "trust" / "sigstore-production-trusted-root.json"
)
_TRUSTED_ROOT_SIZE = 6787
_TRUSTED_ROOT_SHA256 = (
    "6494e21ea73fa7ee769f85f57d5a3e6a08725eae1e38c755fc3517c9e6bc0b66"
)


class HomeAssistantSigstoreVerificationError(ValueError):
    """The input is invalid or failed cryptographic/application verification."""


def _load_trusted_root():
    from sigstore.models import TrustedRoot
    from sigstore_models.trustroot import v1 as trustroot_v1

    trusted_root_bytes = _TRUSTED_ROOT_PATH.read_bytes()
    if (
        len(trusted_root_bytes) != _TRUSTED_ROOT_SIZE
        or hashlib.sha256(trusted_root_bytes).hexdigest() != _TRUSTED_ROOT_SHA256
    ):
        raise HomeAssistantSigstoreVerificationError(
            "reviewed Sigstore trust root does not match"
        )
    return TrustedRoot(trustroot_v1.TrustedRoot.from_json(trusted_root_bytes))


@dataclass(frozen=True, slots=True)
class _VerifiedHomeAssistantAttestation:
    """Facts returned after this verifier succeeds.

    Trust comes from execution of ``verify_home_assistant_2026_8_3_bundle``, not
    from construction of this ordinary private value. No production path may
    consume this value as proof, and this slice deliberately wires none.
    """

    release_version: str
    image_digest: str
    source_commit_sha: str
    authenticated_ref: str
    authenticated_repository: str
    authenticated_workflow_identity: str
    authenticated_workflow_name: str


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise HomeAssistantSigstoreVerificationError(
                f"duplicate JSON object key: {key!r}"
            )
        result[key] = value
    return result


def _validate_statement(payload: bytes) -> None:
    try:
        statement = json.loads(payload, object_pairs_hook=_reject_duplicate_keys)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise HomeAssistantSigstoreVerificationError(
            "DSSE payload is not strict JSON"
        ) from exc

    if not isinstance(statement, dict) or set(statement) != {
        "_type",
        "subject",
        "predicateType",
        "predicate",
    }:
        raise HomeAssistantSigstoreVerificationError(
            "in-toto statement has an unsupported top-level schema"
        )
    if statement["_type"] != _STATEMENT_TYPE:
        raise HomeAssistantSigstoreVerificationError("unexpected statement type")
    if statement["predicateType"] != _PREDICATE_TYPE:
        raise HomeAssistantSigstoreVerificationError("unexpected predicate type")
    if statement["predicate"] != {}:
        raise HomeAssistantSigstoreVerificationError("unexpected predicate content")

    subjects = statement["subject"]
    if not isinstance(subjects, list) or len(subjects) != 1:
        raise HomeAssistantSigstoreVerificationError(
            "statement must contain exactly one subject"
        )
    subject = subjects[0]
    if not isinstance(subject, dict) or set(subject) != {"digest", "annotations"}:
        raise HomeAssistantSigstoreVerificationError("unsupported subject schema")
    if subject["annotations"] != {}:
        raise HomeAssistantSigstoreVerificationError("unexpected subject annotations")
    digest = subject["digest"]
    if not isinstance(digest, dict) or set(digest) != {"sha256"}:
        raise HomeAssistantSigstoreVerificationError(
            "unsupported subject digest schema"
        )
    if digest["sha256"] != _IMAGE_DIGEST.removeprefix("sha256:"):
        raise HomeAssistantSigstoreVerificationError("subject digest does not match")


def verify_home_assistant_2026_8_3_bundle(
    *, bundle_bytes: bytes
) -> _VerifiedHomeAssistantAttestation:
    """Verify bundle bytes against the repository-owned 2026.8.3 policy."""

    if not isinstance(bundle_bytes, bytes):
        raise HomeAssistantSigstoreVerificationError("bundle_bytes must be bytes")

    # Lazy imports keep module import free of trust-root reads or Sigstore I/O.
    from sigstore.models import Bundle
    from sigstore.verify import Verifier
    from sigstore.verify.policy import (
        AllOf,
        GitHubWorkflowName,
        GitHubWorkflowRef,
        GitHubWorkflowRepository,
        GitHubWorkflowSHA,
        Identity,
    )

    try:
        bundle = Bundle.from_json(bundle_bytes)
        if bundle._inner.media_type != _BUNDLE_MEDIA_TYPE:
            raise HomeAssistantSigstoreVerificationError("unexpected bundle media type")
        trusted_root = _load_trusted_root()
        verifier = Verifier(trusted_root=trusted_root)
        policy = AllOf(
            [
                Identity(identity=_IDENTITY, issuer=_ISSUER),
                GitHubWorkflowRepository(_REPOSITORY),
                GitHubWorkflowRef(_REF),
                GitHubWorkflowSHA(_WORKFLOW_SHA),
                GitHubWorkflowName(_WORKFLOW_NAME),
            ]
        )
        payload_type, payload = verifier.verify_dsse(bundle=bundle, policy=policy)
    except HomeAssistantSigstoreVerificationError:
        raise
    except Exception as exc:
        raise HomeAssistantSigstoreVerificationError(
            "Sigstore bundle verification failed"
        ) from exc

    if payload_type != _DSSE_PAYLOAD_TYPE:
        raise HomeAssistantSigstoreVerificationError("unexpected DSSE payload type")
    _validate_statement(payload)
    return _VerifiedHomeAssistantAttestation(
        release_version=_RELEASE,
        image_digest=_IMAGE_DIGEST,
        source_commit_sha=_WORKFLOW_SHA,
        authenticated_ref=_REF,
        authenticated_repository=_REPOSITORY,
        authenticated_workflow_identity=_IDENTITY,
        authenticated_workflow_name=_WORKFLOW_NAME,
    )
