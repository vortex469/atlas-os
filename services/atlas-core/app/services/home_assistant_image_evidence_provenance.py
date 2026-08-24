"""Read-only provenance projection for accepted Home Assistant image evidence.

This module projects one reviewed, repository-owned evidence row against one
closed verification profile.  It performs no cryptographic verification,
remote acquisition, clock access, or operational action.
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from app.discovery.image_release_evidence_loader import ImageReleaseEvidenceLoader
from app.discovery.models import (
    ImageReleaseEvidence,
    ImageReleaseEvidenceSourceClass,
)

_CATALOG_ITEM_ID = "home-assistant"
_RELEASE_VERSION = "2026.8.3"
_IMAGE_REFERENCE = "ghcr.io/home-assistant/home-assistant"
_IMAGE_DIGEST = (
    "sha256:14931c6b13756317849f46da1d01b45937a1150db66c081cfe529d48215943fe"
)
_SOURCE_CLASS = ImageReleaseEvidenceSourceClass.REGISTRY_ATTESTED
_SOURCE_ID = "collector:home-assistant-ghcr-cosign"
_ATTESTED_AT = datetime(2026, 8, 21, 20, 54, 36, tzinfo=UTC)

_VERIFICATION_MECHANISM = "sigstore_bundle_v0_3"
_VERIFICATION_PROFILE_ID = "home-assistant-ghcr-cosign-2026.8.3-v1"
_BUNDLE_SHA256 = "733e4755b02bb6786eeb51942dff588e8f043dcca13bc99a2b9fe0dd3e225520"
_TRUST_ROOT_SHA256 = "6494e21ea73fa7ee769f85f57d5a3e6a08725eae1e38c755fc3517c9e6bc0b66"
_ISSUER = "https://token.actions.githubusercontent.com"
_REPOSITORY = "home-assistant/core"
_WORKFLOW_IDENTITY = "https://github.com/home-assistant/core/.github/workflows/builder.yml@refs/tags/2026.8.3"
_WORKFLOW_NAME = "Build images"
_REF = "refs/tags/2026.8.3"
_SOURCE_COMMIT_SHA = "759e4658f40b3ccb671d418b8a0ed95224bf4561"

# This tuple is the reviewed meaning of the stable profile identifier.  The
# service checks it before projection so an incomplete or accidental constant
# edit fails closed rather than silently changing what the identifier means.
_REVIEWED_VERIFICATION_PROFILE_BINDING = (
    "home-assistant-ghcr-cosign-2026.8.3-v1",
    "sigstore_bundle_v0_3",
    "733e4755b02bb6786eeb51942dff588e8f043dcca13bc99a2b9fe0dd3e225520",
    "6494e21ea73fa7ee769f85f57d5a3e6a08725eae1e38c755fc3517c9e6bc0b66",
    "https://token.actions.githubusercontent.com",
    "home-assistant/core",
    "https://github.com/home-assistant/core/.github/workflows/builder.yml@refs/tags/2026.8.3",
    "Build images",
    "refs/tags/2026.8.3",
    "759e4658f40b3ccb671d418b8a0ed95224bf4561",
)


class HomeAssistantImageEvidenceReverificationState(StrEnum):
    """Meaning of the accepted row relative to the supported local profile."""

    VERIFIED_CURRENT_PROFILE = "verified_current_profile"


class HomeAssistantImageEvidenceProvenance(BaseModel):
    """Immutable informational projection of one accepted provenance row."""

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    catalog_item_id: str
    release_version: str
    image_reference: str
    image_digest: str
    source_class: ImageReleaseEvidenceSourceClass
    source_id: str
    attested_at: datetime
    verification_mechanism: str
    verification_profile_id: str
    bundle_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    trust_root_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    issuer: str
    repository: str
    workflow_identity: str
    workflow_name: str
    ref: str
    source_commit_sha: str = Field(pattern=r"^[0-9a-f]{40}$")
    reverification_state: HomeAssistantImageEvidenceReverificationState


class HomeAssistantImageEvidenceProvenanceError(RuntimeError):
    """Accepted evidence or its code-owned profile is unavailable or invalid."""


class HomeAssistantImageEvidenceProvenanceService:
    """Project the fixed accepted evidence row without external side effects."""

    def get(self) -> HomeAssistantImageEvidenceProvenance:
        """Return the fixed provenance projection, failing closed on drift."""

        if _current_verification_profile_binding() != (
            _REVIEWED_VERIFICATION_PROFILE_BINDING
        ):
            raise HomeAssistantImageEvidenceProvenanceError(
                "Home Assistant verification profile does not match its reviewed binding."
            )

        loader_failed = False
        try:
            rows = ImageReleaseEvidenceLoader().load().rows
        except Exception:  # noqa: BLE001 - project all loader failures safely.
            loader_failed = True
        if loader_failed:
            raise HomeAssistantImageEvidenceProvenanceError(
                "The accepted image evidence set could not be loaded."
            ) from None
        matching = tuple(row for row in rows if row.source_id == _SOURCE_ID)
        if len(matching) != 1:
            raise HomeAssistantImageEvidenceProvenanceError(
                "The accepted Home Assistant provenance row is unavailable."
            )
        row = matching[0]
        if not _matches_accepted_evidence(row):
            raise HomeAssistantImageEvidenceProvenanceError(
                "The accepted Home Assistant provenance row does not match the reviewed profile."
            )

        return HomeAssistantImageEvidenceProvenance(
            catalog_item_id=row.catalog_item_id,
            release_version=row.release_version,
            image_reference=row.image_reference,
            image_digest=row.image_digest,
            source_class=row.source_class,
            source_id=row.source_id,
            attested_at=row.attested_at,
            verification_mechanism=_VERIFICATION_MECHANISM,
            verification_profile_id=_VERIFICATION_PROFILE_ID,
            bundle_sha256=_BUNDLE_SHA256,
            trust_root_sha256=_TRUST_ROOT_SHA256,
            issuer=_ISSUER,
            repository=_REPOSITORY,
            workflow_identity=_WORKFLOW_IDENTITY,
            workflow_name=_WORKFLOW_NAME,
            ref=_REF,
            source_commit_sha=_SOURCE_COMMIT_SHA,
            reverification_state=HomeAssistantImageEvidenceReverificationState.VERIFIED_CURRENT_PROFILE,
        )


def _matches_accepted_evidence(row: ImageReleaseEvidence) -> bool:
    return (
        row.catalog_item_id == _CATALOG_ITEM_ID
        and row.release_version == _RELEASE_VERSION
        and row.image_reference == _IMAGE_REFERENCE
        and row.image_digest == _IMAGE_DIGEST
        and row.source_class is _SOURCE_CLASS
        and row.source_id == _SOURCE_ID
        and row.attested_at == _ATTESTED_AT
    )


def _current_verification_profile_binding() -> tuple[str, ...]:
    return (
        _VERIFICATION_PROFILE_ID,
        _VERIFICATION_MECHANISM,
        _BUNDLE_SHA256,
        _TRUST_ROOT_SHA256,
        _ISSUER,
        _REPOSITORY,
        _WORKFLOW_IDENTITY,
        _WORKFLOW_NAME,
        _REF,
        _SOURCE_COMMIT_SHA,
    )
