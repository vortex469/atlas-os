"""Binding-driven, local-only image-grounding read model.

This service composes existing reviewed Discovery readers and the existing
image-grounding evaluator.  It performs no acquisition, verification,
persistence, mutation, execution, network access, subprocess execution, or
clock reads.
"""

from __future__ import annotations

from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from app.discovery.image_grounding import ImageGroundingResult, ground_deployment_image
from app.discovery.image_release_evidence_loader import ImageReleaseEvidenceLoader
from app.discovery.loader import YamlCatalogLoader
from app.discovery.models import (
    CatalogProvenance,
    ImageReleaseEvidence,
    RepositoryComposeImageObservation,
)
from app.discovery.repository_compose_observation import (
    RepositoryComposeImageObservationAcquirer,
)


class ImageGroundingReadFailure(StrEnum):
    """Bounded P1-local failures that existing grounding statuses cannot express."""

    CATALOG_ITEM_NOT_FOUND = "catalog_item_not_found"


class ImageGroundingReadError(RuntimeError):
    """A requested catalog item cannot be represented by the read model."""

    def __init__(
        self,
        failure: ImageGroundingReadFailure,
        catalog_item_id: str,
    ) -> None:
        self.failure = failure
        self.catalog_item_id = catalog_item_id
        super().__init__(f"{failure.value}: {catalog_item_id}")


class ImageGroundingReadModel(BaseModel):
    """Immutable local inputs and their existing grounding result."""

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    grounding: ImageGroundingResult
    catalog_provenance: CatalogProvenance
    repository_observation: RepositoryComposeImageObservation | None = None
    image_release_evidence: tuple[ImageReleaseEvidence, ...] = ()


class BindingDrivenImageGroundingService:
    """Evaluate one existing catalog item from reviewed local inputs only.

    Construction is inert. :meth:`get` loads the complete accepted evidence
    set and curated catalog, selects one existing item by exact identifier,
    observes only that item's existing binding, and delegates the decision to
    :func:`ground_deployment_image`.
    """

    def __init__(self, repository_root: Path) -> None:
        self._repository_root = Path(repository_root)

    def get(self, catalog_item_id: str) -> ImageGroundingReadModel:
        """Return the deterministic grounding read model for one catalog item."""

        # Validate the complete evidence and catalog inputs before selecting a
        # row. Reader failures propagate fail closed; partial input is never
        # evaluated.
        evidence = ImageReleaseEvidenceLoader().load().rows
        catalog = YamlCatalogLoader().load()
        entry = next(
            (
                candidate
                for candidate in catalog.entries
                if candidate.item.id == catalog_item_id
            ),
            None,
        )
        if entry is None:
            raise ImageGroundingReadError(
                ImageGroundingReadFailure.CATALOG_ITEM_NOT_FOUND,
                catalog_item_id,
            )

        release_version = (
            entry.release_claim.version if entry.release_claim is not None else None
        )
        binding = entry.deployment_binding
        observation = None
        if binding is not None and release_version is not None:
            observation = RepositoryComposeImageObservationAcquirer(
                self._repository_root
            ).observe(binding)

        item_evidence = tuple(
            sorted(
                (row for row in evidence if row.catalog_item_id == catalog_item_id),
                key=lambda row: (
                    row.release_version,
                    row.image_reference,
                    row.image_digest,
                    row.source_class.value,
                    row.source_id,
                    row.attested_at,
                ),
            )
        )
        grounding = ground_deployment_image(
            catalog_item_id=catalog_item_id,
            deployment_binding=binding,
            release_version=release_version,
            repository_observation=observation,
            image_release_evidence=item_evidence,
        )
        return ImageGroundingReadModel(
            grounding=grounding,
            catalog_provenance=entry.provenance,
            repository_observation=observation,
            image_release_evidence=item_evidence,
        )
