"""Bounded public projection of the local image-grounding read model."""

from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.discovery.models import ImageReleaseEvidenceSourceClass

from ..services.discovery_image_grounding import (
    ImageGroundingReadModel,
    ImageGroundingStatus,
)

DISCOVERY_IMAGE_GROUNDING_PROJECTION_SCHEMA = "discovery-image-grounding-projection-v1"

_DISCOVERY_ID_PATTERN = r"^[a-z0-9]+(?:-[a-z0-9]+)*$"
_STRICT_RELEASE_VERSION_PATTERN = (
    r"^(0|[1-9][0-9]{0,9})\.(0|[1-9][0-9]{0,9})\.(0|[1-9][0-9]{0,9})$"
)
_IMAGE_REFERENCE_PATTERN = (
    r"^([a-z0-9._-]+(?::[0-9]+)?/)?[a-z0-9._-]+(?:/[a-z0-9._-]+)*"
    r"(?::[a-z0-9._-]+)?$"
)
_DIGEST_PATTERN = r"^sha256:[0-9a-f]{64}$"
_PINNED_IMAGE_PATTERN = re.compile(
    rf"(?P<reference>{_IMAGE_REFERENCE_PATTERN[1:-1]})@(?P<digest>{_DIGEST_PATTERN[1:-1]})"
)


class _PublicProjectionModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)


class PublicDeploymentBinding(_PublicProjectionModel):
    compose_file: str = Field(min_length=1, max_length=512)
    compose_service: str = Field(
        min_length=1,
        max_length=255,
        pattern=r"^[a-z0-9][a-z0-9_.-]*$",
    )
    mutable_property: Literal["image"] = "image"
    deployment_method: Literal["docker-compose"] = "docker-compose"

    @field_validator("compose_file")
    @classmethod
    def require_reviewed_relative_path(cls, value: str) -> str:
        segments = value.split("/")
        if (
            value != value.strip()
            or "\\" in value
            or value.startswith(("/", "~"))
            or re.match(r"^[A-Za-z]:[\\/]", value)
            or any(segment in ("", ".", "..") for segment in segments)
            or len(segments) > 32
            or not segments[-1].endswith((".yaml", ".yml"))
        ):
            raise ValueError("compose_file must be a reviewed relative YAML path")
        return value


class PublicObservedImageIdentity(_PublicProjectionModel):
    image_reference: str = Field(
        min_length=3,
        max_length=512,
        pattern=_IMAGE_REFERENCE_PATTERN,
    )
    image_digest: str = Field(
        min_length=71,
        max_length=71,
        pattern=_DIGEST_PATTERN,
    )


class PublicImageReleaseEvidence(_PublicProjectionModel):
    release_version: str = Field(
        min_length=1,
        max_length=64,
        pattern=_STRICT_RELEASE_VERSION_PATTERN,
    )
    image_reference: str = Field(
        min_length=3,
        max_length=512,
        pattern=_IMAGE_REFERENCE_PATTERN,
    )
    image_digest: str = Field(
        min_length=71,
        max_length=71,
        pattern=_DIGEST_PATTERN,
    )
    source_class: ImageReleaseEvidenceSourceClass
    source_id: str = Field(min_length=1, max_length=256)
    attested_at: datetime

    @field_validator("attested_at")
    @classmethod
    def require_utc(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("attested_at must be timezone-aware UTC")
        if value.utcoffset().total_seconds() != 0:
            raise ValueError("attested_at must be UTC")
        return value.astimezone(UTC)


class DiscoveryImageGroundingProjection(_PublicProjectionModel):
    schema_version: Literal["discovery-image-grounding-projection-v1"] = (
        DISCOVERY_IMAGE_GROUNDING_PROJECTION_SCHEMA
    )
    catalog_item_id: str = Field(
        min_length=1,
        max_length=64,
        pattern=_DISCOVERY_ID_PATTERN,
    )
    status: ImageGroundingStatus
    release_version: str | None = Field(
        default=None,
        min_length=1,
        max_length=64,
        pattern=_STRICT_RELEASE_VERSION_PATTERN,
    )
    deployment_binding: PublicDeploymentBinding | None = None
    observed_image: PublicObservedImageIdentity | None = None
    accepted_evidence: tuple[PublicImageReleaseEvidence, ...] = Field(
        default=(),
        max_length=100,
    )


def project_image_grounding(
    read_model: ImageGroundingReadModel,
) -> DiscoveryImageGroundingProjection:
    """Redact and independently validate one P1 result for public output."""

    observation = read_model.repository_observation
    binding = None
    observed_image = None
    if observation is not None:
        # P1 can create this observation only from a validated catalog binding.
        binding = PublicDeploymentBinding(
            compose_file=observation.compose_file,
            compose_service=observation.compose_service,
        )
        match = _PINNED_IMAGE_PATTERN.fullmatch(observation.image)
        if match is not None:
            observed_image = PublicObservedImageIdentity(
                image_reference=match.group("reference"),
                image_digest=match.group("digest"),
            )

    evidence = tuple(
        PublicImageReleaseEvidence(
            release_version=row.release_version,
            image_reference=row.image_reference,
            image_digest=row.image_digest,
            source_class=row.source_class,
            source_id=row.source_id,
            attested_at=row.attested_at,
        )
        for row in read_model.image_release_evidence
    )
    grounding = read_model.grounding
    release_version = grounding.release_version
    if (
        release_version is not None
        and re.fullmatch(
            _STRICT_RELEASE_VERSION_PATTERN,
            release_version,
        )
        is None
    ):
        release_version = None
    return DiscoveryImageGroundingProjection(
        catalog_item_id=grounding.catalog_item_id,
        status=grounding.status,
        release_version=release_version,
        deployment_binding=binding,
        observed_image=observed_image,
        accepted_evidence=evidence,
    )
