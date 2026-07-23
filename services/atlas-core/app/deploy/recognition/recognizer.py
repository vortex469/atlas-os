from __future__ import annotations

from app.deploy.plan import DeploymentPlan
from app.deploy.recognition.models import (
    ApplicationRecognition,
)
from app.knowledge_engine import KnowledgeEngine


class ApplicationRecognizer:
    """Compatibility adapter around the Knowledge Engine."""

    def __init__(
        self,
        *,
        knowledge_engine: KnowledgeEngine,
    ) -> None:
        self._knowledge_engine = knowledge_engine

    def recognize(
        self,
        plan: DeploymentPlan,
    ) -> ApplicationRecognition:
        match = self._knowledge_engine.recognize(plan)

        if match is None:
            return ApplicationRecognition(
                application_id="unknown",
                name="Unknown Application",
                category="Unknown",
                confidence=0,
                description=(
                    "Atlas could not identify a known application "
                    "from the deployment components."
                ),
                matched_component_ids=[],
            )

        return ApplicationRecognition(
            application_id=match.application.id,
            name=match.application.name,
            category=match.application.category,
            confidence=match.confidence,
            description=match.application.description,
            matched_component_ids=match.matched_component_ids,
        )