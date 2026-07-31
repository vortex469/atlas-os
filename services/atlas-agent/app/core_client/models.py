from typing import Any

from pydantic import BaseModel, Field


class ServiceHealth(BaseModel):
    provider_id: str
    status: str
    latency_ms: float | None = None
    http_status: int | None = None
    message: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)

class AtlasCoreHealth(BaseModel):
    atlas: str
    services: dict[str, ServiceHealth]

class AtlasCoreStatus(BaseModel):
    atlas: str
    assistant: str
    engine: str
    release: str


class AtlasCoreIntelligenceFinding(BaseModel):
    id: str
    severity: str
    category: str
    source: str
    title: str
    message: str
    recommendation: str | None = None
    component: str | None = None
    affects_health: bool


class AtlasCoreIntelligenceAssessment(BaseModel):
    title: str
    priority: str
    component: str | None = None


class AtlasCoreIntelligenceRecommendation(BaseModel):
    title: str
    reason: str
    priority: str
    confidence: float
    estimated_effort: str
    component: str | None = None


class AtlasCoreIntelligenceSummary(BaseModel):
    score: int
    status: str
    summary: str
    findings: tuple[AtlasCoreIntelligenceFinding, ...] = ()
    assessments: tuple[AtlasCoreIntelligenceAssessment, ...] = ()
    recommendations: tuple[AtlasCoreIntelligenceRecommendation, ...] = ()
