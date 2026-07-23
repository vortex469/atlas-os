from __future__ import annotations

import asyncio
from typing import Any

import httpx
import pytest

from app.providers.ollama import OllamaProvider


def make_provider() -> OllamaProvider:
    return OllamaProvider(
        {
            "name": "Ollama",
            "host": "10.10.30.146",
            "port": 11434,
            "protocol": "http",
            "critical": True,
        }
    )


def make_response(
    method: str,
    url: str,
    *,
    status_code: int = 200,
    json_data: dict[str, Any] | None = None,
) -> httpx.Response:
    request = httpx.Request(method, url)

    return httpx.Response(
        status_code=status_code,
        request=request,
        json=json_data or {},
    )


def test_metadata_describes_ollama_provider() -> None:
    provider = make_provider()

    assert provider.metadata.id == "ollama"
    assert provider.metadata.name == "Ollama"
    assert provider.metadata.priority.value == "critical"
    assert "actions" in {
        capability.value
        for capability in provider.metadata.capabilities
    }


def test_get_health_returns_version(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_get(
        self,
        url: str,
    ) -> httpx.Response:
        return make_response(
            "GET",
            url,
            json_data={
                "version": "0.12.6",
            },
        )

    monkeypatch.setattr(
        httpx.AsyncClient,
        "get",
        fake_get,
    )

    health = asyncio.run(
        make_provider().get_health()
    )

    assert health.status == "online"
    assert health.http_status == 200
    assert health.details["version"] == "0.12.6"


def test_get_health_returns_offline_on_connection_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_get(
        self,
        url: str,
    ) -> httpx.Response:
        raise httpx.ConnectError(
            "Connection refused.",
            request=httpx.Request("GET", url),
        )

    monkeypatch.setattr(
        httpx.AsyncClient,
        "get",
        fake_get,
    )

    health = asyncio.run(
        make_provider().get_health()
    )

    assert health.status == "offline"
    assert health.http_status is None
    assert "Connection refused" in health.details["error"]


def test_list_models_returns_ollama_models(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    models = [
        {
            "name": "llama3.2:3b",
            "size": 2_000_000_000,
        }
    ]

    async def fake_get(
        self,
        url: str,
    ) -> httpx.Response:
        return make_response(
            "GET",
            url,
            json_data={
                "models": models,
            },
        )

    monkeypatch.setattr(
        httpx.AsyncClient,
        "get",
        fake_get,
    )

    result = asyncio.run(
        make_provider().list_models()
    )

    assert result == models


def test_actions_include_model_operations() -> None:
    actions = asyncio.run(
        make_provider().get_actions()
    )

    action_ids = {
        action.id
        for action in actions
    }

    assert action_ids == {
        "run-diagnostics",
        "list-models",
        "pull-model",
    }

    pull_action = next(
        action
        for action in actions
        if action.id == "pull-model"
    )

    assert pull_action.requires_confirmation is True
    assert pull_action.destructive is False


def test_list_models_action_returns_count(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_list_models():
        return [
            {
                "name": "qwen3:8b",
            },
            {
                "name": "nomic-embed-text",
            },
        ]

    provider = make_provider()

    monkeypatch.setattr(
        provider,
        "list_models",
        fake_list_models,
    )

    result = asyncio.run(
        provider.execute_action(
            "list-models",
            {},
        )
    )

    assert result.success is True
    assert result.data["count"] == 2


def test_pull_model_sends_non_streaming_request(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}

    async def fake_post(
        self,
        url: str,
        *,
        json: dict[str, Any],
    ) -> httpx.Response:
        captured["url"] = url
        captured["json"] = json

        return make_response(
            "POST",
            url,
            json_data={
                "status": "success",
            },
        )

    monkeypatch.setattr(
        httpx.AsyncClient,
        "post",
        fake_post,
    )

    result = asyncio.run(
        make_provider().pull_model(
            "llama3.2:3b",
        )
    )

    assert captured["url"].endswith("/api/pull")
    assert captured["json"] == {
        "model": "llama3.2:3b",
        "stream": False,
    }
    assert result["status"] == "success"


def test_pull_model_action_requires_model_parameter() -> None:
    result = asyncio.run(
        make_provider().execute_action(
            "pull-model",
            {},
        )
    )

    assert result.success is False
    assert result.status == "failed"
    assert "non-empty string" in result.message
