"""Data models for model providers."""

from dataclasses import dataclass


@dataclass(frozen=True)
class ModelResponse:
    """Normalized response returned by a model provider."""

    text: str
    model: str
    provider_id: str
