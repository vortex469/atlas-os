"""Inactive Home Assistant GHCR acquisition-to-verification integration.

This module is deliberately not exported or registered.  Construction is
inert; only an explicit collection call invokes the bounded GHCR acquirer.
"""

from __future__ import annotations

import asyncio
from enum import StrEnum

from app.discovery.home_assistant_ghcr_acquisition import (
    _EXPECTED_DIGEST,
    _IMAGE_REFERENCE,
    _RELEASE,
    _HomeAssistantGHCRAcquirer,
    _HomeAssistantGHCRAcquisitionError,
)
from app.discovery.home_assistant_sigstore_verifier import (
    _IDENTITY,
    _REF,
    _REPOSITORY,
    _WORKFLOW_NAME,
    _WORKFLOW_SHA,
    HomeAssistantSigstoreVerificationError,
    _VerifiedHomeAssistantAttestation,
    verify_home_assistant_2026_8_3_bundle,
)
from app.discovery.image_release_collector import (
    CANDIDATE_FACT_SCHEMA,
    CandidateImageReleaseFact,
    CollectionResult,
    CollectorHealth,
)
from app.discovery.models import (
    ImageReleaseEvidence,
    ImageReleaseEvidenceSourceClass,
)

_CATALOG_ITEM_ID = "home-assistant"
_SOURCE_ID = "collector:home-assistant-ghcr-cosign"


class HomeAssistantRegistryAttestedFailure(StrEnum):
    """Stable, non-sensitive integration failure vocabulary."""

    ACQUISITION_FAILED = "acquisition_failed"
    NO_VALID_SIGNATURE = "no_valid_signature"
    CRYPTOGRAPHIC_VERIFICATION_FAILED = "cryptographic_verification_failed"
    CONTRADICTORY_VERIFIED_SIGNATURES = "contradictory_verified_signatures"
    DIGEST_DISAGREEMENT = "digest_disagreement"
    RELEASE_IDENTITY_DISAGREEMENT = "release_identity_disagreement"
    MISSING_AUTHENTICATED_TIMESTAMP = "missing_authenticated_timestamp"


class HomeAssistantRegistryAttestedError(Exception):
    """A bounded integration failure that never contains lower-level detail."""

    def __init__(self, reason: HomeAssistantRegistryAttestedFailure) -> None:
        self.reason = reason
        super().__init__(reason.value)


class HomeAssistantRegistryAttestedAdapter:
    """Acquire and verify the single code-owned Home Assistant release."""

    def collect(self) -> CollectionResult:
        """Synchronously acquire, verify, reconcile, and construct in memory."""

        return asyncio.run(self.collect_async())

    async def collect_async(self) -> CollectionResult:
        """Async form of :meth:`collect`; this is the only I/O entry point."""

        try:
            acquired = await _HomeAssistantGHCRAcquirer().acquire()
        except _HomeAssistantGHCRAcquisitionError:
            raise HomeAssistantRegistryAttestedError(
                HomeAssistantRegistryAttestedFailure.ACQUISITION_FAILED
            ) from None
        except Exception:  # noqa: BLE001 - acquisition is a trust boundary
            raise HomeAssistantRegistryAttestedError(
                HomeAssistantRegistryAttestedFailure.ACQUISITION_FAILED
            ) from None

        if not acquired.sigstore_bundles:
            raise HomeAssistantRegistryAttestedError(
                HomeAssistantRegistryAttestedFailure.NO_VALID_SIGNATURE
            )

        verified: list[_VerifiedHomeAssistantAttestation] = []
        verification_failed = False
        for bundle_bytes in acquired.sigstore_bundles:
            try:
                verified.append(
                    verify_home_assistant_2026_8_3_bundle(bundle_bytes=bundle_bytes)
                )
            except HomeAssistantSigstoreVerificationError:
                verification_failed = True
            except Exception:  # noqa: BLE001 - verification is a trust boundary
                verification_failed = True

        if verification_failed:
            raise HomeAssistantRegistryAttestedError(
                HomeAssistantRegistryAttestedFailure.CRYPTOGRAPHIC_VERIFICATION_FAILED
            ) from None
        if not verified:
            raise HomeAssistantRegistryAttestedError(
                HomeAssistantRegistryAttestedFailure.NO_VALID_SIGNATURE
            )

        first = verified[0]
        if any(result != first for result in verified[1:]):
            raise HomeAssistantRegistryAttestedError(
                HomeAssistantRegistryAttestedFailure.CONTRADICTORY_VERIFIED_SIGNATURES
            )
        if acquired.index_digest != first.image_digest:
            raise HomeAssistantRegistryAttestedError(
                HomeAssistantRegistryAttestedFailure.DIGEST_DISAGREEMENT
            )
        if (
            acquired.release_version != _RELEASE
            or acquired.release_version != first.release_version
            or acquired.image_reference != _IMAGE_REFERENCE
        ):
            raise HomeAssistantRegistryAttestedError(
                HomeAssistantRegistryAttestedFailure.RELEASE_IDENTITY_DISAGREEMENT
            )
        if acquired.index_digest != _EXPECTED_DIGEST:
            raise HomeAssistantRegistryAttestedError(
                HomeAssistantRegistryAttestedFailure.DIGEST_DISAGREEMENT
            )
        if (
            first.authenticated_ref != _REF
            or first.authenticated_repository != _REPOSITORY
            or first.authenticated_workflow_identity != _IDENTITY
            or first.authenticated_workflow_name != _WORKFLOW_NAME
            or first.source_commit_sha != _WORKFLOW_SHA
        ):
            raise HomeAssistantRegistryAttestedError(
                HomeAssistantRegistryAttestedFailure.RELEASE_IDENTITY_DISAGREEMENT
            )
        if first.integrated_at is None or first.integrated_at.utcoffset() is None:
            raise HomeAssistantRegistryAttestedError(
                HomeAssistantRegistryAttestedFailure.MISSING_AUTHENTICATED_TIMESTAMP
            )

        candidate = CandidateImageReleaseFact(
            schema_version=CANDIDATE_FACT_SCHEMA,
            release_version=_RELEASE,
            image_reference=_IMAGE_REFERENCE,
            image_digest=_EXPECTED_DIGEST,
            attested_at=first.integrated_at,
        )
        row = ImageReleaseEvidence(
            catalog_item_id=_CATALOG_ITEM_ID,
            release_version=_RELEASE,
            image_reference=_IMAGE_REFERENCE,
            image_digest=_EXPECTED_DIGEST,
            source_class=ImageReleaseEvidenceSourceClass.REGISTRY_ATTESTED,
            source_id=_SOURCE_ID,
            attested_at=first.integrated_at,
        )
        return CollectionResult(
            descriptor_id=_CATALOG_ITEM_ID,
            health=CollectorHealth.HEALTHY,
            candidate=candidate,
            row=row,
        )
