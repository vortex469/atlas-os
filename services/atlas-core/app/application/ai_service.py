from __future__ import annotations

from app.actions import (
    ProviderActionRequest,
    ProviderActionResult,
    execute_provider_action,
)
from app.providers import ProviderRegistry, provider_registry


class AIControlService:
    """Coordinate high-level AI operations through Atlas providers."""

    def __init__(
        self,
        *,
        registry: ProviderRegistry = provider_registry,
        provider_id: str = "ollama",
    ) -> None:
        self._registry = registry
        self._provider_id = provider_id

    def _provider(self):
        """Resolve the configured AI provider."""

        return self._registry.get(self._provider_id)

    async def installed_models(self) -> ProviderActionResult:
        """Return models installed in the provider's model library."""

        return await execute_provider_action(
            provider=self._provider(),
            action_id="list-models",
            request=ProviderActionRequest(),
        )

    async def running_models(self) -> ProviderActionResult:
        """Return models currently loaded by the provider."""

        return await execute_provider_action(
            provider=self._provider(),
            action_id="runtime-status",
            request=ProviderActionRequest(),
        )

    async def load_model(
        self,
        model: str,
    ) -> ProviderActionResult:
        """Load a model into runtime memory."""

        return await execute_provider_action(
            provider=self._provider(),
            action_id="load-model",
            request=ProviderActionRequest(
                parameters={
                    "model": model,
                },
            ),
        )

    async def unload_model(
        self,
        model: str,
        *,
        confirmed: bool = False,
    ) -> ProviderActionResult:
        """Unload a model, enforcing provider confirmation policy."""

        return await execute_provider_action(
            provider=self._provider(),
            action_id="unload-model",
            request=ProviderActionRequest(
                confirmed=confirmed,
                parameters={
                    "model": model,
                },
            ),
        )


ai_service = AIControlService()
