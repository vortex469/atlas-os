"""Test for context models."""

import pytest
from pydantic import ValidationError

from app.context.models import AgentContext, ServiceHealth


def test_service_health_model():
    """Test ServiceHealth model creation."""
    service = ServiceHealth(
        provider_id="test-provider",
        status="healthy"
    )
    assert service.provider_id == "test-provider"
    assert service.status == "healthy"

def test_agent_context_model():
    """Test AgentContext model creation."""
    context = AgentContext(
        atlas="test-atlas",
        assistant="test-assistant",
        engine="test-engine",
        release="1.0.0",
        services={}
    )
    assert context.atlas == "test-atlas"
    assert context.assistant == "test-assistant"
    assert context.engine == "test-engine"
    assert context.release == "1.0.0"


def test_agent_context_is_frozen() -> None:
    context = AgentContext(
        atlas="test-atlas",
        assistant="test-assistant",
        engine="test-engine",
        release="1.0.0",
        services={},
    )

    with pytest.raises(ValidationError):
        context.release = "changed"
