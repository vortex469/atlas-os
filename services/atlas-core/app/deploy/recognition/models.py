from __future__ import annotations

from pydantic import BaseModel, Field


class ApplicationRecognition(BaseModel):
    """An application identified from a deployment plan."""

    application_id: str
    name: str
    category: str
    confidence: int = Field(
        ge=0,
        le=100,
    )
    description: str
    matched_component_ids: list[str] = []