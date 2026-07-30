"""Context models for Atlas Agent."""
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ServiceHealth(BaseModel):
    """Health information for a single service."""

    model_config = ConfigDict(frozen=True)

    provider_id: str
    status: str
    latency_ms: float | None = None
    http_status: int | None = None
    message: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)

class AgentContext(BaseModel):
    """Complete context for the Atlas Agent."""

    model_config = ConfigDict(frozen=True)

    atlas: str
    assistant: str
    engine: str
    release: str
    services: dict[str, ServiceHealth]
