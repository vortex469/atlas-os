"""Bounded, trusted image-release acquisition boundary (v0.14 P1b-collector).

First slice of the P1b-collector: the smallest trusted acquisition boundary
around ``ImageReleaseEvidence``. It provides immutable, code-owned acquisition
descriptors, an in-memory candidate/result contract, a typed failure
vocabulary, an empty production descriptor/adapter registry, and a narrow
collector API with fully injectable adapters and transport.

Trust model -- three separate identities:

* **Acquisition identity** is code-owned: the descriptor id, acquisition
  host, request path, and adapter identity come from the shipped
  (empty) descriptor registry. A remote payload can never select or modify
  any of them.
* **Claimed image identity** is the code-owned ``expected_image_reference``
  on the descriptor. It is independently validated and is deliberately NOT
  required to match the acquisition host (for example acquisition host
  ``api.github.com`` may claim image repository ``ghcr.io/vendor/project``).
* **Authority**: successful collection produces an in-memory candidate and
  row only. It does NOT create curated evidence, does NOT write the curated
  evidence directory, does NOT call the loader or grounding, and grants no
  deployment authority. The trust sequence continues: human review, then
  committed curated evidence, then the existing loader, then the existing
  grounding. This module stops before human promotion.

The production descriptor registry and source adapter registry are EMPTY.
No production network activity occurs: constructing the collector, importing
this module, or calling ``collect`` with the production registries performs
zero I/O (unknown descriptor or unregistered adapter fails typed before any
transport call). Tests inject fake descriptors and adapters.
"""

from __future__ import annotations

import asyncio
import re
from collections.abc import Mapping
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, Protocol, runtime_checkable

from pydantic import Field, ValidationError, field_validator, model_validator

from app.discovery.exceptions import ImageReleaseCollectorError
from app.discovery.image_release_collector_transport import (
    TransportFailure,
    parse_strict_json_object,
)
from app.discovery.models import (
    DiscoveryCenterModel,
    ImageReleaseEvidence,
    ImageReleaseEvidenceSourceClass,
)

CANDIDATE_FACT_SCHEMA = "collector-candidate-fact-v1"

_DESCRIPTOR_ID_PATTERN = r"^[a-z0-9]+(?:-[a-z0-9]+)*$"
_ACQUISITION_HOST_PATTERN = (
    r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?(?:\.[a-z0-9](?:[a-z0-9-]{0,61}"
    r"[a-z0-9])?)*$"
)
_ACQUISITION_PATH_PATTERN = r"^/[a-zA-Z0-9._~!$&'()*+;=%/-]*$"
_JSON_CONTENT_TYPE_PATTERN = re.compile(
    r"^application/json(?:\s*;\s*charset=(?:utf-8|\"utf-8\"))?$",
    re.IGNORECASE,
)


class CollectorHealth(StrEnum):
    """Collector-local health vocabulary.

    Collector-local only: it is NOT the discovery dynamic-source health and
    is not integrated with any health, projection, or evaluation contract.
    """

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNAVAILABLE = "unavailable"


class ImageReleaseCollectorFailure(StrEnum):
    """Collector-local typed failures for the acquisition boundary."""

    UNKNOWN_DESCRIPTOR = "unknown_descriptor"
    UNREGISTERED_ADAPTER = "unregistered_adapter"
    ACQUISITION_MISMATCH = "acquisition_mismatch"
    DNS_DISALLOWED = "dns_disallowed"
    CONNECTION_FAILED = "connection_failed"
    TIMEOUT = "timeout"
    TLS_FAILED = "tls_failed"
    REDIRECT_REFUSED = "redirect_refused"
    HTTP_ERROR = "http_error"
    RATE_LIMITED = "rate_limited"
    RESPONSE_TOO_LARGE = "response_too_large"
    INVALID_CONTENT_TYPE = "invalid_content_type"
    MALFORMED_JSON = "malformed_json"
    SCHEMA_INVALID = "schema_invalid"
    IMAGE_IDENTITY_MISMATCH = "image_identity_mismatch"
    RELEASE_VERSION_INVALID = "release_version_invalid"
    NO_STABLE_RELEASE = "no_stable_release"


# Deterministic local rule: which failures mean the source is unreachable at
# all versus reachable-but-degraded. This mapping is the single source of
# truth for both the result-model invariant and the collector's mapping of
# transport failure reasons.
_UNAVAILABLE_FAILURES = frozenset(
    {
        ImageReleaseCollectorFailure.DNS_DISALLOWED,
        ImageReleaseCollectorFailure.CONNECTION_FAILED,
        ImageReleaseCollectorFailure.TIMEOUT,
        ImageReleaseCollectorFailure.TLS_FAILED,
        ImageReleaseCollectorFailure.RATE_LIMITED,
    }
)

# Transport failure reasons (strings) -> collector failure vocabulary.
_TRANSPORT_FAILURE_REASONS = {
    "dns_disallowed": ImageReleaseCollectorFailure.DNS_DISALLOWED,
    "connection_failed": ImageReleaseCollectorFailure.CONNECTION_FAILED,
    "timeout": ImageReleaseCollectorFailure.TIMEOUT,
    "tls_failed": ImageReleaseCollectorFailure.TLS_FAILED,
    "http_error": ImageReleaseCollectorFailure.HTTP_ERROR,
    "response_too_large": ImageReleaseCollectorFailure.RESPONSE_TOO_LARGE,
    "invalid_content_type": ImageReleaseCollectorFailure.INVALID_CONTENT_TYPE,
    "malformed_json": ImageReleaseCollectorFailure.MALFORMED_JSON,
    "schema_invalid": ImageReleaseCollectorFailure.SCHEMA_INVALID,
}

# The only source class this boundary may attach to a collected row.
# ``curated`` is human-promotion only and ``registry_attested`` requires
# attestation material this boundary never validates, so an untrusted
# remote payload can at most claim upstream-signed provenance.
_COLLECTOR_SOURCE_CLASS = ImageReleaseEvidenceSourceClass.UPSTREAM_SIGNED


class _CandidateRevalidationFailed(Exception):
    """Adapter output violated the candidate contract structurally."""


class ImageReleaseSourceDescriptor(DiscoveryCenterModel):
    """Code-owned description of where Atlas may fetch image-release evidence.

    Every value here is selected by code, never by a remote payload. The
    acquisition host/path and the expected image repository identity are
    independently validated; nothing requires them to match.
    """

    descriptor_id: str = Field(
        min_length=3, max_length=64, pattern=_DESCRIPTOR_ID_PATTERN
    )
    acquisition_host: str = Field(min_length=1, max_length=253)
    acquisition_path: str = Field(min_length=2, max_length=512)
    expected_image_reference: str = Field(
        min_length=3,
        max_length=512,
        pattern=r"^([a-z0-9._-]+(?::[0-9]+)?/)?[a-z0-9._-]+(?:/[a-z0-9._-]+)*"
        r"(?::[a-z0-9._-]+)?$",
    )
    source_class: ImageReleaseEvidenceSourceClass
    adapter_id: str = Field(min_length=3, max_length=64, pattern=_DESCRIPTOR_ID_PATTERN)

    @field_validator("descriptor_id")
    @classmethod
    def reject_descriptor_id_whitespace(cls, value: str) -> str:
        if value != value.strip():
            raise ValueError("descriptor_id must not have surrounding whitespace.")
        return value

    @field_validator("acquisition_host", mode="before")
    @classmethod
    def normalize_acquisition_host(cls, value: Any) -> str:
        if not isinstance(value, str):
            raise TypeError("acquisition_host must be a string.")
        candidate = value.strip()
        if candidate != value or not candidate:
            raise ValueError("acquisition_host must not have surrounding whitespace.")
        lowered = candidate.lower()
        if candidate != lowered:
            raise ValueError("acquisition_host must be lowercase.")
        if "*" in lowered:
            raise ValueError("wildcard acquisition hosts are not allowed.")
        if not re.fullmatch(_ACQUISITION_HOST_PATTERN, lowered):
            raise ValueError(
                "acquisition_host must be a lowercase DNS hostname "
                "(no port, scheme, or userinfo)."
            )
        return lowered

    @field_validator("acquisition_path", mode="before")
    @classmethod
    def normalize_acquisition_path(cls, value: Any) -> str:
        if not isinstance(value, str):
            raise TypeError("acquisition_path must be a string.")
        candidate = value
        if candidate != candidate.strip():
            raise ValueError("acquisition_path must not have surrounding whitespace.")
        if not re.fullmatch(_ACQUISITION_PATH_PATTERN, candidate):
            raise ValueError(
                "acquisition_path must be an absolute path with no query, "
                "fragment, backslash, or control characters."
            )
        if ".." in candidate or candidate.rstrip("/") in {"", "."}:
            raise ValueError("acquisition_path must not contain dot segments.")
        return candidate

    @field_validator("expected_image_reference")
    @classmethod
    def reject_expected_image_reference_whitespace(cls, value: str) -> str:
        if value != value.strip():
            raise ValueError(
                "expected_image_reference must not have surrounding whitespace."
            )
        return value


class CandidateImageReleaseFact(DiscoveryCenterModel):
    """Untrusted-but-validated candidate fact for one image release.

    Produced in memory by a source-specific adapter after all source checks
    pass, before any promotion. It carries only what is needed to construct
    an ``ImageReleaseEvidence`` row; the descriptor identity, acquisition
    host/path, source class, and expected repository identity are NOT part
    of the candidate and cannot be chosen by a remote payload -- the
    collector re-derives them from the code-owned descriptor.
    """

    schema_version: str = Field(pattern=r"^collector-candidate-fact-v1$")
    release_version: str = Field(
        min_length=1,
        max_length=64,
        pattern=r"^(0|[1-9][0-9]{0,9})\.(0|[1-9][0-9]{0,9})\.(0|[1-9][0-9]{0,9})$",
    )
    image_reference: str = Field(
        min_length=3,
        max_length=512,
        pattern=r"^([a-z0-9._-]+(?::[0-9]+)?/)?[a-z0-9._-]+(?:/[a-z0-9._-]+)*"
        r"(?::[a-z0-9._-]+)?$",
    )
    image_digest: str = Field(
        min_length=71, max_length=71, pattern=r"^sha256:[0-9a-f]{64}$"
    )
    attested_at: datetime

    @field_validator("release_version")
    @classmethod
    def reject_release_version_whitespace(cls, value: str) -> str:
        if value != value.strip():
            raise ValueError("release_version must not have surrounding whitespace.")
        return value

    @field_validator("image_reference")
    @classmethod
    def reject_image_reference_whitespace(cls, value: str) -> str:
        if value != value.strip():
            raise ValueError("image_reference must not have surrounding whitespace.")
        return value

    @field_validator("attested_at")
    @classmethod
    def normalize_attested_at(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("attested_at must be timezone-aware.")
        return value.astimezone(UTC)


class CollectionResult(DiscoveryCenterModel):
    """Bounded, in-memory outcome of one collection attempt.

    Valid combinations are enforced: a healthy result has exactly a
    candidate and a row and no failure; a failed result has exactly one
    failure and no candidate or row, with health determined by the
    deterministic local rule over the failure vocabulary.
    """

    descriptor_id: str = Field(min_length=3, max_length=64)
    health: CollectorHealth
    candidate: CandidateImageReleaseFact | None = None
    row: ImageReleaseEvidence | None = None
    failure_reason: ImageReleaseCollectorFailure | None = None

    @model_validator(mode="after")
    def validate_shape(self) -> CollectionResult:
        success = self.health is CollectorHealth.HEALTHY
        if success != (self.candidate is not None and self.row is not None):
            raise ValueError("healthy results require a candidate and row only")
        if success == (self.failure_reason is not None):
            raise ValueError("failed results require exactly one controlled failure")
        if self.failure_reason is not None:
            expected = (
                CollectorHealth.UNAVAILABLE
                if self.failure_reason in _UNAVAILABLE_FAILURES
                else CollectorHealth.DEGRADED
            )
            if self.health is not expected:
                raise ValueError("health must match the controlled failure category")
        return self


@runtime_checkable
class ImageReleaseSourceAdapter(Protocol):
    """Source-specific validator/normalizer for one descriptor mechanism.

    An adapter is selected only through the code-owned adapter registry,
    keyed by its own ``source_id``. It receives the code-owned descriptor
    (read-only) and the bounded, strict-parsed JSON payload object; it may
    return a validated candidate or a typed failure. It cannot change the
    acquisition host/path, the descriptor identity, or the source class:
    those are re-derived from the descriptor by the collector.
    """

    source_id: str

    async def normalize(
        self, descriptor: ImageReleaseSourceDescriptor, payload: dict[str, object]
    ) -> CandidateImageReleaseFact | ImageReleaseCollectorFailure: ...


class ImageReleaseCollector:
    """Narrow, stateless, in-memory image-release collection boundary.

    Construction performs no I/O. ``collect`` resolves the code-owned
    descriptor and adapter first (unknown descriptor or unregistered
    adapter fails typed before any transport activity), fetches through the
    bounded transport, and normalizes in memory. There is no fallback
    parser, no persistence, no evidence-directory write, no loader or
    grounding call, no cache, and no deployment authority.
    """

    def __init__(
        self,
        *,
        descriptors: Mapping[str, ImageReleaseSourceDescriptor] | None = None,
        adapters: Mapping[str, Any] | None = None,
        transport: Any | None = None,
    ) -> None:
        if descriptors is None:
            descriptors = PRODUCTION_DESCRIPTORS
        if adapters is None:
            adapters = PRODUCTION_SOURCE_ADAPTERS
        if transport is None:
            from app.discovery.image_release_collector_transport import PinnedHTTPS

            transport = PinnedHTTPS()
        self._descriptors = descriptors
        self._adapters = adapters
        self._transport = transport

    @classmethod
    def production(cls) -> ImageReleaseCollector:
        """A collector over the shipped (empty) production registries."""

        return cls()

    def collect(
        self,
        descriptor: ImageReleaseSourceDescriptor | str,
    ) -> CollectionResult:
        """Collect one candidate for a code-owned descriptor.

        Accepts a descriptor object (re-validated strictly) or a descriptor
        id looked up in the code-owned registry. All outcomes -- including
        unknown descriptor, unregistered adapter, and every acquisition
        failure -- are returned as a typed :class:`CollectionResult`; no
        exception escapes except programming errors such as a malformed
        descriptor object.
        """

        if isinstance(descriptor, str):
            descriptor = self._descriptors.get(descriptor)
            if descriptor is None:
                return self._failure(
                    "unknown", ImageReleaseCollectorFailure.UNKNOWN_DESCRIPTOR
                )
            return self._collect(descriptor)
        if not isinstance(descriptor, ImageReleaseSourceDescriptor):
            raise ImageReleaseCollectorError(
                "collect() requires a descriptor id or an ImageReleaseSourceDescriptor."
            )
        return self._collect(descriptor)

    async def collect_async(
        self,
        descriptor: ImageReleaseSourceDescriptor | str,
    ) -> CollectionResult:
        """Async form of :meth:`collect` for event-loop hosts."""

        if isinstance(descriptor, str):
            descriptor = self._descriptors.get(descriptor)
            if descriptor is None:
                return self._failure(
                    "unknown", ImageReleaseCollectorFailure.UNKNOWN_DESCRIPTOR
                )
            return await self._collect_async(descriptor)
        if not isinstance(descriptor, ImageReleaseSourceDescriptor):
            raise ImageReleaseCollectorError(
                "collect_async() requires a descriptor id or an "
                "ImageReleaseSourceDescriptor."
            )
        return await self._collect_async(descriptor)

    def _collect(self, descriptor: ImageReleaseSourceDescriptor) -> CollectionResult:
        return asyncio.run(self._collect_async(descriptor))

    async def _collect_async(
        self, descriptor: ImageReleaseSourceDescriptor
    ) -> CollectionResult:
        # Every identity check happens before any transport activity.
        descriptor = ImageReleaseSourceDescriptor.model_validate(
            descriptor.model_dump()
        )
        adapter = self._adapters.get(descriptor.adapter_id)
        if adapter is None:
            return self._failure(
                descriptor.descriptor_id,
                ImageReleaseCollectorFailure.UNREGISTERED_ADAPTER,
            )
        if getattr(adapter, "source_id", None) != descriptor.adapter_id:
            return self._failure(
                descriptor.descriptor_id,
                ImageReleaseCollectorFailure.ACQUISITION_MISMATCH,
            )

        try:
            response = await self._transport.fetch(
                host=descriptor.acquisition_host,
                path=descriptor.acquisition_path,
            )
        except TransportFailure as exc:
            return self._failure(
                descriptor.descriptor_id,
                _TRANSPORT_FAILURE_REASONS.get(
                    exc.reason, ImageReleaseCollectorFailure.CONNECTION_FAILED
                ),
            )
        except Exception:  # noqa: BLE001 - the transport is a trust boundary
            return self._failure(
                descriptor.descriptor_id,
                ImageReleaseCollectorFailure.CONNECTION_FAILED,
            )

        if 300 <= response.status_code < 400:
            return self._failure(
                descriptor.descriptor_id,
                ImageReleaseCollectorFailure.REDIRECT_REFUSED,
            )
        if response.status_code in {403, 429} and response.rate_limited:
            return self._failure(
                descriptor.descriptor_id,
                ImageReleaseCollectorFailure.RATE_LIMITED,
            )
        if not 200 <= response.status_code < 300:
            return self._failure(
                descriptor.descriptor_id, ImageReleaseCollectorFailure.HTTP_ERROR
            )
        if _JSON_CONTENT_TYPE_PATTERN.fullmatch(response.content_type) is None:
            return self._failure(
                descriptor.descriptor_id,
                ImageReleaseCollectorFailure.INVALID_CONTENT_TYPE,
            )

        try:
            payload = parse_strict_json_object(response.body)
        except TransportFailure as exc:
            return self._failure(
                descriptor.descriptor_id,
                _TRANSPORT_FAILURE_REASONS.get(
                    exc.reason, ImageReleaseCollectorFailure.MALFORMED_JSON
                ),
            )

        try:
            normalized = await adapter.normalize(descriptor, payload)
        except Exception:  # noqa: BLE001 - adapters are a trust boundary
            return self._failure(
                descriptor.descriptor_id,
                ImageReleaseCollectorFailure.SCHEMA_INVALID,
            )
        if isinstance(normalized, ImageReleaseCollectorFailure):
            return self._failure(descriptor.descriptor_id, normalized)

        try:
            candidate = self._validate_candidate(descriptor, normalized)
        except _CandidateRevalidationFailed:
            return self._failure(
                descriptor.descriptor_id,
                ImageReleaseCollectorFailure.SCHEMA_INVALID,
            )
        if candidate is None:
            return self._failure(
                descriptor.descriptor_id,
                ImageReleaseCollectorFailure.IMAGE_IDENTITY_MISMATCH,
            )
        try:
            row = build_evidence_row(descriptor, candidate)
        except ValidationError:
            return self._failure(
                descriptor.descriptor_id,
                ImageReleaseCollectorFailure.RELEASE_VERSION_INVALID,
            )
        return CollectionResult(
            descriptor_id=descriptor.descriptor_id,
            health=CollectorHealth.HEALTHY,
            candidate=candidate,
            row=row,
        )

    @staticmethod
    def _validate_candidate(
        descriptor: ImageReleaseSourceDescriptor,
        normalized: CandidateImageReleaseFact,
    ) -> CandidateImageReleaseFact | None:
        # Re-validate strictly: an adapter must not bypass the candidate
        # contract (schema version, version format, digest shape, tz-aware
        # time). Structural violations are SCHEMA_INVALID.
        if not isinstance(normalized, CandidateImageReleaseFact):
            raise _CandidateRevalidationFailed()
        try:
            candidate = CandidateImageReleaseFact.model_validate(
                normalized.model_dump()
            )
        except ValidationError:
            raise _CandidateRevalidationFailed() from None
        # The payload may never replace the code-owned image identity.
        if candidate.image_reference != descriptor.expected_image_reference:
            return None
        return candidate

    @staticmethod
    def _failure(
        descriptor_id: str, failure: ImageReleaseCollectorFailure
    ) -> CollectionResult:
        health = (
            CollectorHealth.UNAVAILABLE
            if failure in _UNAVAILABLE_FAILURES
            else CollectorHealth.DEGRADED
        )
        return CollectionResult(
            descriptor_id=descriptor_id,
            health=health,
            failure_reason=failure,
        )


def build_evidence_row(
    descriptor: ImageReleaseSourceDescriptor,
    candidate: CandidateImageReleaseFact,
) -> ImageReleaseEvidence:
    """Construct the in-memory evidence row for a validated candidate.

    Every authority-carrying value is re-derived from the code-owned
    descriptor: ``source_id`` is a deterministic code-owned template,
    ``source_class`` is the collector-owned class, ``catalog_item_id`` is
    the descriptor identity. The candidate contributes only the release
    version, image identity, digest, and attested time. The row is pure
    data: construction performs no I/O and creates no authority.
    """

    return ImageReleaseEvidence(
        catalog_item_id=descriptor.descriptor_id,
        release_version=candidate.release_version,
        image_reference=candidate.image_reference,
        image_digest=candidate.image_digest,
        source_class=_COLLECTOR_SOURCE_CLASS,
        source_id=f"collector:{descriptor.descriptor_id}",
        attested_at=candidate.attested_at,
    )


#: Shipped production descriptor registry: EMPTY by design. No real upstream
#: source (no GitHub, registry, Frigate, or Home Assistant descriptor) is
#: active in production.
PRODUCTION_DESCRIPTORS: Mapping[str, ImageReleaseSourceDescriptor] = {}

#: Shipped production source-adapter registry: EMPTY by design.
PRODUCTION_SOURCE_ADAPTERS: Mapping[str, Any] = {}
