from __future__ import annotations

import asyncio
from typing import Any

import pytest

from app.actions import (
    ProviderActionConfirmationRequiredError,
    ProviderActionResult,
)
from app.application.ai_service import AIControlService
from app.providers import (
    Provider,
    ProviderAction,
    ProviderHealth,
    ProviderMetadata,
    ProviderPriority,
    ProviderRegistry,
    ProviderWorkspace,
)


class FakeOllamaProvider(Provider):
    """Test provider that records AI control operations."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self._metadata = ProviderMetadata(
            id="ollama",
            name="Ollama",
            workspace=ProviderWorkspace.DEVELOPER,
            priority=ProviderPriority.CRITICAL,
        )

    @property
    def metadata(self) -> ProviderMetadata:
        return self._metadata

    async def get_health(self) -> ProviderHealth:
        return ProviderHealth(
            status="online",
            latency_ms=1,
            http_status=200,
        )

    async def get_actions(self) -> list[ProviderAction]:
        return [
            ProviderAction(
                id="list-models",
                label="List Models",
            ),
            ProviderAction(
                id="runtime-status",
                label="Runtime Status",
            ),
            ProviderAction(
                id="load-model",
                label="Load Model",
            ),
            ProviderAction(
                id="unload-model",
                label="Unload Model",
                requires_confirmation=True,
            ),
        ]

    async def execute_action(
        self,
        action_id: str,
        parameters: dict[str, Any],
    ) -> ProviderActionResult:
        self.calls.append((action_id, parameters))

        return ProviderActionResult(
            provider_id=self.metadata.id,
            action_id=action_id,
            status="succeeded",
            success=True,
            message=f"Executed {action_id}.",
            data={
                "parameters": parameters,
            },
        )


def make_service() -> tuple[AIControlService, FakeOllamaProvider]:
    registry = ProviderRegistry()
    provider = FakeOllamaProvider()
    registry.register(provider)

    return (
        AIControlService(registry=registry),
        provider,
    )


def test_installed_models_uses_list_models_action() -> None:
    service, provider = make_service()

    result = asyncio.run(service.installed_models())

    assert result.success is True
    assert provider.calls == [
        ("list-models", {}),
    ]


def test_running_models_uses_runtime_status_action() -> None:
    service, provider = make_service()

    result = asyncio.run(service.running_models())

    assert result.success is True
    assert provider.calls == [
        ("runtime-status", {}),
    ]


def test_load_model_forwards_model_name() -> None:
    service, provider = make_service()

    result = asyncio.run(
        service.load_model("gemma4:12b")
    )

    assert result.success is True
    assert provider.calls == [
        (
            "load-model",
            {
                "model": "gemma4:12b",
            },
        ),
    ]


def test_unload_model_requires_confirmation() -> None:
    service, provider = make_service()

    with pytest.raises(
        ProviderActionConfirmationRequiredError,
        match="requires confirmation",
    ):
        asyncio.run(
            service.unload_model("gemma4:12b")
        )

    assert provider.calls == []


def test_confirmed_unload_forwards_model_name() -> None:
    service, provider = make_service()

    result = asyncio.run(
        service.unload_model(
            "gemma4:12b",
            confirmed=True,
        )
    )

    assert result.success is True
    assert provider.calls == [
        (
            "unload-model",
            {
                "model": "gemma4:12b",
            },
        ),
    ]
