from abc import ABC, abstractmethod
from typing import Any

from app.providers.models import (
    ProviderAction,
    ProviderHealth,
    ProviderMetadata,
)


class Provider(ABC):
    """Base contract implemented by all Atlas providers."""

    @property
    @abstractmethod
    def metadata(self) -> ProviderMetadata:
        """Return stable provider metadata."""

    @abstractmethod
    async def get_health(self) -> ProviderHealth:
        """Return the provider's current operational health."""

    async def get_findings(self) -> list[Any]:
        """Return provider-specific ACE findings when supported."""

        return []

    async def get_recommendations(self) -> list[Any]:
        """Return provider-specific recommendations when supported."""

        return []

    async def get_actions(self) -> list[ProviderAction]:
        """Return actions currently advertised by the provider."""

        return []
