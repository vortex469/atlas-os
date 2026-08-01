from __future__ import annotations

from typing import Protocol, runtime_checkable

from app.models.connections import (
    ProviderConnectionSchema,
    TestProviderConnectionRequest,
    TestProviderConnectionResult,
    UpdateProviderConnectionRequest,
    UpdateProviderConnectionResult,
)


@runtime_checkable
class ProviderConnectionAdapter(Protocol):
    """Optional provider contract for generic connection management."""

    def connection_schema(self) -> ProviderConnectionSchema:
        """Return a sanitized public connection schema for this provider."""

    async def test_connection(
        self,
        request: TestProviderConnectionRequest,
    ) -> TestProviderConnectionResult:
        """Validate provider connection settings without persisting them."""

    async def update_connection(
        self,
        request: UpdateProviderConnectionRequest,
    ) -> UpdateProviderConnectionResult:
        """Persist provider connection settings after explicit user approval."""
