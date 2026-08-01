"""Test for context engine."""

import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

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
from app.core_client.models import (
    AtlasCoreActionHistoryEntry,
    AtlasCoreIntelligenceSummary,
)


def make_intelligence_summary() -> AtlasCoreIntelligenceSummary:
    return AtlasCoreIntelligenceSummary.model_validate(
        {
            "score": 75,
            "status": "warning",
            "summary": "Atlas has advisory evidence.",
            "findings": [
                {
                    "id": "finding-1",
                    "severity": "warning",
                    "category": "reliability",
                    "source": "ace",
                    "title": "Provider degraded",
                    "message": "One provider is degraded.",
                    "affects_health": True,
                }
            ],
            "assessments": [],
            "recommendations": [
                {
                    "title": "Review provider",
                    "reason": "The provider affects health.",
                    "priority": "high",
                    "confidence": 0.9,
                    "estimated_effort": "small",
                }
            ],
        }
    )


def make_action_history_entry(
    *,
    message: str = "Action failed.",
) -> AtlasCoreActionHistoryEntry:
    timestamp = datetime(2026, 7, 31, 16, 0, tzinfo=timezone.utc)
    return AtlasCoreActionHistoryEntry(
        id="entry-1",
        provider_id="docker",
        provider_name="Docker",
        action_id="restart-container",
        action_label="Restart Container",
        status="failed",
        success=False,
        message=message,
        confirmed=True,
        destructive=True,
        parameter_names=("container",),
        request_id="request-1",
        started_at=timestamp,
        completed_at=timestamp,
        duration_ms=1.0,
    )


def test_context_engine_init():
    """Test ContextEngine initialization."""
    mock_client = MagicMock(spec=AtlasCoreClient)
    engine = ContextEngine(mock_client)
    assert engine.core_client == mock_client


def make_context_client(
    *,
    health_state: str,
    status_state: str,
) -> AsyncMock:
    service = MagicMock(
        provider_id="provider",
        status="healthy",
        latency_ms=None,
        http_status=200,
        message=None,
        details={},
    )
    health = MagicMock(atlas=health_state, services={"service": service})
    status = MagicMock(
        atlas=status_state,
        assistant="assistant",
        engine="engine",
        release="1.0",
    )
    client = AsyncMock()
    client.get_health.return_value = health
    client.get_status.return_value = status
    client.get_intelligence_summary.return_value = make_intelligence_summary()
    client.get_action_history.return_value = ()
    return client


@pytest.mark.parametrize(
    ("health_state", "status_state"),
    (
        ("healthy", "online"),
        ("degraded", "offline"),
        ("healthy", "healthy"),
        ("offline", "offline"),
    ),
)
def test_atlas_availability_states_are_compatible(
    health_state: str,
    status_state: str,
) -> None:
    client = make_context_client(
        health_state=health_state,
        status_state=status_state,
    )

    context = asyncio.run(ContextEngine(client).get_context())

    assert context.atlas == status_state
    assert context.services["service"].status == "healthy"


@pytest.mark.parametrize(
    ("health_state", "status_state"),
    (
        ("healthy", "offline"),
        ("degraded", "online"),
    ),
)
def test_atlas_availability_states_reject_genuine_conflicts(
    health_state: str,
    status_state: str,
) -> None:
    client = make_context_client(
        health_state=health_state,
        status_state=status_state,
    )

    with pytest.raises(ContextConflictError):
        asyncio.run(ContextEngine(client).get_context())


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
    mock_client.get_intelligence_summary.return_value = (
        make_intelligence_summary()
    )
    mock_client.get_action_history.return_value = (
        make_action_history_entry(message="  Action   failed.  "),
    )

    engine = ContextEngine(mock_client)
    context = asyncio.run(engine.get_context())

    assert isinstance(context, AgentContext)
    assert context.atlas == "test-atlas"
    assert context.assistant == "test-assistant"
    assert context.engine == "test-engine"
    assert context.release == "1.0.0"
    assert "test-service" in context.services
    assert context.intelligence is not None
    assert context.intelligence.findings[0].identifier == "finding-1"
    assert (
        context.intelligence.recommendations[0].title
        == "Review provider"
    )
    assert context.action_history is not None
    assert context.action_history.entries[0].message == "Action failed."
    mock_client.get_health.assert_awaited_once_with()
    mock_client.get_status.assert_awaited_once_with()
    mock_client.get_intelligence_summary.assert_awaited_once_with()
    mock_client.get_action_history.assert_awaited_once_with(limit=25)
    
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


@pytest.mark.parametrize(
    ("error", "code", "message"),
    (
        (
            AtlasCoreConnectionError("raw connection detail"),
            "connection_error",
            "Atlas intelligence connection failed.",
        ),
        (
            AtlasCoreTimeoutError("raw timeout detail"),
            "timeout",
            "Atlas intelligence request timed out.",
        ),
        (
            AtlasCoreResponseError("raw response detail"),
            "response_error",
            "Atlas intelligence returned an unsuccessful response.",
        ),
        (
            AtlasCorePayloadError("raw payload detail"),
            "payload_error",
            "Atlas intelligence returned an invalid payload.",
        ),
    ),
)
def test_intelligence_failure_preserves_essential_context(
    error,
    code,
    message,
) -> None:
    service = MagicMock(
        provider_id="provider",
        status="healthy",
        latency_ms=None,
        http_status=200,
        message=None,
        details={},
    )
    health = MagicMock(atlas="atlas", services={"service": service})
    status = MagicMock(
        atlas="atlas",
        assistant="assistant",
        engine="engine",
        release="1.0",
    )
    client = AsyncMock()
    client.get_health.return_value = health
    client.get_status.return_value = status
    client.get_intelligence_summary.side_effect = error
    client.get_action_history.return_value = ()

    context = asyncio.run(ContextEngine(client).get_context())

    assert context.atlas == "atlas"
    assert context.services["service"].status == "healthy"
    assert context.intelligence is not None
    assert context.intelligence.failure is not None
    assert context.intelligence.failure.code == code
    assert context.intelligence.failure.message == message
    assert "raw" not in context.intelligence.failure.message
    client.get_intelligence_summary.assert_awaited_once_with()


def test_action_history_failure_preserves_essential_context() -> None:
    service = MagicMock(
        provider_id="provider",
        status="healthy",
        latency_ms=None,
        http_status=200,
        message=None,
        details={},
    )
    health = MagicMock(atlas="atlas", services={"service": service})
    status = MagicMock(
        atlas="atlas",
        assistant="assistant",
        engine="engine",
        release="1.0",
    )
    client = AsyncMock()
    client.get_health.return_value = health
    client.get_status.return_value = status
    client.get_intelligence_summary.return_value = make_intelligence_summary()
    client.get_action_history.side_effect = AtlasCoreTimeoutError("raw timeout")

    context = asyncio.run(ContextEngine(client).get_context())

    assert context.atlas == "atlas"
    assert context.intelligence is not None
    assert context.action_history is not None
    assert context.action_history.failure is not None
    assert context.action_history.failure.code == "timeout"
    assert (
        context.action_history.failure.message
        == "Atlas action history request timed out."
    )
    assert "raw" not in context.action_history.failure.message


def test_action_history_messages_are_bounded() -> None:
    context = ContextEngine._normalize_action_history(
        (
            make_action_history_entry(message="word " * 100),
        )
    )

    assert len(context.entries[0].message) <= 240
    assert context.entries[0].message.endswith("…")
