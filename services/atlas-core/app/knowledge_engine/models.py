from __future__ import annotations

from pydantic import BaseModel, Field


class ResourceRecommendation(BaseModel):
    """Recommended resources for an application."""

    cpu_cores: int | None = Field(
        default=None,
        ge=1,
    )
    ram_mb: int | None = Field(
        default=None,
        ge=1,
    )


class ApplicationDefinition(BaseModel):
    """Knowledge catalog definition for a known application."""

    id: str
    name: str
    category: str
    description: str

    images: list[str] = Field(default_factory=list)
    service_names: list[str] = Field(default_factory=list)
    required_services: list[str] = Field(default_factory=list)
    optional_services: list[str] = Field(default_factory=list)

    documentation: str | None = None

    resources: ResourceRecommendation = Field(
        default_factory=ResourceRecommendation
    )