from __future__ import annotations

from time import perf_counter
from typing import Any
from urllib.parse import urljoin

import httpx

from app.actions.models import ProviderActionResult
from app.context import AtlasContext
from app.providers import (
    Provider,
    ProviderAction,
    ProviderCapability,
    ProviderHealth,
    ProviderMetadata,
    ProviderPriority,
    ProviderWorkspace,
)
from app.providers.context_helpers import (
    base_url_from_context,
    context_from_legacy_service,
    metadata_from_context,
    timeout_from_context,
)


class OllamaProvider(Provider):
    """Atlas provider for an Ollama model-inference service."""

    def __init__(
        self,
        service: AtlasContext | dict[str, Any],
        *,
        timeout_seconds: float | None = None,
        pull_timeout_seconds: float = 900.0,
    ) -> None:
        # Temporary compatibility seam for direct legacy constructors.
        self.atlas_context = (
            service
            if isinstance(service, AtlasContext)
            else context_from_legacy_service("ollama", service)
        )
        self._timeout_seconds = timeout_seconds or timeout_from_context(
            self.atlas_context,
        )
        self._pull_timeout_seconds = pull_timeout_seconds
        self._critical = bool(
            self.atlas_context.metadata.metadata.get("critical", False),
        )

        self._base_url = base_url_from_context(
            self.atlas_context,
            default_port=11434,
        )

        self._metadata = metadata_from_context(
            self.atlas_context,
            default_description=(
                "Local model inference, model inventory, and model lifecycle provider."
            ),
            default_workspace=ProviderWorkspace.DEVELOPER,
            default_icon="brain",
            default_priority=ProviderPriority.HIGH,
            default_capabilities=frozenset(
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
                    "critical": self._critical,
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
            raise ValueError(  # noqa: TRY004
                "Ollama returned an invalid models response."
            )

        return models

    async def list_running_models(self) -> list[dict[str, Any]]:
        async with httpx.AsyncClient(
            timeout=self._timeout_seconds,
        ) as client:
            response = await client.get(
                self._url("/api/ps"),
            )
            response.raise_for_status()
            payload = response.json()

        models = payload.get("models", [])

        if not isinstance(models, list):
            raise ValueError(  # noqa: TRY004
                "Ollama returned an invalid running models response."
            )

        return models

    async def load_model(
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
                self._url("/api/generate"),
                json={
                    "model": normalized_model,
                    "prompt": "",
                    "stream": False,
                    "keep_alive": -1,
                },
            )
            response.raise_for_status()
            payload = response.json()

        if not isinstance(payload, dict):
            raise ValueError(  # noqa: TRY004
                "Ollama returned an invalid load response."
            )

        return payload

    async def unload_model(
        self,
        model: str,
    ) -> dict[str, Any]:
        normalized_model = model.strip()

        if not normalized_model:
            raise ValueError(
                "A non-empty model name is required."
            )

        async with httpx.AsyncClient(
            timeout=self._timeout_seconds,
        ) as client:
            response = await client.post(
                self._url("/api/generate"),
                json={
                    "model": normalized_model,
                    "prompt": "",
                    "stream": False,
                    "keep_alive": 0,
                },
            )
            response.raise_for_status()
            payload = response.json()

        if not isinstance(payload, dict):
            raise ValueError(  # noqa: TRY004
                "Ollama returned an invalid unload response."
            )

        return payload

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
            raise ValueError(  # noqa: TRY004
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
                    id="runtime-status",
                    label="Runtime Status",
                    description="Show currently loaded Ollama models.",
                    icon="cpu",
                    requires_confirmation=False,
                    destructive=False,
                    enabled=True,
                ),

                ProviderAction(
                    id="load-model",
                    label="Load Model",
                    description=(
                        "Load an Ollama model into memory and keep "
                        "it resident."
                    ),
                    icon="upload",
                    requires_confirmation=False,
                    destructive=False,
                    enabled=True,
                    parameters={
                        "model": {
                            "type": "string",
                            "required": True,
                            "description": "Installed Ollama model name.",
                            "example": "gemma4:12b",
                        }
                    },
                ),
                ProviderAction(
                    id="unload-model",
                    label="Unload Model",
                    description=(
                        "Unload an Ollama model and release its "
                        "runtime memory."
                    ),
                    icon="power",
                    requires_confirmation=True,
                    destructive=False,
                    enabled=True,
                    parameters={
                        "model": {
                            "type": "string",
                            "required": True,
                            "description": "Loaded Ollama model name.",
                            "example": "gemma4:12b",
                        }
                    },
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

        if action_id == "runtime-status":
            try:
                models = await self.list_running_models()
            except (
                httpx.HTTPError,
                ValueError,
            ) as error:
                return ProviderActionResult(
                    provider_id=self.metadata.id,
                    action_id=action_id,
                    status="failed",
                    success=False,
                    message="Unable to retrieve Ollama runtime status.",
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
                    f"Found {len(models)} running "
                    f"Ollama model(s)."
                ),
                data={
                    "running_models": models,
                    "count": len(models),
                },
            )

        if action_id == "load-model":
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
                result = await self.load_model(model)
            except (
                httpx.HTTPError,
                ValueError,
            ) as error:
                return ProviderActionResult(
                    provider_id=self.metadata.id,
                    action_id=action_id,
                    status="failed",
                    success=False,
                    message=f"Unable to load model '{model}'.",
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
                message=f"Loaded Ollama model '{model}'.",
                data={
                    "model": model,
                    "result": result,
                },
            )

        if action_id == "unload-model":
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
                result = await self.unload_model(model)
            except (
                httpx.HTTPError,
                ValueError,
            ) as error:
                return ProviderActionResult(
                    provider_id=self.metadata.id,
                    action_id=action_id,
                    status="failed",
                    success=False,
                    message=f"Unable to unload model '{model}'.",
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
                message=f"Unloaded Ollama model '{model}'.",
                data={
                    "model": model,
                    "result": result,
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
