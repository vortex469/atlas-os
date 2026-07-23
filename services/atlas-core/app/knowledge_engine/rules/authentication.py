from __future__ import annotations

from app.deploy.plan import ApplicationComponent
from app.knowledge_engine.assessment import (
    KnowledgeAssessment,
    KnowledgeFinding,
)

from .base import AssessmentRule


class AuthenticationRule(AssessmentRule):
    """Checks that required authentication variables are configured."""

    def __init__(
        self,
        *,
        application_name: str,
        required_variables: list[str],
    ) -> None:
        self._application_name = application_name
        self._required_variables = required_variables

    def assess(
        self,
        component: ApplicationComponent,
        assessment: KnowledgeAssessment,
    ) -> None:
        for variable in self._required_variables:
            if variable not in component.environment:
                assessment.findings.append(
                    KnowledgeFinding(
                        severity="warning",
                        title=f"{variable} missing",
                        description=(
                            f"{self._application_name} should be "
                            f"configured with {variable}."
                        ),
                    )
                )

                assessment.recommendations.append(
                    f"Configure {variable}."
                )