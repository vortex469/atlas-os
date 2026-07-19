from pydantic import BaseModel, Field

from app.intelligence.findings import Finding


class Assessment(BaseModel):
    title: str
    priority: str
    component: str | None = None
    details: dict = Field(default_factory=dict)


class Recommendation(BaseModel):
    title: str
    reason: str
    priority: str
    confidence: float = 1.0
    estimated_effort: str = "Unknown"
    component: str | None = None


class SituationReport(BaseModel):
    score: int
    status: str
    summary: str

    findings: list[Finding] = Field(default_factory=list)
    assessments: list[Assessment] = Field(default_factory=list)
    recommendations: list[Recommendation] = Field(default_factory=list)
