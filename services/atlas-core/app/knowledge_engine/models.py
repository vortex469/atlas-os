from __future__ import annotations

from pydantic import BaseModel, Field


class ResourceRecommendation(BaseModel):
    cpu_cores: int | None = Field(default=None, ge=1)
    ram_mb: int | None = Field(default=None, ge=1)


class EnvironmentVariable(BaseModel):
    required: bool = False
    description: str | None = None


class ApplicationDefinition(BaseModel):
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

    recommended_ports: list[int] = Field(
        default_factory=list
    )

    persistent_paths: list[str] = Field(
        default_factory=list
    )

    environment_variables: dict[
        str,
        EnvironmentVariable,
    ] = Field(default_factory=dict)

    notes: list[str] = Field(
        default_factory=list
    )