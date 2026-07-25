import asyncio

import httpx
import pytest

from app.providers import loader
from app.providers.qdrant import QdrantProvider
from app.providers.registry import ProviderRegistry


def service(**overrides) -> dict:
    return {
        "name": "Qdrant",
        "host": "qdrant.example.test",
        "port": 6333,
        "protocol": "https",
        "critical": False,
        **overrides,
    }


def collections_response(*names: str) -> dict:
    return {
        "result": {
            "collections": [
                {"name": name}
                for name in names
            ],
        },
        "status": "ok",
        "time": 0.001,
    }


def test_qdrant_health_uses_api_key_and_sanitizes_inventory() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/collections"
        assert request.headers["api-key"] == "test-key"
        return httpx.Response(
            200,
            json=collections_response("memory", "documents"),
        )

    provider = QdrantProvider(
        service(expected_collections=["memory"]),
        api_key="test-key",
        transport=httpx.MockTransport(handler),
    )

    health = asyncio.run(provider.get_health())

    assert health.status == "online"
    assert health.http_status == 200
    assert health.details["collection_count"] == 2
    assert health.details["collections"] == [
        "documents",
        "memory",
    ]
    assert health.details["missing_expected_collections"] == []
    assert "test-key" not in str(health.model_dump())


def test_qdrant_can_use_unauthenticated_internal_api() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert "api-key" not in request.headers
        return httpx.Response(
            200,
            json=collections_response(),
        )

    provider = QdrantProvider(
        service(protocol="http", verify_tls=False),
        api_key="",
        transport=httpx.MockTransport(handler),
    )

    health = asyncio.run(provider.get_health())

    assert health.status == "online"
    assert health.details["authenticated"] is False


def test_missing_expected_collections_produce_finding() -> None:
    provider = QdrantProvider(
        service(
            expected_collections=["documents", "memory"],
        ),
        api_key="test-key",
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                200,
                json=collections_response("memory"),
            ),
        ),
    )

    findings = asyncio.run(provider.get_findings())

    assert len(findings) == 1
    assert findings[0].id == (
        "qdrant-expected-collections-missing"
    )
    assert findings[0].details["collections"] == ["documents"]
    assert findings[0].metric["missing_collections"] == 1


def test_empty_qdrant_finding_is_advisory() -> None:
    provider = QdrantProvider(
        service(),
        api_key="test-key",
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                200,
                json=collections_response(),
            ),
        ),
    )

    findings = asyncio.run(provider.get_findings())

    assert findings[0].id == "qdrant-no-collections"
    assert findings[0].severity == "info"
    assert findings[0].affects_health is False


def test_qdrant_authentication_failure_is_degraded() -> None:
    provider = QdrantProvider(
        service(),
        api_key="expired",
        transport=httpx.MockTransport(
            lambda request: httpx.Response(403),
        ),
    )

    health = asyncio.run(provider.get_health())

    assert health.status == "degraded"
    assert health.http_status == 403
    assert health.message == "Qdrant API authentication failed."


def test_critical_qdrant_connection_failure_is_critical() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError(
            "Connection refused",
            request=request,
        )

    provider = QdrantProvider(
        service(critical=True),
        api_key="test-key",
        transport=httpx.MockTransport(handler),
    )

    findings = asyncio.run(provider.get_findings())

    assert findings[0].id == "qdrant-api-offline"
    assert findings[0].severity == "critical"


@pytest.mark.parametrize(
    "expected_collections",
    [
        "memory",
        ["memory", ""],
        ["memory", "memory"],
    ],
)
def test_invalid_expected_collections_are_rejected(
    expected_collections,
) -> None:
    with pytest.raises(ValueError):
        QdrantProvider(
            service(
                expected_collections=expected_collections,
            ),
        )


def test_invalid_collection_payload_is_offline() -> None:
    provider = QdrantProvider(
        service(),
        api_key="test-key",
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                200,
                json={"result": {"collections": [{"id": 1}]}},
            ),
        ),
    )

    health = asyncio.run(provider.get_health())

    assert health.status == "offline"
    assert "invalid collection entry" in health.details["error"]


def test_loader_selects_qdrant_provider(monkeypatch) -> None:
    registry = ProviderRegistry()
    monkeypatch.setattr(loader, "provider_registry", registry)
    monkeypatch.setattr(
        loader,
        "load_inventory",
        lambda: {
            "services": {
                "qdrant": service(),
            },
        },
    )

    loader.load_provider_registry()

    assert isinstance(
        registry.get("qdrant"),
        QdrantProvider,
    )
