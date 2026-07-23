from __future__ import annotations

from abc import ABC, abstractmethod

from app.deploy.components import ApplicationComponent
from app.knowledge_engine.assessment import KnowledgeAssessment


class AssessmentRule(ABC):
    """Base class for reusable assessment rules."""

    @abstractmethod
    def assess(
        self,
        component: ApplicationComponent,
        assessment: KnowledgeAssessment,
    ) -> None:
        """Evaluate a component and update the assessment."""
        raise NotImplementedError