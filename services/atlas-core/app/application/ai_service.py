from __future__ import annotations

import asyncio
from typing import Any
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

    async def status(self) -> dict[str, Any]:
        """Return an aggregated view of the Atlas AI subsystem."""

        provider = self._provider()

        health, installed, running = await asyncio.gather(
            provider.get_health(),
            self.installed_models(),
            self.running_models(),
        )

        installed_models = (
            installed.data.get("models", [])
            if installed.success
            else []
        )
        running_models = (
            running.data.get("running_models", [])
            if running.success
            else []
        )

        return {
            "provider": {
                "id": provider.metadata.id,
                "name": provider.metadata.name,
                "online": health.status == "online",
            },
            "health": health.model_dump(mode="json"),
            "models": {
                "installed": installed_models,
                "installed_count": len(installed_models),
                "running": running_models,
                "running_count": len(running_models),
            },
            "errors": {
                "installed_models": (
                    None
                    if installed.success
                    else installed.message
                ),
                "running_models": (
                    None
                    if running.success
                    else running.message
                ),
            },
        }

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
