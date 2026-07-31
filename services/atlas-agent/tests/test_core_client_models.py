import pytest
from pydantic import ValidationError

from app.core_client.models import (
    AtlasCoreHealth,
    AtlasCoreIntelligenceSummary,
    AtlasCoreStatus,
    ServiceHealth,
)


def test_service_health_valid_payload():
    """Test valid ServiceHealth payload."""
    data = {
        "provider_id": "test-provider",
        "status": "healthy",
        "latency_ms": 150.5,
        "http_status": 200,
        "message": "All good",
        "details": {"version": "1.0"}
    }
    health = ServiceHealth(**data)
    assert health.provider_id == "test-provider"
    assert health.status == "healthy"
    assert health.latency_ms == 150.5
    assert health.http_status == 200
    assert health.message == "All good"
    assert health.details == {"version": "1.0"}

def test_service_health_default_values():
    """Test default optional values."""
    health = ServiceHealth(provider_id="test", status="healthy")
    assert health.latency_ms is None
    assert health.http_status is None
    assert health.message is None
    assert health.details == {}

def test_service_health_details_independent_default():
    """Test that details uses an independent default dictionary."""
    health1 = ServiceHealth(provider_id="test1", status="healthy")
    health2 = ServiceHealth(provider_id="test2", status="healthy")

    # Modify one instance's details
    health1.details["key"] = "value"

    # The other should be unaffected
    assert health2.details == {}
    assert health1.details == {"key": "value"}

def test_atlas_core_health_valid_payload():
    """Test valid AtlasCoreHealth payload with nested service."""
    service_data = {
        "provider_id": "test-provider",
        "status": "healthy"
    }

    data = {
        "atlas": "test-atlas",
        "services": {"service1": service_data}
    }

    core_health = AtlasCoreHealth(**data)
    assert core_health.atlas == "test-atlas"
    assert "service1" in core_health.services
    assert core_health.services["service1"].provider_id == "test-provider"
    assert core_health.services["service1"].status == "healthy"

def test_atlas_core_status_valid_payload():
    """Test valid AtlasCoreStatus payload."""
    data = {
        "atlas": "test-atlas",
        "assistant": "test-assistant",
        "engine": "test-engine",
        "release": "1.0.0"
    }

    status = AtlasCoreStatus(**data)
    assert status.atlas == "test-atlas"
    assert status.assistant == "test-assistant"
    assert status.engine == "test-engine"
    assert status.release == "1.0.0"

def test_missing_required_fields_rejected():
    """Test that missing required fields are rejected."""
    # Test ServiceHealth missing required fields
    with pytest.raises(ValidationError):
        ServiceHealth(latency_ms=100)

    with pytest.raises(ValidationError):
        ServiceHealth(status="healthy")

    # Test AtlasCoreStatus missing required fields
    with pytest.raises(ValidationError):
        AtlasCoreStatus(atlas="test-atlas", assistant="test")

    with pytest.raises(ValidationError):
        AtlasCoreStatus(atlas="test-atlas", assistant="test", engine="test")

def test_invalid_nested_service_rejected():
    """Test that invalid nested service payload is rejected."""
    # This should work
    valid_data = {
        "atlas": "test-atlas",
        "services": {"service1": {"provider_id": "test", "status": "healthy"}}
    }

    core_health = AtlasCoreHealth(**valid_data)
    assert core_health.atlas == "test-atlas"

    # This should fail
    invalid_data = {
        "atlas": "test-atlas",
        "services": {"service1": {"status": "healthy"}}  # missing provider_id
    }

    with pytest.raises(ValidationError):
        AtlasCoreHealth(**invalid_data)


def test_atlas_core_intelligence_summary_valid_payload() -> None:
    summary = AtlasCoreIntelligenceSummary.model_validate(
        {
            "score": 72,
            "status": "warning",
            "summary": "Atlas requires attention.",
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
            "assessments": [
                {
                    "title": "Review provider health",
                    "priority": "high",
                }
            ],
            "recommendations": [
                {
                    "title": "Restore provider",
                    "reason": "The provider affects Atlas health.",
                    "priority": "high",
                    "confidence": 0.9,
                    "estimated_effort": "small",
                }
            ],
        }
    )

    assert summary.findings[0].id == "finding-1"
    assert summary.assessments[0].priority == "high"
    assert summary.recommendations[0].confidence == 0.9


def test_atlas_core_intelligence_summary_has_immutable_defaults() -> None:
    first = AtlasCoreIntelligenceSummary(
        score=100,
        status="healthy",
        summary="Healthy",
    )
    second = AtlasCoreIntelligenceSummary(
        score=100,
        status="healthy",
        summary="Healthy",
    )

    assert first.findings == ()
    assert second.findings == ()


def test_atlas_core_intelligence_summary_rejects_invalid_nested_data() -> None:
    with pytest.raises(ValidationError):
        AtlasCoreIntelligenceSummary.model_validate(
            {
                "score": 50,
                "status": "warning",
                "summary": "Invalid finding",
                "findings": [{"id": "missing-required-fields"}],
            }
        )
