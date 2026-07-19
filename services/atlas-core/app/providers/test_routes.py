from fastapi.testclient import TestClient

from app.main import app
from app.providers.loader import load_provider_registry

client = TestClient(app)


def setup_module():
    """Ensure the provider registry is populated for route tests."""
    load_provider_registry()


def test_list_providers_returns_200():
    response = client.get("/providers")

    assert response.status_code == 200


def test_provider_list_is_not_empty():
    response = client.get("/providers")

    data = response.json()

    assert isinstance(data, list)
    assert len(data) > 0


def test_hermes_provider_exists():
    response = client.get("/providers/hermes")

    assert response.status_code == 200

    data = response.json()

    assert data["id"] == "hermes"
    assert data["name"] == "Hermes"
    assert data["health"]["status"] in (
        "online",
        "offline",
        "degraded",
    )


def test_unknown_provider_returns_404():
    response = client.get("/providers/not-real")

    assert response.status_code == 404

    assert response.json()["detail"] == (
        "Unknown provider 'not-real'."
    )


def test_every_provider_contains_required_fields():
    response = client.get("/providers")

    for provider in response.json():
        assert "id" in provider
        assert "name" in provider
        assert "workspace" in provider
        assert "priority" in provider
        assert "capabilities" in provider
        assert "health" in provider
