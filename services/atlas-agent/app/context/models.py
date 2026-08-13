"""Context models for Atlas Agent."""
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

INTELLIGENCE_FAILURE_MESSAGES = {
    "connection_error": "Atlas intelligence connection failed.",
    "timeout": "Atlas intelligence request timed out.",
    "response_error": (
        "Atlas intelligence returned an unsuccessful response."
    ),
    "payload_error": "Atlas intelligence returned an invalid payload.",
}

ACTION_HISTORY_FAILURE_MESSAGES = {
    "connection_error": "Atlas action history connection failed.",
    "timeout": "Atlas action history request timed out.",
    "response_error": (
        "Atlas action history returned an unsuccessful response."
    ),
    "payload_error": "Atlas action history returned an invalid payload.",
}


class ServiceHealth(BaseModel):
    """Health information for a single service."""

    model_config = ConfigDict(frozen=True)

    provider_id: str
    status: str
    latency_ms: float | None = None
    http_status: int | None = None
    message: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)


class IntelligenceFinding(BaseModel):
    """One normalized Atlas intelligence finding."""

    model_config = ConfigDict(frozen=True)

    identifier: str
    severity: str
    category: str
    source: str
    title: str
    message: str
    recommendation: str | None = None
    component: str | None = None
    affects_health: bool


class IntelligenceAssessment(BaseModel):
    """One normalized Atlas intelligence assessment."""

    model_config = ConfigDict(frozen=True)

    title: str
    priority: str
    component: str | None = None


class IntelligenceRecommendation(BaseModel):
    """One normalized Atlas intelligence recommendation."""

    model_config = ConfigDict(frozen=True)

    title: str
    reason: str
    priority: str
    confidence: float
    estimated_effort: str
    component: str | None = None


class IntelligenceFailure(BaseModel):
    """Stable representation of unavailable intelligence enrichment."""

    model_config = ConfigDict(frozen=True)

    code: Literal[
        "connection_error",
        "timeout",
        "response_error",
        "payload_error",
    ]
    message: str

    @model_validator(mode="after")
    def validate_stable_message(self) -> "IntelligenceFailure":
        if self.message != INTELLIGENCE_FAILURE_MESSAGES[self.code]:
            raise ValueError(
                "Intelligence failure message must match its code"
            )
        return self


class IntelligenceContext(BaseModel):
    """Advisory Atlas intelligence attached to an Agent context."""

    model_config = ConfigDict(frozen=True)

    findings: tuple[IntelligenceFinding, ...] = ()
    assessments: tuple[IntelligenceAssessment, ...] = ()
    recommendations: tuple[IntelligenceRecommendation, ...] = ()
    failure: IntelligenceFailure | None = None


class ActionHistoryEntry(BaseModel):
    """One sanitized provider action history entry from Atlas Core."""

    model_config = ConfigDict(frozen=True)

    identifier: str
    provider_id: str
    provider_name: str
    action_id: str
    action_label: str
    status: Literal["succeeded", "failed"]
    success: bool
    message: str
    confirmed: bool
    destructive: bool
    parameter_names: tuple[str, ...] = ()
    request_id: str | None = None
    started_at: datetime
    completed_at: datetime
    duration_ms: float


class ActionHistoryFailure(BaseModel):
    """Stable representation of unavailable action history."""

    model_config = ConfigDict(frozen=True)

    code: Literal[
        "connection_error",
        "timeout",
        "response_error",
        "payload_error",
    ]
    message: str

    @model_validator(mode="after")
    def validate_stable_message(self) -> "ActionHistoryFailure":
        if self.message != ACTION_HISTORY_FAILURE_MESSAGES[self.code]:
            raise ValueError(
                "Action history failure message must match its code"
            )
        return self


class ActionHistoryContext(BaseModel):
    """Bounded advisory Atlas provider action history context."""

    model_config = ConfigDict(frozen=True)

    entries: tuple[ActionHistoryEntry, ...] = ()
    failure: ActionHistoryFailure | None = None


class AgentContext(BaseModel):
    """Complete context for the Atlas Agent."""

    model_config = ConfigDict(frozen=True)

    atlas: str
    assistant: str
    engine: str
    release: str
    services: dict[str, ServiceHealth]
    intelligence: IntelligenceContext | None = None
    action_history: ActionHistoryContext | None = None
