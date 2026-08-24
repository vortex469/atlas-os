"""Bounded, pure image-grounding contract for one deployment binding.

P1a of v0.14 adds inert, contract-only image grounding to the Discovery
Center. The evaluator is deterministic and side-effect free: it performs no
registry resolution, no tag resolution, no filesystem reads, no network
access, no clock reads, no provider calls, and no Agent calls.

Grounding is fail-closed. A positive result requires ALL of the following:

- the catalog entry carries a curated :class:`DeploymentBinding`;
- the supplied release version is strict numeric ``X.Y.Z`` (no leading
  zeros, no suffixes, no whitespace);
- exactly one repository compose image observation is present and it
  matches the binding compose file, service, and deployment method;
- the observation is an immutable digest-pinned image reference
  (``[registry/]repository[:tag]@sha256:<64 lowercase hex>``); a mutable
  or tag-only observed image can never ground;
- at least one image-release evidence row is present, every row is
  compatible with the supplied release version and the binding
  deployment method, and the evidence set contains at least one trusted
  row (``curated`` or ``registry_attested``);
- the trusted row's ``release_version`` exactly equals the supplied
  release version;
- the parsed observed repository/image identity exactly equals the
  trusted row's ``image_reference``;
- the parsed observed sha256 digest exactly equals the trusted row's
  ``image_digest``.

A bare digest alone is insufficient: a digest does not prove release
correspondence, so the exact version-to-evidence association and the
exact repository identity are required as well. Contradictory evidence
rows (differing release versions, image references, or digests) fail
closed as ``CONFLICTED`` regardless of input tuple order.
"""

from __future__ import annotations

import re
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from app.discovery.models import (
    _STRICT_RELEASE_VERSION_PATTERN,
    DeploymentBinding,
    ImageReleaseEvidence,
    ImageReleaseEvidenceSourceClass,
    RepositoryComposeImageObservation,
)

IMAGE_GROUNDING_SCHEMA = "discovery-image-grounding-v1"

#: Source classes that may positively ground a deployment image.
#: ``upstream_signed`` is not trusted in P1a: an upstream signature does
#: not by itself attest release correspondence for this deployment.
TRUSTED_IMAGE_RELEASE_SOURCE_CLASSES: frozenset[ImageReleaseEvidenceSourceClass] = (
    frozenset(
        {
            ImageReleaseEvidenceSourceClass.CURATED,
            ImageReleaseEvidenceSourceClass.REGISTRY_ATTESTED,
        }
    )
)

_DIGEST_PIN_PATTERN = re.compile(r"@sha256:[0-9a-f]{64}$")


class ImageGroundingStatus(StrEnum):
    """Bounded image-grounding states."""

    GROUNDED = "grounded"
    NO_DEPLOYMENT_BINDING = "no_deployment_binding"
    NO_STRICT_RELEASE_VERSION = "no_strict_release_version"
    NO_REPOSITORY_OBSERVATION = "no_repository_observation"
    OBSERVATION_MISMATCH = "observation_mismatch"
    MUTABLE_OBSERVATION = "mutable_observation"
    NO_IMAGE_RELEASE_EVIDENCE = "no_image_release_evidence"
    EVIDENCE_NOT_TRUSTED = "evidence_not_trusted"
    EVIDENCE_VERSION_MISMATCH = "evidence_version_mismatch"
    REPOSITORY_IDENTITY_MISMATCH = "repository_identity_mismatch"
    DIGEST_MISMATCH = "digest_mismatch"
    CONFLICTED = "conflicted"


class ImageGroundingResult(BaseModel):
    """Bounded, deterministic image-grounding result for one binding."""

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    schema_version: str = Field(
        default=IMAGE_GROUNDING_SCHEMA,
        pattern=r"^discovery-image-grounding-v1$",
    )
    status: ImageGroundingStatus
    # Bounded to the Discovery item id width. The evaluator truncates an
    # oversized caller id for this bounded result payload (never for
    # matching); an empty caller id is rejected here because of
    # ``min_length=1``.
    catalog_item_id: str = Field(min_length=1, max_length=64)
    # ``release_version`` and ``image_reference`` faithfully reflect the
    # caller-supplied input that drove the decision (a non-strict version, or
    # an observed identity longer than a canonical reference), so they carry
    # no max_length: the evaluator must return a bounded status, never raise.
    release_version: str | None = Field(default=None, min_length=1)
    image_reference: str | None = Field(default=None, min_length=1)
    image_digest: str | None = Field(default=None, max_length=71)
    reason: str | None = None


def parse_strict_release_version(version: str | None) -> bool:
    """Return True only for a strict numeric ``X.Y.Z`` release version.

    Strict means: three ASCII decimal components, no leading zeros (the
    exact component ``"0"`` is allowed), no pre-release suffix, no build
    metadata, and no surrounding whitespace. Mirrors the strict-version
    semantics used elsewhere in the Discovery Center.
    """

    if version is None:
        return False
    return re.fullmatch(_STRICT_RELEASE_VERSION_PATTERN, version) is not None


def _parse_digest_pinned_image(
    image: str,
) -> tuple[str, str] | None:
    """Split a digest-pinned image string into identity and digest.

    The identity is the lowercase repository/image reference that may
    carry a mutable tag (for example ``ghcr.io/foo/bar:1.2.3`` or
    ``ghcr.io/foo/bar``). The digest is the immutable ``sha256:`` hex
    portion. A tag-only or otherwise mutable image, a malformed digest
    suffix, an empty identity, or surrounding whitespace yields ``None``.
    """

    if image != image.strip():
        return None
    # A well-formed digest-pinned reference contains exactly one ``@``.
    # Any additional ``@`` (for example a repository name that merely
    # contains a ``sha256:`` substring) makes the reference unparseable and
    # therefore ungroundable.
    if image.count("@") != 1:
        return None
    match = _DIGEST_PIN_PATTERN.search(image)
    if match is None:
        return None
    identity = image[: match.start()]
    if not identity:
        return None
    if "@" in identity or identity.startswith("sha256:"):
        return None
    # Skip the leading ``@`` so the digest is exactly ``sha256:<64 hex>``.
    return identity, image[match.start() + 1 :]


def _result(
    status: ImageGroundingStatus,
    catalog_item_id: str,
    release_version: str | None = None,
    image_reference: str | None = None,
    image_digest: str | None = None,
    reason: str | None = None,
) -> ImageGroundingResult:
    return ImageGroundingResult(
        status=status,
        catalog_item_id=catalog_item_id,
        release_version=release_version,
        image_reference=image_reference,
        image_digest=image_digest,
        reason=reason,
    )


def _grounded(
    catalog_item_id: str,
    release_version: str,
    reference: str,
    digest: str,
) -> ImageGroundingResult:
    return _result(
        ImageGroundingStatus.GROUNDED,
        catalog_item_id,
        release_version,
        reference,
        digest,
        reason=None,
    )


def ground_deployment_image(
    *,
    catalog_item_id: str,
    deployment_binding: DeploymentBinding | None,
    release_version: str | None,
    repository_observation: RepositoryComposeImageObservation | None,
    image_release_evidence: tuple[ImageReleaseEvidence, ...],
) -> ImageGroundingResult:
    """Pure deterministic image grounding from already-collected contracts.

    The caller supplies the deployment binding, the release version under
    evaluation, the observed compose image string, and every
    image-release evidence row in scope. The result is bounded by
    :class:`ImageGroundingStatus`, fail-closed, and independent of the
    input evidence tuple order.
    """

    # The result model is bounded to the Discovery item id width. An
    # oversized caller id is truncated only for the bounded result payload
    # (never for matching), so a long id still yields a bounded status.
    # An empty caller id, however, is not truncated away: it is rejected by
    # the result model, whose ``catalog_item_id`` has ``min_length=1``.
    bounded_item_id = catalog_item_id[:64]

    if deployment_binding is None:
        return _result(
            ImageGroundingStatus.NO_DEPLOYMENT_BINDING,
            bounded_item_id,
            release_version,
            reason="no deployment binding",
        )

    if not parse_strict_release_version(release_version):
        return _result(
            ImageGroundingStatus.NO_STRICT_RELEASE_VERSION,
            bounded_item_id,
            release_version,
            reason="release version is not strict numeric X.Y.Z",
        )

    if repository_observation is None:
        return _result(
            ImageGroundingStatus.NO_REPOSITORY_OBSERVATION,
            bounded_item_id,
            release_version,
            reason="no repository compose image observation",
        )

    # A valid DeploymentBinding is always a docker-compose image binding by
    # construction, so only the compose file and service need comparing.
    if (
        repository_observation.compose_file != deployment_binding.compose_file
        or repository_observation.compose_service != deployment_binding.compose_service
    ):
        return _result(
            ImageGroundingStatus.OBSERVATION_MISMATCH,
            bounded_item_id,
            release_version,
            reason="observation compose file or service does not match the binding",
        )

    parsed = _parse_digest_pinned_image(repository_observation.image)
    if parsed is None:
        return _result(
            ImageGroundingStatus.MUTABLE_OBSERVATION,
            bounded_item_id,
            release_version,
            reason="observed image is not an immutable digest-pinned reference",
        )
    observed_reference, observed_digest = parsed

    if not image_release_evidence:
        return _result(
            ImageGroundingStatus.NO_IMAGE_RELEASE_EVIDENCE,
            bounded_item_id,
            release_version,
            observed_reference,
            reason="no image-release evidence",
        )

    # Compatibility is scoped to this item and this exact strict release
    # version, which is the set of evidence relevant to the decision.
    compatible = tuple(
        evidence
        for evidence in image_release_evidence
        if evidence.catalog_item_id == catalog_item_id
        and evidence.release_version == release_version
    )
    if not compatible:
        return _result(
            ImageGroundingStatus.EVIDENCE_VERSION_MISMATCH,
            bounded_item_id,
            release_version,
            observed_reference,
            reason="no image-release evidence for this exact release version",
        )

    # Conflict detection uses set semantics over the compatible set, so it is
    # independent of the input evidence tuple order. A single contradictory
    # row (trusted or not) fails the whole decision closed.
    conflict_keys = {
        (evidence.image_reference, evidence.image_digest) for evidence in compatible
    }
    if len(conflict_keys) > 1:
        return _result(
            ImageGroundingStatus.CONFLICTED,
            bounded_item_id,
            release_version,
            observed_reference,
            reason="image-release evidence conflicts for this release version",
        )

    trusted = tuple(
        evidence
        for evidence in compatible
        if evidence.source_class in TRUSTED_IMAGE_RELEASE_SOURCE_CLASSES
    )
    if not trusted:
        return _result(
            ImageGroundingStatus.EVIDENCE_NOT_TRUSTED,
            bounded_item_id,
            release_version,
            observed_reference,
            reason="no trusted image-release evidence for this release version",
        )

    # With no conflict, every compatible row shares one (reference, digest)
    # pair. Derive it from the single conflict key so the decision cannot
    # depend on which row the caller placed first in the tuple.
    evidence_reference, evidence_digest = next(iter(conflict_keys))

    if evidence_reference != observed_reference:
        return _result(
            ImageGroundingStatus.REPOSITORY_IDENTITY_MISMATCH,
            bounded_item_id,
            release_version,
            observed_reference,
            observed_digest,
            reason="observed repository/image identity does not match trusted evidence",
        )
    if evidence_digest != observed_digest:
        return _result(
            ImageGroundingStatus.DIGEST_MISMATCH,
            bounded_item_id,
            release_version,
            evidence_reference,
            observed_digest,
            reason="observed digest does not match trusted evidence",
        )
    return _grounded(
        bounded_item_id,
        release_version,
        evidence_reference,
        evidence_digest,
    )
