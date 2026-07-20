from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class ApplicationCategory(str, Enum):
    PRODUCTIVITY = "productivity"
    MEDIA = "media"
    AI = "ai"
    DATABASE = "database"
    NETWORKING = "networking"
    AUTOMATION = "automation"
    MONITORING = "monitoring"
    OTHER = "other"


class ApplicationCapability(BaseModel):
    id: str
    name: str
    description: str = ""


class ApplicationRequirement(BaseModel):
    id: str
    description: str
    required: bool = True


class Application(BaseModel):
    id: str = Field(
        pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$"
    )

    name: str

    description: str = ""

    version: str | None = None

    category: ApplicationCategory = (
        ApplicationCategory.OTHER
    )

    homepage: str | None = None

    documentation: str | None = None

    capabilities: list[
        ApplicationCapability
    ] = Field(default_factory=list)

    requirements: list[
        ApplicationRequirement
    ] = Field(default_factory=list)