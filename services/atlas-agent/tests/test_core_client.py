"""Tests for AtlasCoreClient."""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from app.config.settings import Settings
from app.core_client.client import AtlasCoreClient
from app.core_client.exceptions import (
    AtlasCoreConnectionError,
    AtlasCorePayloadError,
    AtlasCoreResponseError,
    AtlasCoreTimeoutError,
)
from app.core_client.models import AtlasCoreHealth, AtlasCoreStatus


def create_test_settings(host="127.0.0.1", port=8643, timeout=10.0):
    """Create test settings with custom values."""
    return Settings(
        atlas_core_host=host,
        atlas_core_port=port,
        atlas_core_timeout_seconds=timeout
    )


def create_mock_health_response():
    """Create a valid health response payload."""
    return {
        "atlas": "test-atlas",
        "services": {
            "service1": {
                "provider_id": "test-provider",
                "status": "healthy",
                "latency_ms": 150.5,
                "http_status": 200,
                "message": "All good",
                "details": {"version": "1.0"}
            }
        }
    }


def create_mock_status_response():
    """Create a valid status response payload."""
    return {
        "atlas": "test-atlas",
        "assistant": "test-assistant",
        "engine": "test-engine",
        "release": "1.0.0"
    }


@pytest.fixture
def mock_health_response():
    """Mock a valid health response."""
    return create_mock_health_response()


@pytest.fixture
def mock_status_response():
    """Mock a valid status response."""
    return create_mock_status_response()


@pytest.fixture
def mock_settings():
    """Mock settings fixture."""
    return create_test_settings()


@pytest.fixture
def atlas_core_client(mock_settings):
    """Create AtlasCoreClient instance."""
    return AtlasCoreClient(settings=mock_settings)


@pytest.fixture
def mock_client():
    """Mock httpx.AsyncClient."""
    return MagicMock()


def test_get_health_parsing_valid_response(atlas_core_client, mock_health_response):
    """Test that get_health() parses a valid health response."""

    # Create mock transport with proper handler
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/v1/health"
        return httpx.Response(200, json=mock_health_response)

    with httpx.MockTransport(handler) as transport:
        # Inject the mock transport into the client
        client = httpx.AsyncClient(transport=transport)
        atlas_client = AtlasCoreClient(settings=create_test_settings(), client=client)

        # Run the test
        result = asyncio.run(atlas_client.get_health())

        assert isinstance(result, AtlasCoreHealth)
        assert result.atlas == "test-atlas"
        assert "service1" in result.services
        assert result.services["service1"].provider_id == "test-provider"


def test_get_status_parsing_valid_response(atlas_core_client, mock_status_response):
    """Test that get_status() parses a valid status response."""

    # Create mock transport with proper handler
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/v1/status/"
        return httpx.Response(200, json=mock_status_response)

    with httpx.MockTransport(handler) as transport:
        # Inject the mock transport into the client
        client = httpx.AsyncClient(transport=transport)
        atlas_client = AtlasCoreClient(settings=create_test_settings(), client=client)

        # Run the test
        result = asyncio.run(atlas_client.get_status())

        assert isinstance(result, AtlasCoreStatus)
        assert result.atlas == "test-atlas"
        assert result.assistant == "test-assistant"


def test_validate_connection_calls_health_endpoint(atlas_core_client):
    """Test that validate_connection() calls the health endpoint and returns None."""

    # Create mock transport with proper handler
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/v1/health"
        return httpx.Response(200, json=create_mock_health_response())

    with httpx.MockTransport(handler) as transport:
        # Inject the mock transport into the client
        client = httpx.AsyncClient(transport=transport)
        atlas_client = AtlasCoreClient(settings=create_test_settings(), client=client)

        # Run the test
        result = asyncio.run(atlas_client.validate_connection())

        assert result is None


def test_configured_host_and_port_used(atlas_core_client):
    """Test that configured host and port are used for internally created clients."""
    # Create a new client with custom host and port
    custom_settings = create_test_settings(host="192.168.1.100", port=9000)
    client = AtlasCoreClient(settings=custom_settings)

    # The base URL should be constructed with the custom values
    assert client._base_url == "http://192.168.1.100:9000"


def test_configured_timeout_applied(atlas_core_client):
    """Test that configured timeout is applied to internally created clients."""
    # Create a new client with custom timeout
    custom_settings = create_test_settings(timeout=30.0)
    client = AtlasCoreClient(settings=custom_settings)

    # The timeout should be set correctly
    assert client._timeout.connect == 30.0
    assert client._timeout.read == 30.0


def test_injected_client_not_closed_by_close(atlas_core_client, mock_client):
    """Test that injected AsyncClient is not closed by close()."""
    # Create a client with an injected httpx.AsyncClient
    injected_client = MagicMock()
    client_with_injected = AtlasCoreClient(settings=create_test_settings(), client=injected_client)

    # Call close - should not close the injected client
    asyncio.run(client_with_injected.close())

    # The injected client's aclose method should not have been called
    assert not injected_client.aclose.called


def test_internally_created_client_closed_by_close(monkeypatch):
    """Test that internally created AsyncClient is closed by close()."""
    internal_client = MagicMock(spec=httpx.AsyncClient)
    internal_client.aclose = AsyncMock()
    monkeypatch.setattr(
        "app.core_client.client.httpx.AsyncClient",
        lambda: internal_client,
    )
    atlas_client = AtlasCoreClient(settings=create_test_settings())

    assert atlas_client._get_client() is internal_client

    asyncio.run(atlas_client.close())

    internal_client.aclose.assert_awaited_once_with()
    assert atlas_client._client is None


def test_context_manager_closes_internally_owned_client(monkeypatch):
    """Test that async context-manager use closes an internally owned client."""
    internal_client = MagicMock(spec=httpx.AsyncClient)
    internal_client.aclose = AsyncMock()
    monkeypatch.setattr(
        "app.core_client.client.httpx.AsyncClient",
        lambda: internal_client,
    )
    atlas_client = AtlasCoreClient(settings=create_test_settings())
    atlas_client._get_client()

    asyncio.run(atlas_client.__aenter__())
    asyncio.run(atlas_client.__aexit__(None, None, None))

    internal_client.aclose.assert_awaited_once_with()


def test_context_manager_does_not_close_injected_client(atlas_core_client, mock_client):
    """Test that async context-manager use does not close an injected client."""
    # Create a client with an injected httpx.AsyncClient
    injected_client = MagicMock()
    client_with_injected = AtlasCoreClient(settings=create_test_settings(), client=injected_client)

    # Use the context manager
    asyncio.run(client_with_injected.__aenter__())
    asyncio.run(client_with_injected.__aexit__(None, None, None))

    # The injected client's aclose method should not have been called
    assert not injected_client.aclose.called


def test_connect_error_maps_to_atlas_core_connection_error(atlas_core_client):
    """Test that httpx.ConnectError maps to AtlasCoreConnectionError."""

    # Create mock transport with proper handler that raises an error
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection failed")

    with httpx.MockTransport(handler) as transport:
        # Inject the mock transport into the client
        client = httpx.AsyncClient(transport=transport)
        atlas_client = AtlasCoreClient(settings=create_test_settings(), client=client)

        with pytest.raises(AtlasCoreConnectionError) as exc_info:
            asyncio.run(atlas_client.get_health())

        assert "connection failed" in str(exc_info.value)


def test_timeout_exception_maps_to_atlas_core_timeout_error(atlas_core_client):
    """Test that httpx.TimeoutException maps to AtlasCoreTimeoutError."""

    # Create mock transport with proper handler that raises an error
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.TimeoutException("timeout")

    with httpx.MockTransport(handler) as transport:
        # Inject the mock transport into the client
        client = httpx.AsyncClient(transport=transport)
        atlas_client = AtlasCoreClient(settings=create_test_settings(), client=client)

        with pytest.raises(AtlasCoreTimeoutError) as exc_info:
            asyncio.run(atlas_client.get_health())

        assert "timeout" in str(exc_info.value)


def test_request_error_maps_to_atlas_core_connection_error(atlas_core_client):
    """Test that another httpx.RequestError maps to AtlasCoreConnectionError."""

    # Create mock transport with proper handler that raises an error
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.RequestError("request error")

    with httpx.MockTransport(handler) as transport:
        # Inject the mock transport into the client
        client = httpx.AsyncClient(transport=transport)
        atlas_client = AtlasCoreClient(settings=create_test_settings(), client=client)

        with pytest.raises(AtlasCoreConnectionError) as exc_info:
            asyncio.run(atlas_client.get_health())

        assert "request error" in str(exc_info.value)


def test_non_2xx_health_response_maps_to_atlas_core_response_error(atlas_core_client):
    """Test that non-2xx health response maps to AtlasCoreResponseError."""

    # Create mock transport with proper handler
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="server error")

    with httpx.MockTransport(handler) as transport:
        # Inject the mock transport into the client
        client = httpx.AsyncClient(transport=transport)
        atlas_client = AtlasCoreClient(settings=create_test_settings(), client=client)

        with pytest.raises(AtlasCoreResponseError) as exc_info:
            asyncio.run(atlas_client.get_health())

        assert "500" in str(exc_info.value)


def test_non_2xx_status_response_maps_to_atlas_core_response_error(atlas_core_client):
    """Test that non-2xx status response maps to AtlasCoreResponseError."""

    # Create mock transport with proper handler
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, text="service unavailable")

    with httpx.MockTransport(handler) as transport:
        # Inject the mock transport into the client
        client = httpx.AsyncClient(transport=transport)
        atlas_client = AtlasCoreClient(settings=create_test_settings(), client=client)

        with pytest.raises(AtlasCoreResponseError) as exc_info:
            asyncio.run(atlas_client.get_status())

        assert "503" in str(exc_info.value)


def test_invalid_json_maps_to_atlas_core_payload_error(atlas_core_client):
    """Test that invalid JSON maps to AtlasCorePayloadError."""

    # Create mock transport with proper handler
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="invalid json")

    with httpx.MockTransport(handler) as transport:
        # Inject the mock transport into the client
        client = httpx.AsyncClient(transport=transport)
        atlas_client = AtlasCoreClient(settings=create_test_settings(), client=client)

        with pytest.raises(AtlasCorePayloadError) as exc_info:
            asyncio.run(atlas_client.get_health())

        assert "Invalid payload" in str(exc_info.value)


def test_invalid_health_payload_maps_to_atlas_core_payload_error(atlas_core_client):
    """Test that invalid health payload maps to AtlasCorePayloadError."""

    # Create mock transport with proper handler
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"invalid": "payload"})

    with httpx.MockTransport(handler) as transport:
        # Inject the mock transport into the client
        client = httpx.AsyncClient(transport=transport)
        atlas_client = AtlasCoreClient(settings=create_test_settings(), client=client)

        with pytest.raises(AtlasCorePayloadError) as exc_info:
            asyncio.run(atlas_client.get_health())

        assert "Invalid payload" in str(exc_info.value)


def test_invalid_status_payload_maps_to_atlas_core_payload_error(atlas_core_client):
    """Test that invalid status payload maps to AtlasCorePayloadError."""

    # Create mock transport with proper handler
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"invalid": "payload"})

    with httpx.MockTransport(handler) as transport:
        # Inject the mock transport into the client
        client = httpx.AsyncClient(transport=transport)
        atlas_client = AtlasCoreClient(settings=create_test_settings(), client=client)

        with pytest.raises(AtlasCorePayloadError) as exc_info:
            asyncio.run(atlas_client.get_status())

        assert "Invalid payload" in str(exc_info.value)


def test_useful_context_preserved_in_error_messages(atlas_core_client):
    """Test that useful context is preserved in error messages."""

    # Test connection error
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection failed")

    with httpx.MockTransport(handler) as transport:
        # Inject the mock transport into the client
        client = httpx.AsyncClient(transport=transport)
        atlas_client = AtlasCoreClient(settings=create_test_settings(), client=client)

        try:
            asyncio.run(atlas_client.get_health())
            assert False, "Expected exception was not raised"
        except AtlasCoreConnectionError as e:
            # The error message should contain the URL and original error
            assert "http://127.0.0.1:8643/api/v1/health" in str(e)
            assert "connection failed" in str(e)

    # Test timeout error
    def handler_timeout(request: httpx.Request) -> httpx.Response:
        raise httpx.TimeoutException("timeout")

    with httpx.MockTransport(handler_timeout) as transport:
        # Inject the mock transport into the client
        client = httpx.AsyncClient(transport=transport)
        atlas_client = AtlasCoreClient(settings=create_test_settings(), client=client)

        try:
            asyncio.run(atlas_client.get_health())
            assert False, "Expected exception was not raised"
        except AtlasCoreTimeoutError as e:
            # The error message should contain the URL and original error
            assert "http://127.0.0.1:8643/api/v1/health" in str(e)
            assert "timeout" in str(e)
