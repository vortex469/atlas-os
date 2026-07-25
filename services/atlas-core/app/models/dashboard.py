from pydantic import BaseModel

from app.models.health import HealthState


class AtlasSummary(BaseModel):
    release: str | None = None
    status: str | None = None
    assistant: str | None = None
    timestamp: str | None = None


class HealthSummary(BaseModel):
    score: int = 0
    state: HealthState = HealthState.UNKNOWN
    warnings: int = 0
    critical: int = 0


class AISummary(BaseModel):
    provider: str | None = None
    online: bool = False
    health: str | None = None
    latency_ms: float | None = None
    installed_models: int = 0
    running_models: int = 0


class ServiceSummary(BaseModel):
    status: HealthState


class AlertSummary(BaseModel):
    severity: str
    title: str


class Dashboard(BaseModel):
    atlas: AtlasSummary
    health: HealthSummary
    ai: AISummary
    services: dict[str, ServiceSummary]
    alerts: list[AlertSummary]
