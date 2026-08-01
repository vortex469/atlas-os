from __future__ import annotations

import pytest

from app.clients import homeassistant_client
from app.context import (
    AtlasContext,
    ConnectionContext,
    MetadataContext,
    RuntimeContext,
    SecretContext,
)


def ha_context(
    *,
    base_url: str = "https://ha.context.local:8123",
    token: str | None = "context-token",
    timeout_seconds: float = 12.5,
    verify_tls: bool = False,
) -> AtlasContext:
    secrets = {}
    if token is not None:
        secrets["token"] = SecretContext(
            name="token",
            source="runtime",
            configured=True,
            redacted="********",
            value=token,
        )
    else:
        secrets["token"] = SecretContext(
            name="token",
            source="missing",
            configured=False,
        )

    return AtlasContext(
        metadata=MetadataContext(
            consumer_id="home_assistant",
            consumer_type="provider",
            name="Context Home Assistant",
        ),
        connection=ConnectionContext(
            mode="https",
            base_url=base_url,
            timeout_seconds=timeout_seconds,
            verify_tls=verify_tls,
            source="runtime",
        ),
        secrets=secrets,
        runtime=RuntimeContext(),
        generation=f"ha-{base_url}",
    )


class FakeResponse:
    status_code = 200

    def __init__(self, payload: object) -> None:
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> object:
        return self._payload


def test_headers_use_context_bearer_token_without_exposing_value() -> None:
    context = ha_context(token="super-secret-token")

    headers = homeassistant_client.get_headers(context)

    assert headers["Authorization"] == "Bearer super-secret-token"
    assert "super-secret-token" not in repr(context)
    assert "super-secret-token" not in repr(context.model_dump())


def test_missing_token_raises_stable_sanitized_error() -> None:
    with pytest.raises(RuntimeError) as error:
        homeassistant_client.get_headers(ha_context(token=None))

    assert str(error.value) == "Home Assistant token is not configured."
    assert "context-token" not in str(error.value)


def test_api_status_uses_context_url_timeout_tls_and_auth(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    def fake_get(url: str, **kwargs: object) -> FakeResponse:
        captured["url"] = url
        captured.update(kwargs)
        return FakeResponse({"message": "API running."})

    monkeypatch.setattr(homeassistant_client.httpx, "get", fake_get)

    payload = homeassistant_client.get_api_status(
        ha_context(
            base_url="https://ha-one.local:9443/root/",
            token="token-one",
            timeout_seconds=21.0,
            verify_tls=True,
        )
    )

    assert payload == {"message": "API running."}
    assert captured["url"] == "https://ha-one.local:9443/root/api/"
    assert captured["headers"] == {
        "Authorization": "Bearer token-one",
        "Content-Type": "application/json",
    }
    assert captured["timeout"] == 21.0
    assert captured["verify"] is True


def test_changing_context_changes_endpoint_and_auth(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, str]] = []

    def fake_get(url: str, **kwargs: object) -> FakeResponse:
        headers = kwargs["headers"]
        assert isinstance(headers, dict)
        calls.append((url, str(headers["Authorization"])))
        return FakeResponse([])

    monkeypatch.setattr(homeassistant_client.httpx, "get", fake_get)

    homeassistant_client.get_states(ha_context(base_url="http://first", token="a"))
    homeassistant_client.get_states(ha_context(base_url="http://second", token="b"))

    assert calls == [
        ("http://first/api/states", "Bearer a"),
        ("http://second/api/states", "Bearer b"),
    ]
