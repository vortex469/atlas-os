from __future__ import annotations

from collections.abc import Iterator

from app.deploy.plan import (
    ApplicationComponent,
    DeploymentPlan,
)
from app.knowledge_engine.utils import (
    normalize_image,
)


class ApplicationAssessor:
    """Base class for application assessors."""

    @staticmethod
    def iter_matching_components(
        plan: DeploymentPlan,
        images: set[str],
    ) -> Iterator[ApplicationComponent]:
        for component in plan.components:
            if component.image is None:
                continue

            if normalize_image(component.image) in images:
                yield component