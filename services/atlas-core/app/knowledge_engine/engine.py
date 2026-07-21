from __future__ import annotations

from app.deploy.plan import DeploymentPlan
from app.knowledge_engine.loader import (
    KnowledgeCatalogLoader,
)
from app.knowledge_engine.matcher import (
    ApplicationMatch,
    ApplicationMatcher,
)
from app.knowledge_engine.assessment import (
    KnowledgeAssessment,
)
from app.knowledge_engine.assessors.postgres import (
    PostgresAssessor,
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

        if match.application.id == "postgres":
            PostgresAssessor().assess(
                plan,
                assessment,
            )

        return assessment