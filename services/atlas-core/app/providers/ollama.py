from __future__ import annotations

from time import perf_counter
from typing import Any
from urllib.parse import urljoin

import httpx

from app.actions.models import ProviderActionResult
from app.providers import (
    Provider,
    ProviderAction,
    ProviderCapability,
    ProviderHealth,
    ProviderMetadata,
    ProviderPriority,
    ProviderWorkspace,
)


class OllamaProvider(Provider):
    """Atlas provider for an Ollama model-inference service."""

    def __init__(
        self,
        service: dict[str, Any],
        *,
        timeout_seconds: float = 10.0,
        pull_timeout_seconds: float = 900.0,
    ) -> None:
        self._service = service
        self._timeout_seconds = timeout_seconds
        self._pull_timeout_seconds = pull_timeout_seconds

        protocol = service.get("protocol", "http")
        host = service["host"]
        port = service.get("port", 11434)

        self._base_url = f"{protocol}://{host}:{port}/"

        self._metadata = ProviderMetadata(
            id="ollama",
            name=service.get("name", "Ollama"),
            version="1.0.0",
            description=(
                "Local model inference, model inventory, and "
                "model lifecycle provider."
            ),
            workspace=ProviderWorkspace.DEVELOPER,
            icon="brain",
            priority=(
                ProviderPriority.CRITICAL
                if service.get("critical", False)
                else ProviderPriority.HIGH
            ),
            capabilities=frozenset(
                {
                    ProviderCapability.HEALTH,
                    ProviderCapability.ACTIONS,
                    ProviderCapability.METRICS,
                    ProviderCapability.CONFIGURATION,
                }
            ),
        )

    @property
    def metadata(self) -> ProviderMetadata:
        return self._metadata

    def _url(self, path: str) -> str:
        return urljoin(self._base_url, path.lstrip("/"))

    async def get_health(self) -> ProviderHealth:
        started_at = perf_counter()

        try:
            async with httpx.AsyncClient(
                timeout=self._timeout_seconds,
            ) as client:
                response = await client.get(
                    self._url("/api/version"),
                )
                response.raise_for_status()
                payload = response.json()

            latency_ms = round(
                (perf_counter() - started_at) * 1000,
                2,
            )

            return ProviderHealth(
                status="online",
                latency_ms=latency_ms,
                http_status=response.status_code,
                message="Ollama is available.",
                details={
                    "url": self._base_url.rstrip("/"),
                    "version": payload.get("version"),
                    "critical": self._service.get(
                        "critical",
                        False,
                    ),
                },
            )
        except httpx.HTTPStatusError as error:
            latency_ms = round(
                (perf_counter() - started_at) * 1000,
                2,
            )

            return ProviderHealth(
                status="degraded",
                latency_ms=latency_ms,
                http_status=error.response.status_code,
                message="Ollama returned an unexpected status.",
                details={
                    "url": self._base_url.rstrip("/"),
                    "error": str(error),
                },
            )
        except (
            httpx.HTTPError,
            ValueError,
        ) as error:
            latency_ms = round(
                (perf_counter() - started_at) * 1000,
                2,
            )

            return ProviderHealth(
                status="offline",
                latency_ms=latency_ms,
                message="Ollama is unavailable.",
                details={
                    "url": self._base_url.rstrip("/"),
                    "error": str(error),
                },
            )

    async def list_models(self) -> list[dict[str, Any]]:
        async with httpx.AsyncClient(
            timeout=self._timeout_seconds,
        ) as client:
            response = await client.get(
                self._url("/api/tags"),
            )
            response.raise_for_status()
            payload = response.json()

        models = payload.get("models", [])

        if not isinstance(models, list):
            raise ValueError(
                "Ollama returned an invalid models response."
            )

        return models

    async def pull_model(
        self,
        model: str,
    ) -> dict[str, Any]:
        normalized_model = model.strip()

        if not normalized_model:
            raise ValueError(
                "A non-empty model name is required."
            )

        async with httpx.AsyncClient(
            timeout=self._pull_timeout_seconds,
        ) as client:
            response = await client.post(
                self._url("/api/pull"),
                json={
                    "model": normalized_model,
                    "stream": False,
                },
            )
            response.raise_for_status()
            payload = response.json()

        if not isinstance(payload, dict):
            raise ValueError(
                "Ollama returned an invalid pull response."
            )

        return payload

    async def get_actions(self) -> list[ProviderAction]:
        actions = await super().get_actions()

        actions.extend(
            [
                ProviderAction(
                    id="list-models",
                    label="List Models",
                    description=(
                        "List models installed in the local "
                        "Ollama model library."
                    ),
                    icon="list",
                    requires_confirmation=False,
                    destructive=False,
                    enabled=True,
                ),
                ProviderAction(
                    id="pull-model",
                    label="Pull Model",
                    description=(
                        "Download a model into the local Ollama "
                        "model library."
                    ),
                    icon="download",
                    requires_confirmation=True,
                    destructive=False,
                    enabled=True,
                    parameters={
                        "model": {
                            "type": "string",
                            "required": True,
                            "description": (
                                "Ollama model name, optionally "
                                "including a tag."
                            ),
                            "example": "llama3.2:3b",
                        }
                    },
                ),
            ]
        )

        return actions

    async def execute_action(
        self,
        action_id: str,
        parameters: dict[str, Any],
    ) -> ProviderActionResult:
        if action_id == "run-diagnostics":
            return await super().execute_action(
                action_id,
                parameters,
            )

        if action_id == "list-models":
            try:
                models = await self.list_models()
            except (
                httpx.HTTPError,
                ValueError,
            ) as error:
                return ProviderActionResult(
                    provider_id=self.metadata.id,
                    action_id=action_id,
                    status="failed",
                    success=False,
                    message="Unable to list Ollama models.",
                    data={
                        "error": str(error),
                    },
                )

            return ProviderActionResult(
                provider_id=self.metadata.id,
                action_id=action_id,
                status="succeeded",
                success=True,
                message=(
                    f"Found {len(models)} installed "
                    f"Ollama model(s)."
                ),
                data={
                    "models": models,
                    "count": len(models),
                },
            )

        if action_id == "pull-model":
            model = parameters.get("model")

            if not isinstance(model, str) or not model.strip():
                return ProviderActionResult(
                    provider_id=self.metadata.id,
                    action_id=action_id,
                    status="failed",
                    success=False,
                    message=(
                        "Parameter 'model' must be a non-empty "
                        "string."
                    ),
                )

            try:
                result = await self.pull_model(model)
            except (
                httpx.HTTPError,
                ValueError,
            ) as error:
                return ProviderActionResult(
                    provider_id=self.metadata.id,
                    action_id=action_id,
                    status="failed",
                    success=False,
                    message=f"Unable to pull model '{model}'.",
                    data={
                        "model": model,
                        "error": str(error),
                    },
                )

            return ProviderActionResult(
                provider_id=self.metadata.id,
                action_id=action_id,
                status="succeeded",
                success=True,
                message=f"Pulled Ollama model '{model}'.",
                data={
                    "model": model,
                    "result": result,
                },
            )

        return await super().execute_action(
            action_id,
            parameters,
        )
