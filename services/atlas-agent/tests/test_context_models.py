"""Test for context models."""

import pytest
from pydantic import ValidationError

from app.context.models import (
    AgentContext,
    IntelligenceContext,
    IntelligenceFailure,
    ServiceHealth,
)


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
    assert context.intelligence is None


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


def test_intelligence_success_and_failure_are_distinct() -> None:
    successful = IntelligenceContext()
    unavailable = IntelligenceContext(
        failure=IntelligenceFailure(
            code="timeout",
            message="Atlas intelligence request timed out.",
        )
    )

    assert successful.failure is None
    assert unavailable.failure is not None
    assert unavailable.failure.code == "timeout"


def test_intelligence_failure_rejects_unknown_code() -> None:
    with pytest.raises(ValidationError):
        IntelligenceFailure(
            code="unexpected",
            message="Unexpected failure.",
        )


def test_intelligence_failure_rejects_nonstandard_message() -> None:
    with pytest.raises(ValidationError):
        IntelligenceFailure(
            code="timeout",
            message="Raw timeout detail",
        )


def test_intelligence_models_are_frozen() -> None:
    intelligence = IntelligenceContext()

    with pytest.raises(ValidationError):
        intelligence.failure = IntelligenceFailure(
            code="payload_error",
            message="Atlas intelligence returned an invalid payload.",
        )
