from __future__ import annotations

import re
from collections.abc import Mapping
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

CATALOG_SCHEMA_VERSION = 1
DISCOVERY_ID_PATTERN = r"^[a-z0-9]+(?:-[a-z0-9]+)*$"


class DiscoveryCenterModel(BaseModel):
    """Base immutable model for Discovery Center domain contracts."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
    )


class DiscoveryItemType(StrEnum):
    """Initial provider-neutral Discovery Center item types."""

    APPLICATION = "application"
    SERVICE = "service"
    CONTAINER_IMAGE = "container_image"
    AI_MODEL = "ai_model"
    INTEGRATION = "integration"
    HARDWARE_DEVICE = "hardware_device"
    DEPLOYMENT_METHOD = "deployment_method"


class DiscoveryItemStatus(StrEnum):
    """Catalog lifecycle status for a discovered item definition."""

    ACTIVE = "active"
    DEPRECATED = "deprecated"
    EXPERIMENTAL = "experimental"
    UNKNOWN = "unknown"


class DiscoveryRelationshipType(StrEnum):
    """Provider-neutral relationships between catalog items and capabilities."""

    DEPENDS_ON = "depends_on"
    PROVIDES = "provides"
    CONSUMES = "consumes"
    REQUIRES = "requires"
    INTEGRATES_WITH = "integrates_with"
    CONFLICTS_WITH = "conflicts_with"
    RUNS_ON = "runs_on"
    DEPLOYED_BY = "deployed_by"
    COMPATIBLE_WITH = "compatible_with"
    INCOMPATIBLE_WITH = "incompatible_with"


class CatalogSourceType(StrEnum):
    """Kinds of catalog sources that may produce Discovery Center entries."""

    CURATED = "curated"
    PRIVATE = "private"
    COMMUNITY = "community"
    DYNAMIC = "dynamic"


class CatalogTrustLevel(StrEnum):
    """Trust levels assigned to catalog facts."""

    CURATED = "curated"
    VERIFIED = "verified"
    COMMUNITY = "community"
    PRIVATE = "private"
    DYNAMIC = "dynamic"


class CapabilityReference(DiscoveryCenterModel):
    """Minimal reference to a capability identifier."""

    id: str = Field(pattern=DISCOVERY_ID_PATTERN)


class ResourceRequirements(DiscoveryCenterModel):
    """Minimum resource requirements for a Discovery Center item."""

    cpu_cores_min: float | None = Field(default=None, ge=0)
    memory_mb_min: int | None = Field(default=None, ge=0)
    storage_gb_min: float | None = Field(default=None, ge=0)
    gpu_required: bool = False
    gpu_memory_gb_min: float | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def validate_gpu_memory_requires_gpu(self) -> ResourceRequirements:
        if self.gpu_memory_gb_min is not None and not self.gpu_required:
            raise ValueError("gpu_memory_gb_min requires gpu_required=true.")
        return self


class PlatformRequirements(DiscoveryCenterModel):
    """Platform constraints required by a Discovery Center item."""

    architectures: tuple[str, ...] = ()
    operating_systems: tuple[str, ...] = ()
    runtimes: tuple[str, ...] = ()
    devices: tuple[str, ...] = ()

    @field_validator(
        "architectures",
        "operating_systems",
        "runtimes",
        "devices",
        mode="before",
    )
    @classmethod
    def normalize_string_tuple(cls, value: Any) -> tuple[str, ...]:
        return normalize_unique_tuple(value)


class PortRequirement(DiscoveryCenterModel):
    """Network port requirement exposed or consumed by an item."""

    port: int = Field(ge=1, le=65535)
    protocol: Literal["tcp", "udp"] = "tcp"
    direction: Literal["inbound", "outbound"] = "inbound"
    required: bool = True
    description: str = ""

    @field_validator("protocol", "direction", mode="before")
    @classmethod
    def normalize_literal(cls, value: str) -> str:
        if not isinstance(value, str):
            return value
        return value.strip().lower()


class NetworkRequirements(DiscoveryCenterModel):
    """Network requirements for a Discovery Center item."""

    ports: tuple[PortRequirement, ...] = ()
    requires_internet: bool = False
    requires_lan: bool = False
    notes: tuple[str, ...] = ()

    @field_validator("notes", mode="before")
    @classmethod
    def normalize_notes(cls, value: Any) -> tuple[str, ...]:
        return normalize_unique_tuple(value, lowercase=False)


class DiscoveryRequirements(DiscoveryCenterModel):
    """Structured requirements used by future deterministic compatibility checks."""

    capabilities: tuple[CapabilityReference, ...] = ()
    resources: ResourceRequirements = Field(default_factory=ResourceRequirements)
    platform: PlatformRequirements = Field(default_factory=PlatformRequirements)
    network: NetworkRequirements = Field(default_factory=NetworkRequirements)

    @field_validator("capabilities")
    @classmethod
    def validate_unique_capability_ids(
        cls,
        values: tuple[CapabilityReference, ...],
    ) -> tuple[CapabilityReference, ...]:
        capability_ids = [capability.id for capability in values]
        if len(capability_ids) != len(set(capability_ids)):
            raise ValueError("requirement capability ids must be unique.")
        return values


class DiscoveryRelationship(DiscoveryCenterModel):
    """Structured relationship between catalog items or capabilities."""

    type: DiscoveryRelationshipType
    target: str = Field(min_length=1)
    required: bool = True
    minimum_version: str | None = None
    maximum_version: str | None = None
    description: str = ""
    metadata: Mapping[str, Any] = Field(default_factory=dict)

    @field_validator("target", mode="before")
    @classmethod
    def normalize_target(cls, value: str) -> str:
        if not isinstance(value, str):
            return value
        normalized = value.strip()
        if not normalized:
            raise ValueError("relationship target must not be empty.")
        return normalized


class DiscoveryItem(DiscoveryCenterModel):
    """Provider-neutral description of a cataloged thing."""

    id: str = Field(pattern=DISCOVERY_ID_PATTERN)
    type: DiscoveryItemType
    status: DiscoveryItemStatus = DiscoveryItemStatus.ACTIVE
    name: str = Field(min_length=1)
    description: str = ""
    version: str | None = None
    aliases: tuple[str, ...] = ()
    tags: tuple[str, ...] = ()
    homepage_url: str | None = None
    documentation_url: str | None = None
    capabilities: tuple[CapabilityReference, ...] = ()
    requirements: DiscoveryRequirements = Field(default_factory=DiscoveryRequirements)
    relationships: tuple[DiscoveryRelationship, ...] = ()
    metadata: Mapping[str, Any] = Field(default_factory=dict)

    @field_validator("aliases", mode="before")
    @classmethod
    def normalize_aliases(cls, value: Any) -> tuple[str, ...]:
        return normalize_unique_tuple(value, lowercase=False)

    @field_validator("tags", mode="before")
    @classmethod
    def normalize_tags(cls, value: Any) -> tuple[str, ...]:
        return normalize_unique_tuple(value)

    @field_validator("capabilities")
    @classmethod
    def validate_unique_capability_ids(
        cls,
        values: tuple[CapabilityReference, ...],
    ) -> tuple[CapabilityReference, ...]:
        capability_ids = [capability.id for capability in values]
        if len(capability_ids) != len(set(capability_ids)):
            raise ValueError("capability ids must be unique.")
        return values

    @field_validator("relationships")
    @classmethod
    def validate_unique_relationships(
        cls,
        values: tuple[DiscoveryRelationship, ...],
    ) -> tuple[DiscoveryRelationship, ...]:
        relationship_keys = [
            (relationship.type, relationship.target) for relationship in values
        ]
        if len(relationship_keys) != len(set(relationship_keys)):
            raise ValueError("relationship type and target pairs must be unique.")
        return values


class CatalogProvenance(DiscoveryCenterModel):
    """Metadata describing where a catalog fact came from."""

    source_type: CatalogSourceType = CatalogSourceType.CURATED
    source: str = Field(min_length=1)
    entry_id: str | None = Field(default=None, pattern=DISCOVERY_ID_PATTERN)
    version: str | None = None
    trust_level: CatalogTrustLevel = CatalogTrustLevel.CURATED


class CuratedReleaseClaim(DiscoveryCenterModel):
    """Explicit curated assertion used only for release-conflict evaluation."""

    version: str = Field(
        min_length=1, max_length=64, pattern=r"^[0-9]+\.[0-9]+\.[0-9]+$"
    )
    published_at: datetime

    @field_validator("published_at")
    @classmethod
    def normalize_published_at(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("published_at must be timezone-aware")
        return value.astimezone(UTC)


class ImageReleaseEvidenceSourceClass(StrEnum):
    """Provenance classes for immutable image-release evidence."""

    CURATED = "curated"
    REGISTRY_ATTESTED = "registry_attested"
    UPSTREAM_SIGNED = "upstream_signed"


# Image identity (optional registry, repository path, optional tag) but
# never a digest suffix. Compared for exact equality against the identity
# portion of a digest-pinned observed image reference.
_IMAGE_REFERENCE_PATTERN = (
    r"^([a-z0-9._-]+(?::[0-9]+)?/)?[a-z0-9._-]+(?:/[a-z0-9._-]+)*"
    r"(?::[a-z0-9._-]+)?$"
)
_SHA256_DIGEST_PATTERN = r"^sha256:[0-9a-f]{64}$"
# Strict numeric ``X.Y.Z``. Each component is the exact ``"0"`` or a decimal
# integer with no leading zero, bounded to 10 digits (the width of the
# largest 31-bit signed integer). Mirrors the strict-version semantics used
# elsewhere in the Discovery Center.
_STRICT_RELEASE_VERSION_PATTERN = (
    r"^(0|[1-9][0-9]{0,9})\.(0|[1-9][0-9]{0,9})\.(0|[1-9][0-9]{0,9})$"
)


class ImageReleaseEvidence(DiscoveryCenterModel):
    """Immutable attestation that one strict release of one catalog item is
    published as one exact container image digest.

    The contract is data only: it carries no mutable tag, no executable
    value, and no execution intent. It is inert in v0.14 P1a and has no
    production consumer.
    """

    catalog_item_id: str = Field(
        min_length=1, max_length=64, pattern=DISCOVERY_ID_PATTERN
    )
    release_version: str = Field(
        min_length=1, max_length=64, pattern=_STRICT_RELEASE_VERSION_PATTERN
    )
    image_reference: str = Field(
        min_length=3, max_length=512, pattern=_IMAGE_REFERENCE_PATTERN
    )
    image_digest: str = Field(
        min_length=71, max_length=71, pattern=_SHA256_DIGEST_PATTERN
    )
    source_class: ImageReleaseEvidenceSourceClass
    source_id: str = Field(min_length=1, max_length=256)
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

    @field_validator("source_id")
    @classmethod
    def reject_source_id_whitespace(cls, value: str) -> str:
        if value != value.strip():
            raise ValueError("source_id must not have surrounding whitespace.")
        return value

    @field_validator("attested_at")
    @classmethod
    def normalize_attested_at(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("attested_at must be timezone-aware.")
        return value.astimezone(UTC)


class RepositoryComposeImageObservation(DiscoveryCenterModel):
    """Observed image string for one compose file and service in a target
    repository.

    The observation is data only: it records what a deployment file says at
    one point in time. It performs no filesystem read, registry resolution,
    or tag resolution; those responsibilities belong to the caller that
    constructs the observation. It is inert in v0.14 P1a and has no
    production consumer.
    """

    compose_file: str = Field(min_length=1, max_length=512)
    compose_service: str = Field(min_length=1, max_length=255)
    image: str = Field(min_length=1, max_length=1024)

    @field_validator("compose_file", mode="before")
    @classmethod
    def normalize_observed_compose_file(cls, value: Any) -> str:
        if not isinstance(value, str):
            raise TypeError("compose_file must be a string.")
        candidate = value
        if candidate != candidate.strip():
            raise ValueError("compose_file must not have surrounding whitespace.")
        if "\\" in candidate:
            raise ValueError("compose_file must not contain backslashes.")
        if candidate.startswith("/"):
            raise ValueError("compose_file must be repository-relative.")
        if candidate.startswith("~"):
            raise ValueError("compose_file must be repository-relative.")
        if re.match(r"^[A-Za-z]:[\\/]", candidate):
            raise ValueError("compose_file must not contain drive letters.")
        segments = candidate.split("/")
        if any(segment in ("", ".", "..") for segment in segments):
            raise ValueError(
                "compose_file must not contain traversal or empty segments."
            )
        if len(segments) > 32:
            raise ValueError("compose_file path depth exceeds the bound.")
        if not segments[-1].endswith((".yaml", ".yml")):
            raise ValueError(
                "compose_file must end with a lowercase .yaml or .yml extension."
            )
        return candidate

    @field_validator("compose_service", mode="before")
    @classmethod
    def normalize_observed_compose_service(cls, value: Any) -> str:
        if not isinstance(value, str):
            raise TypeError("compose_service must be a string.")
        candidate = value
        if candidate != candidate.strip():
            raise ValueError("compose_service must not have surrounding whitespace.")
        if "/" in candidate:
            raise ValueError("compose_service must not contain path separators.")
        if not re.fullmatch(r"[a-z0-9][a-z0-9_.-]*", candidate):
            raise ValueError("compose_service must be a compose service identifier.")
        return candidate


class DeploymentBinding(DiscoveryCenterModel):
    """Curated repository deployment knowledge for a catalog item.

    The binding is declarative data only. It carries no executable values:
    no image tag, desired value, command, target ID, approval level, or
    execution intent. It is not exposed through the public API in P0.
    """

    compose_file: str = Field(min_length=1, max_length=512)
    compose_service: str = Field(min_length=1, max_length=255)
    mutable_property: Literal["image"] = "image"
    deployment_method: Literal["docker-compose"] = "docker-compose"

    @field_validator("compose_file", mode="before")
    @classmethod
    def normalize_compose_file(cls, value: Any) -> str:
        if not isinstance(value, str):
            raise TypeError("compose_file must be a string.")
        candidate = value
        if candidate != candidate.strip():
            raise ValueError("compose_file must not have surrounding whitespace.")
        if "\\" in candidate:
            raise ValueError("compose_file must not contain backslashes.")
        if candidate.startswith("/"):
            raise ValueError("compose_file must be repository-relative.")
        if candidate.startswith("~"):
            raise ValueError("compose_file must be repository-relative.")
        if re.match(r"^[A-Za-z]:[\\/]", candidate):
            raise ValueError("compose_file must not contain drive letters.")
        segments = candidate.split("/")
        if any(segment in ("", ".", "..") for segment in segments):
            raise ValueError(
                "compose_file must not contain traversal or empty segments."
            )
        if len(segments) > 32:
            raise ValueError("compose_file path depth exceeds the bound.")
        if not segments[-1].endswith((".yaml", ".yml")):
            raise ValueError(
                "compose_file must end with a lowercase .yaml or .yml extension."
            )
        return candidate

    @field_validator("compose_service", mode="before")
    @classmethod
    def normalize_compose_service(cls, value: Any) -> str:
        if not isinstance(value, str):
            raise TypeError("compose_service must be a string.")
        candidate = value
        if candidate != candidate.strip():
            raise ValueError("compose_service must not have surrounding whitespace.")
        if "/" in candidate:
            raise ValueError("compose_service must not contain path separators.")
        if not re.fullmatch(r"[a-z0-9][a-z0-9_.-]*", candidate):
            raise ValueError(
                "compose_service must be a compose service identifier.",
            )
        return candidate


class CatalogEntry(DiscoveryCenterModel):
    """Catalog record wrapper around a Discovery Center item."""

    schema_version: int = CATALOG_SCHEMA_VERSION
    item: DiscoveryItem
    provenance: CatalogProvenance
    deployment_binding: DeploymentBinding | None = None
    release_claim: CuratedReleaseClaim | None = None
    metadata: Mapping[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_schema_version(self) -> CatalogEntry:
        if self.schema_version != CATALOG_SCHEMA_VERSION:
            raise ValueError("unsupported catalog schema version.")
        return self

    @model_validator(mode="after")
    def validate_deployment_binding_requires_curated_provenance(self) -> CatalogEntry:
        if self.deployment_binding is not None and (
            self.provenance.source_type is not CatalogSourceType.CURATED
            or self.provenance.trust_level is not CatalogTrustLevel.CURATED
        ):
            raise ValueError(
                "deployment_binding requires source_type and trust_level 'curated'.",
            )
        return self


def normalize_unique_tuple(
    value: Any,
    *,
    lowercase: bool = True,
) -> tuple[str, ...]:
    """Normalize a sequence of strings and reject duplicates or blanks."""

    if value is None:
        return ()
    if isinstance(value, str):
        candidates = (value,)
    else:
        candidates = tuple(value)

    normalized: list[str] = []
    for candidate in candidates:
        if not isinstance(candidate, str):
            raise TypeError("values must be strings.")
        item = candidate.strip()
        if not item:
            raise ValueError("values must not be empty.")
        if lowercase:
            item = item.lower()
        normalized.append(item)

    if len(normalized) != len(set(normalized)):
        raise ValueError("values must be unique.")
    return tuple(normalized)
