from __future__ import annotations

from app.deploy.plan import DeploymentPlan
from app.knowledge_engine.assessment import (
    KnowledgeAssessment,
)
from app.knowledge_engine.assessors.registry import (
    AssessorRegistry,
)
from app.knowledge_engine.loader import (
    KnowledgeCatalogLoader,
)
from app.knowledge_engine.matcher import (
    ApplicationMatch,
    ApplicationMatcher,
)


class KnowledgeEngine:
    """Coordinate catalog matching and operational assessment."""

    def __init__(
        self,
        *,
        loader: KnowledgeCatalogLoader,
        matcher: ApplicationMatcher,
        registry: AssessorRegistry,
    ) -> None:
        self._loader = loader
        self._matcher = matcher
        self._registry = registry

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

    def assess(
        self,
        plan: DeploymentPlan,
    ) -> KnowledgeAssessment:
        """Create an operational assessment for a deployment."""

        match = self.recognize(plan)

        assessment = KnowledgeAssessment(
            recognition=match,
        )

        if match is None:
            return assessment

        assessor = self._registry.get(
            match.application.id
        )

        if assessor is not None:
            assessor.assess(
                plan,
                assessment,
            )

        return assessment