from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.providers.capabilities import (
    ProviderCapability,
    ProviderPriority,
    ProviderWorkspace,
)


class ProviderMetadata(BaseModel):
    """Stable metadata describing an Atlas provider."""

    model_config = ConfigDict(frozen=True)

    id: str = Field(
        min_length=1,
        pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$",
        description="Stable URL-safe provider identifier.",
    )
    name: str = Field(min_length=1)
    version: str = Field(default="1.0.0", min_length=1)
    description: str = ""
    workspace: ProviderWorkspace
    icon: str = "box"
    priority: ProviderPriority = ProviderPriority.NORMAL
    capabilities: frozenset[ProviderCapability] = Field(
        default_factory=lambda: frozenset(
            {ProviderCapability.HEALTH},
        ),
    )


class ProviderHealth(BaseModel):
    """Current operational state returned by a provider."""

    status: str
    latency_ms: int | float | None = None
    http_status: int | None = None
    message: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)


class ProviderAction(BaseModel):
    """An action advertised by a provider."""

    id: str = Field(
        min_length=1,
        pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$",
    )
    label: str = Field(min_length=1)
    description: str = ""
    icon: str = "play"
    requires_confirmation: bool = False
    destructive: bool = False
    enabled: bool = True
    parameters: dict[str, Any] = Field(default_factory=dict)


class ProviderSnapshot(BaseModel):
    """Frontend-friendly representation of a registered provider."""

    metadata: ProviderMetadata
    health: ProviderHealth
    actions: list[ProviderAction] = Field(default_factory=list)
