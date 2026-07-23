from __future__ import annotations

from pydantic import BaseModel, Field

from app.deploy.plan import DeploymentPlan
from app.knowledge_engine.models import (
    ApplicationDefinition,
)


class ApplicationMatch(BaseModel):
    """A scored application match."""

    application: ApplicationDefinition
    confidence: int = Field(
        ge=0,
        le=100,
    )
    matched_component_ids: list[str] = Field(
        default_factory=list
    )


class ApplicationMatcher:
    """Match deployment components against catalog definitions."""

    def match(
        self,
        plan: DeploymentPlan,
        applications: list[ApplicationDefinition],
    ) -> ApplicationMatch | None:
        best_match: ApplicationMatch | None = None

        for application in applications:
            candidate = self._score_application(
                plan,
                application,
            )

            if candidate is None:
                continue

            if (
                best_match is None
                or candidate.confidence > best_match.confidence
            ):
                best_match = candidate

        return best_match

    def _score_application(
        self,
        plan: DeploymentPlan,
        application: ApplicationDefinition,
    ) -> ApplicationMatch | None:
        known_images = {
            self._normalize_image(image)
            for image in application.images
        }

        known_service_names = {
            self._normalize_name(name)
            for name in application.service_names
        }

        matched_component_ids: list[str] = []
        image_matches = 0
        service_matches = 0

        for component in plan.components:
            normalized_image = self._normalize_image(
                component.image
            )
            normalized_name = self._normalize_name(
                component.name
            )

            matched = False

            if (
                normalized_image
                and normalized_image in known_images
            ):
                image_matches += 1
                matched = True

            if normalized_name in known_service_names:
                service_matches += 1
                matched = True

            if matched:
                matched_component_ids.append(
                    component.id
                )

        if image_matches == 0 and service_matches == 0:
            return None

        confidence = min(
            100,
            image_matches * 100
            + service_matches * 25,
        )

        return ApplicationMatch(
            application=application,
            confidence=confidence,
            matched_component_ids=matched_component_ids,
        )

    def _normalize_image(
        self,
        image: str | None,
    ) -> str:
        if image is None:
            return ""

        normalized = image.strip().lower()

        if "@" in normalized:
            normalized = normalized.split("@", 1)[0]

        image_name = normalized.rsplit("/", 1)[-1]

        if ":" in image_name:
            normalized = normalized.rsplit(":", 1)[0]

        return normalized

    def _normalize_name(
        self,
        name: str,
    ) -> str:
        return (
            name.strip()
            .lower()
            .replace("_", "-")
            .replace(" ", "-")
        )