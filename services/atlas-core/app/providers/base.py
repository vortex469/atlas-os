from abc import ABC, abstractmethod
from typing import Any

from app.actions.models import ProviderActionResult
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

        return [
            ProviderAction(
                id="run-diagnostics",
                label="Run Diagnostics",
                description=(
                    "Collect provider metadata, capabilities, and "
                    "current health information."
                ),
                icon="stethoscope",
                requires_confirmation=False,
                destructive=False,
                enabled=True,
            ),
        ]

    async def execute_action(
        self,
        action_id: str,
        parameters: dict[str, Any],
    ) -> ProviderActionResult:
        """Execute a provider action.

        Providers may override this method to implement additional actions.
        """

        if action_id == "run-diagnostics":
            health = await self.get_health()

            return ProviderActionResult(
                provider_id=self.metadata.id,
                action_id=action_id,
                status="succeeded",
                success=True,
                message=(
                    f"Diagnostics completed for "
                    f"{self.metadata.name}."
                ),
                data={
                    "provider": {
                        "id": self.metadata.id,
                        "name": self.metadata.name,
                        "version": self.metadata.version,
                        "workspace": self.metadata.workspace.value,
                        "priority": self.metadata.priority.value,
                        "capabilities": sorted(
                            capability.value
                            for capability
                            in self.metadata.capabilities
                        ),
                    },
                    "health": health.model_dump(),
                    "parameters": parameters,
                },
            )

        raise NotImplementedError(
            f"Provider '{self.metadata.id}' cannot execute "
            f"action '{action_id}'."
        )
