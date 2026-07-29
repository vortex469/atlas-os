"""Interface for model providers."""

from typing import Protocol


class ModelProvider(Protocol):
    """Interface for model providers."""

    @property
    def provider_id(self) -> str:
        """Unique identifier for this provider."""

    def health_check(self) -> bool:
        """Check if the model provider is healthy and reachable."""
