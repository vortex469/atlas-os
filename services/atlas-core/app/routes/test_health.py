from app.models.contracts import AtlasHealth
from app.routes.health import health


def test_health_exposes_provider_link_and_details(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        "app.routes.health.get_health",
        lambda: {
            "Example Service": {
                "provider_id": "example-service",
                "status": "online",
                "latency_ms": 12,
                "http_status": 200,
                "message": None,
                "details": {
                    "url": "http://example.test/health",
                    "critical": True,
                },
            },
        },
    )

    response = AtlasHealth.model_validate(health())
    service = response.services["Example Service"]

    assert service.provider_id == "example-service"
    assert service.details == {
        "url": "http://example.test/health",
        "critical": True,
    }
