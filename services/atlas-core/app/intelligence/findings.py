from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class Severity(StrEnum):
    CRITICAL = "critical"
    WARNING = "warning"
    INFO = "info"


class Finding(BaseModel):
    id: str
    severity: Severity
    category: str
    source: str
    title: str
    message: str
    recommendation: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)
    affects_health: bool = True
    score_penalty: int = Field(default=0, ge=0, le=100)
