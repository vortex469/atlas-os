from fastapi.testclient import TestClient

from app.main import app
from app.providers.loader import load_provider_registry

client = TestClient(app)


def setup_module() -> None:
    """Populate the provider registry for API integration tests."""

    load_provider_registry()


def test_list_providers_returns_200() -> None:
    response = client.get("/providers")

    assert response.status_code == 200


def test_provider_list_is_not_empty() -> None:
    response = client.get("/providers")
    data = response.json()

    assert isinstance(data, list)
    assert len(data) > 0


def test_hermes_provider_exists() -> None:
    response = client.get("/providers/hermes")

    assert response.status_code == 200

    data = response.json()

    assert data["id"] == "hermes"
    assert data["name"] == "Hermes"
    assert data["health"]["status"] in {
        "online",
        "offline",
        "degraded",
    }


def test_unknown_provider_returns_404() -> None:
    response = client.get("/providers/not-real")

    assert response.status_code == 404
    assert response.json()["detail"] == (
        "Unknown provider 'not-real'."
    )


def test_every_provider_contains_required_fields() -> None:
    response = client.get("/providers")

    assert response.status_code == 200

    for provider in response.json():
        assert "id" in provider
        assert "name" in provider
        assert "workspace" in provider
        assert "priority" in provider
        assert "capabilities" in provider
        assert "health" in provider


def test_provider_actions_returns_a_list() -> None:
    response = client.get("/providers/hermes/actions")

    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_unknown_provider_actions_return_404() -> None:
    response = client.get("/providers/not-real/actions")

    assert response.status_code == 404
    assert response.json()["detail"] == (
        "Unknown provider 'not-real'."
    )
