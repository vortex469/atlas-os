from __future__ import annotations

from app.deploy.plan import ApplicationComponent
from app.knowledge_engine.assessment import (
    KnowledgeAssessment,
    KnowledgeFinding,
)

from .base import AssessmentRule


class StorageRule(AssessmentRule):
    """Checks that persistent storage is configured."""

    def __init__(
        self,
        *,
        application_name: str,
        target_path: str,
        recommendation: str,
    ) -> None:
        self._application_name = application_name
        self._target_path = target_path
        self._recommendation = recommendation

    def assess(
        self,
        component: ApplicationComponent,
        assessment: KnowledgeAssessment,
    ) -> None:
        for mount in component.storage:
            if (
                mount.target == self._target_path
                and mount.persistent
            ):
                return

        assessment.findings.append(
            KnowledgeFinding(
                severity="warning",
                title="Persistent storage missing",
                description=(
                    f"{self._application_name} data is not mounted "
                    f"to persistent storage at {self._target_path}."
                ),
            )
        )

        assessment.recommendations.append(
            self._recommendation
        )