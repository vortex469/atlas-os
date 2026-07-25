from typing import Literal

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


class ProviderCollectionTiming(BaseModel):
    provider_id: str
    provider_name: str
    status: Literal["completed", "timed_out", "failed"]
    duration_ms: float = Field(ge=0)
    finding_count: int = Field(ge=0)


class IntelligenceTelemetry(BaseModel):
    provider_collection_duration_ms: float = Field(
        default=0,
        ge=0,
    )
    provider_timeout_seconds: float = Field(default=0, ge=0)
    providers: list[ProviderCollectionTiming] = Field(
        default_factory=list
    )


class SituationReport(BaseModel):
    score: int
    status: str
    summary: str

    findings: list[Finding] = Field(default_factory=list)
    assessments: list[Assessment] = Field(default_factory=list)
    recommendations: list[Recommendation] = Field(default_factory=list)
    telemetry: IntelligenceTelemetry = Field(
        default_factory=IntelligenceTelemetry
    )
