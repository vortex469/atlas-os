"""Read-only composition for grounding the reviewed Home Assistant image."""

from __future__ import annotations

from pathlib import Path

from app.discovery.image_grounding import ImageGroundingResult, ground_deployment_image
from app.discovery.image_release_evidence_loader import ImageReleaseEvidenceLoader
from app.discovery.loader import YamlCatalogLoader
from app.discovery.repository_compose_observation import (
    RepositoryComposeImageObservationAcquirer,
)

_CATALOG_ITEM_ID = "home-assistant"


class HomeAssistantCatalogEntryNotFoundError(RuntimeError):
    """The reviewed Home Assistant catalog entry is unavailable."""


class HomeAssistantImageGroundingService:
    """Compose reviewed local inputs for Home Assistant image grounding.

    Construction is inert. Calling :meth:`ground` performs only bounded local
    reads through the existing catalog, evidence, and Compose observers.
    """

    def __init__(self, repository_root: Path) -> None:
        self._repository_root = Path(repository_root)

    def ground(self) -> ImageGroundingResult:
        """Return the existing grounding result for Home Assistant."""

        # Load and validate the complete evidence directory before selecting
        # any catalog entry or attempting a repository observation.
        evidence = ImageReleaseEvidenceLoader().load().rows
        catalog = YamlCatalogLoader().load()
        entry = next(
            (
                candidate
                for candidate in catalog.entries
                if candidate.item.id == _CATALOG_ITEM_ID
            ),
            None,
        )
        if entry is None:
            raise HomeAssistantCatalogEntryNotFoundError(
                "The Home Assistant catalog entry is unavailable."
            )

        release_version = (
            entry.release_claim.version if entry.release_claim is not None else None
        )
        binding = entry.deployment_binding
        if binding is None or release_version is None:
            return ground_deployment_image(
                catalog_item_id=_CATALOG_ITEM_ID,
                deployment_binding=binding,
                release_version=release_version,
                repository_observation=None,
                image_release_evidence=evidence,
            )

        observation = RepositoryComposeImageObservationAcquirer(
            self._repository_root
        ).observe(binding)
        return ground_deployment_image(
            catalog_item_id=_CATALOG_ITEM_ID,
            deployment_binding=binding,
            release_version=release_version,
            repository_observation=observation,
            image_release_evidence=evidence,
        )
