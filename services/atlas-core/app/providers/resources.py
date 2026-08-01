from __future__ import annotations

from typing import Protocol, runtime_checkable

from app.models.resources import (
    ProviderExpectationOption,
    ProviderResourceCollection,
    UpdateResourceExpectationResult,
)


@runtime_checkable
class ProviderExpectationAdapter(Protocol):
    """Optional provider contract for expectation vocabulary metadata."""

    def expectation_options(
        self,
        resource_type: str,
    ) -> list[ProviderExpectationOption]:
        """Return provider-defined expectation choices for a resource type."""

    def normalize_expectation(
        self,
        resource_type: str,
        expectation: str,
    ) -> str:
        """Normalize or reject a provider-specific expectation value."""

    def expectation_label(
        self,
        resource_type: str,
        expectation: str | None,
    ) -> str:
        """Return a display label for a provider-specific expectation."""


@runtime_checkable
class ProviderResourceAdapter(ProviderExpectationAdapter, Protocol):
    """Optional provider contract for generic resource management."""

    async def list_resources(self) -> ProviderResourceCollection:
        """Return the provider's current discovered resources."""

    async def refresh_resources(self) -> ProviderResourceCollection:
        """Refresh discovery and return the latest resources."""

    async def update_resource_expectation(
        self,
        resource_id: str,
        expectation: str,
    ) -> UpdateResourceExpectationResult:
        """Persist user intent for one provider resource."""
