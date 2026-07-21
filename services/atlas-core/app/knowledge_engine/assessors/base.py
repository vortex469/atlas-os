from __future__ import annotations

from abc import ABC, abstractmethod

from app.deploy.plan import DeploymentPlan
from app.knowledge_engine.assessment import (
    KnowledgeAssessment,
)


class ApplicationAssessor(ABC):
    """Base class for application-specific assessors."""

    @abstractmethod
    def assess(
        self,
        plan: DeploymentPlan,
        assessment: KnowledgeAssessment,
    ) -> None:
        """Update the assessment in-place."""