from __future__ import annotations

from typing import Protocol, runtime_checkable

from app.context import AtlasContext
from app.providers.base import Provider


@runtime_checkable
class ContextAwareProvider(Protocol):
    """Optional protocol for providers backed by immutable AtlasContext."""

    @property
    def atlas_context(self) -> AtlasContext:
        """Return the immutable AtlasContext used to construct the provider."""


@runtime_checkable
class ProviderFactory(Protocol):
    """Build a provider from an immutable AtlasContext."""

    provider_type: str

    def build(self, atlas_context: AtlasContext) -> Provider:
        """Return a provider initialized from AtlasContext."""
