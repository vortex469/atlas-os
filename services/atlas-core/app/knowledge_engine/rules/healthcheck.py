from __future__ import annotations

from app.deploy.components import ApplicationComponent
from app.knowledge_engine.assessment import (
    KnowledgeAssessment,
    KnowledgeFinding,
)
from app.knowledge_engine.rules.base import AssessmentRule


class HealthCheckRule(AssessmentRule):
    """Checks whether a component has an enabled health check."""

    def __init__(
        self,
        *,
        application_name: str,
        recommendation: str,
    ) -> None:
        self._application_name = application_name
        self._recommendation = recommendation

    def assess(
        self,
        component: ApplicationComponent,
        assessment: KnowledgeAssessment,
    ) -> None:
        if (
            component.healthcheck is not None
            and not component.healthcheck.disabled
            and component.healthcheck.test
        ):
            return

        assessment.findings.append(
            KnowledgeFinding(
                severity="warning",
                title="Health check missing",
                description=(
                    f"{self._application_name} does not have "
                    "an active container health check."
                ),
            )
        )

        assessment.recommendations.append(
            self._recommendation
        )