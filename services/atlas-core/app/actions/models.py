from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class ProviderActionRequest(BaseModel):
    """Input supplied when executing a provider action."""

    confirmed: bool = False
    parameters: dict[str, Any] = Field(default_factory=dict)


class ProviderActionResult(BaseModel):
    """Standard result returned by every provider action."""

    provider_id: str
    action_id: str
    status: Literal["succeeded", "failed"]
    success: bool
    message: str
    data: dict[str, Any] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)


class ProviderActionAuditEntry(BaseModel):
    """Sanitized record of a provider action execution."""

    id: str
    provider_id: str
    provider_name: str
    action_id: str
    action_label: str
    status: Literal["succeeded", "failed"]
    success: bool
    message: str
    confirmed: bool
    destructive: bool
    parameter_names: list[str] = Field(default_factory=list)
    request_id: str | None = None
    started_at: datetime
    completed_at: datetime
    duration_ms: float = Field(ge=0)


class ProviderActionHistorySummary(BaseModel):
    entry_count: int = Field(ge=0)
    max_entries: int = Field(ge=1)
    retention_days: int = Field(ge=1)
    oldest_entry_at: datetime | None = None
    newest_entry_at: datetime | None = None


class ProviderActionHistoryProvider(BaseModel):
    id: str
    name: str


class ProviderActionPruneRequest(BaseModel):
    confirmed: bool = False


class ProviderActionPruneResult(BaseModel):
    deleted_entries: int = Field(ge=0)
    remaining_entries: int = Field(ge=0)
    cutoff: datetime
