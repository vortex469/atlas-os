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
