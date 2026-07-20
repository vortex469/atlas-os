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
