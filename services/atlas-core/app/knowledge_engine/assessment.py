from __future__ import annotations

from pydantic import BaseModel, Field

from app.knowledge_engine.matcher import ApplicationMatch


class KnowledgeFinding(BaseModel):
    """A single operational finding."""

    severity: str
    title: str
    description: str


class KnowledgeAssessment(BaseModel):
    """Operational assessment for a deployment."""

    recognition: ApplicationMatch | None = None

    findings: list[KnowledgeFinding] = Field(
        default_factory=list
    )

    recommendations: list[str] = Field(
        default_factory=list
    )

    best_practices: list[str] = Field(
        default_factory=list
    )