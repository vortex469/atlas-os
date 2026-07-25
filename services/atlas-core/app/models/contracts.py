from typing import Any

from pydantic import BaseModel, Field


class APIErrorDetail(BaseModel):
    code: str
    message: str
    status: int
    details: Any = Field(default_factory=dict)


class APIError(BaseModel):
    error: APIErrorDetail
    request_id: str


class ServiceHealth(BaseModel):
    provider_id: str
    status: str
    latency_ms: float | None = None
    http_status: int | None = None
    message: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)


class AtlasHealth(BaseModel):
    atlas: str
    services: dict[str, ServiceHealth]


class ProviderHealth(BaseModel):
    status: str
    latency_ms: float | None = None
    http_status: int | None = None
    message: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)


class ProviderResponse(BaseModel):
    id: str
    name: str
    workspace: str
    priority: str
    version: str
    description: str
    icon: str
    capabilities: list[str] = Field(default_factory=list)
    health: ProviderHealth


class AceFinding(BaseModel):
    id: str
    severity: str
    category: str
    source: str
    title: str
    message: str
    recommendation: str | None = None
    component: str | None = None
    metric: dict[str, Any] = Field(default_factory=dict)
    details: dict[str, Any] = Field(default_factory=dict)
    affects_health: bool
    score_penalty: int


class AceAssessment(BaseModel):
    title: str
    priority: str
    component: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)


class AceRecommendation(BaseModel):
    title: str
    reason: str
    priority: str
    confidence: float
    estimated_effort: str
    component: str | None = None


class AceSummary(BaseModel):
    score: int
    status: str
    summary: str
    findings: list[AceFinding] = Field(default_factory=list)
    assessments: list[AceAssessment] = Field(default_factory=list)
    recommendations: list[AceRecommendation] = Field(default_factory=list)
