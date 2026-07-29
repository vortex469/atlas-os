"""Test for context engine."""

import asyncio
from unittest.mock import AsyncMock, MagicMock

from app.context.engine import ContextEngine
from app.context.exceptions import ContextConflictError
from app.context.models import AgentContext
from app.core_client.client import AtlasCoreClient
from app.core_client.exceptions import (
    AtlasCoreConnectionError,
    AtlasCorePayloadError,
    AtlasCoreResponseError,
    AtlasCoreTimeoutError,
)


def test_context_engine_init():
    """Test ContextEngine initialization."""
    mock_client = MagicMock(spec=AtlasCoreClient)
    engine = ContextEngine(mock_client)
    assert engine.core_client == mock_client


def test_get_context():
    """Test get_context method."""
    # Mock the core client responses
    mock_service_health = MagicMock()
    mock_service_health.provider_id = "test-provider"
    mock_service_health.status = "healthy"
    mock_service_health.latency_ms = 100.0
    mock_service_health.http_status = 200
    mock_service_health.message = "OK"
    mock_service_health.details = {"key": "value"}

    mock_health = MagicMock()
    mock_health.atlas = "test-atlas"  # Set the atlas field to match status
    mock_health.services = {
        "test-service": mock_service_health
    }

    mock_status = MagicMock(atlas="test-atlas", assistant="test-assistant", engine="test-engine", release="1.0.0")

    mock_client = AsyncMock()
    mock_client.get_health.return_value = mock_health
    mock_client.get_status.return_value = mock_status

    engine = ContextEngine(mock_client)
    context = asyncio.run(engine.get_context())

    assert isinstance(context, AgentContext)
    assert context.atlas == "test-atlas"
    assert context.assistant == "test-assistant"
    assert context.engine == "test-engine"
    assert context.release == "1.0.0"
    assert "test-service" in context.services
    
    # Test normalized AgentContext fields
    assert hasattr(context, "atlas")
    assert hasattr(context, "assistant")
    assert hasattr(context, "engine")
    assert hasattr(context, "release")
    assert hasattr(context, "services")

    # Test complete services mapping
    service_health = context.services["test-service"]
    assert service_health.provider_id == "test-provider"
    assert service_health.status == "healthy"
    assert service_health.latency_ms == 100.0
    assert service_health.http_status == 200
    assert service_health.message == "OK"
    assert service_health.details == {"key": "value"}

    # Test atlas mismatch raising ContextConflictError
    mock_service_health_mismatch = MagicMock()
    mock_service_health_mismatch.provider_id = "test-provider"
    mock_service_health_mismatch.status = "healthy"
    mock_service_health_mismatch.latency_ms = 100.0
    mock_service_health_mismatch.http_status = 200
    mock_service_health_mismatch.message = "OK"
    mock_service_health_mismatch.details = {"key": "value"}

    mock_health_mismatch = MagicMock()
    mock_health_mismatch.atlas = "different-atlas"  # Set different atlas to trigger mismatch
    mock_health_mismatch.services = {
        "test-service": mock_service_health_mismatch
    }

    mock_status_mismatch = MagicMock(atlas="test-atlas", assistant="test-assistant", engine="test-engine", release="1.0.0")

    mock_client_mismatch = AsyncMock()
    mock_client_mismatch.get_health.return_value = mock_health_mismatch
    mock_client_mismatch.get_status.return_value = mock_status_mismatch

    engine_mismatch = ContextEngine(mock_client_mismatch)
    try:
        asyncio.run(engine_mismatch.get_context())
        assert False, "Expected ContextConflictError was not raised"
    except ContextConflictError:
        pass  # Expected

    # Test AtlasCoreClient exceptions propagating unchanged
    mock_client_error = AsyncMock()
    mock_client_error.get_health.side_effect = AtlasCoreTimeoutError("timeout error")
    mock_client_error.get_status.return_value = mock_status

    engine_error = ContextEngine(mock_client_error)
    try:
        asyncio.run(engine_error.get_context())
        assert False, "Expected AtlasCoreTimeoutError was not raised"
    except AtlasCoreTimeoutError:
        pass  # Expected

    # Test that other AtlasCoreClient exceptions propagate unchanged
    mock_client_error2 = AsyncMock()
    mock_client_error2.get_health.side_effect = AtlasCoreConnectionError("connection error")
    mock_client_error2.get_status.return_value = mock_status

    engine_error2 = ContextEngine(mock_client_error2)
    try:
        asyncio.run(engine_error2.get_context())
        assert False, "Expected AtlasCoreConnectionError was not raised"
    except AtlasCoreConnectionError:
        pass  # Expected

    # Test that generic AtlasCoreClient errors propagate unchanged
    mock_client_error3 = AsyncMock()
    mock_client_error3.get_health.side_effect = AtlasCoreResponseError("response error")
    mock_client_error3.get_status.return_value = mock_status

    engine_error3 = ContextEngine(mock_client_error3)
    try:
        asyncio.run(engine_error3.get_context())
        assert False, "Expected AtlasCoreResponseError was not raised"
    except AtlasCoreResponseError:
        pass  # Expected

    # Test that payload errors propagate unchanged
    mock_client_error4 = AsyncMock()
    mock_client_error4.get_health.side_effect = AtlasCorePayloadError("payload error")
    mock_client_error4.get_status.return_value = mock_status

    engine_error4 = ContextEngine(mock_client_error4)
    try:
        asyncio.run(engine_error4.get_context())
        assert False, "Expected AtlasCorePayloadError was not raised"
    except AtlasCorePayloadError:
        pass  # Expected
