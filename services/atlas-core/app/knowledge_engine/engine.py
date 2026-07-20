from __future__ import annotations

from app.deploy.plan import DeploymentPlan
from app.knowledge_engine.loader import (
    KnowledgeCatalogLoader,
)
from app.knowledge_engine.matcher import (
    ApplicationMatch,
    ApplicationMatcher,
)


class KnowledgeEngine:
    """Coordinate knowledge catalog loading and application matching."""

    def __init__(
        self,
        *,
        loader: KnowledgeCatalogLoader,
        matcher: ApplicationMatcher,
    ) -> None:
        self._loader = loader
        self._matcher = matcher

    def recognize(
        self,
        plan: DeploymentPlan,
    ) -> ApplicationMatch | None:
        """Return the strongest known application match."""

        applications = self._loader.load_applications()

        return self._matcher.match(
            plan,
            applications,
        )
