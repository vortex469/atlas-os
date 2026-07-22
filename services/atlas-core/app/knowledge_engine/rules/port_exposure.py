from __future__ import annotations

from app.deploy.plan import ApplicationComponent
from app.knowledge_engine.assessment import (
    KnowledgeAssessment,
    KnowledgeFinding,
)

from .base import AssessmentRule


class PortExposureRule(AssessmentRule):
    """Checks whether a sensitive service port is publicly exposed."""

    def __init__(
        self,
        *,
        application_name: str,
        container_port: int,
        recommendation: str,
    ) -> None:
        self._application_name = application_name
        self._container_port = container_port
        self._recommendation = recommendation

    def assess(
        self,
        component: ApplicationComponent,
        assessment: KnowledgeAssessment,
    ) -> None:
        for port in component.ports:
            if (
                port.container_port == self._container_port
                and port.public
            ):
                assessment.findings.append(
                    KnowledgeFinding(
                        severity="warning",
                        title=f"{self._application_name} publicly exposed",
                        description=(
                            f"{self._application_name} port "
                            f"{self._container_port} is publicly exposed."
                        ),
                    )
                )

                assessment.recommendations.append(
                    self._recommendation
                )
                return