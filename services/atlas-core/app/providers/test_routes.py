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
    body = response.json()
    assert body["error"]["code"] == "not_found"
    assert body["error"]["status"] == 404
    assert body["error"]["message"] == (
        "Unknown provider 'not-real'."
    )
    assert body["request_id"]


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
    body = response.json()
    assert body["error"]["code"] == "not_found"
    assert body["error"]["status"] == 404
    assert body["error"]["message"] == (
        "Unknown provider 'not-real'."
    )
    assert body["request_id"]


def test_provider_advertises_diagnostics_action() -> None:
    response = client.get("/providers/hermes/actions")

    assert response.status_code == 200

    actions = response.json()

    assert any(
        action["id"] == "run-diagnostics"
        for action in actions
    )


def test_provider_diagnostics_action_executes() -> None:
    response = client.post(
        "/providers/hermes/actions/run-diagnostics",
        json={
            "confirmed": False,
            "parameters": {},
        },
    )

    assert response.status_code == 200

    result = response.json()

    assert result["provider_id"] == "hermes"
    assert result["action_id"] == "run-diagnostics"
    assert result["status"] == "succeeded"
    assert result["success"] is True
    assert result["data"]["provider"]["id"] == "hermes"
    assert "health" in result["data"]


def test_provider_action_accepts_an_empty_body() -> None:
    response = client.post(
        "/providers/hermes/actions/run-diagnostics",
    )

    assert response.status_code == 200
    assert response.json()["success"] is True


def test_unknown_provider_action_returns_404() -> None:
    response = client.post(
        "/providers/hermes/actions/not-real",
        json={},
    )

    assert response.status_code == 404
    body = response.json()
    assert body["error"]["code"] == "not_found"
    assert body["error"]["status"] == 404
    assert body["error"]["message"] == (
        "Provider 'hermes' does not advertise action "
        "'not-real'."
    )
    assert body["request_id"]


def test_action_on_unknown_provider_returns_404() -> None:
    response = client.post(
        "/providers/not-real/actions/run-diagnostics",
        json={},
    )

    assert response.status_code == 404
    body = response.json()
    assert body["error"]["code"] == "not_found"
    assert body["error"]["status"] == 404
    assert body["error"]["message"] == (
        "Unknown provider 'not-real'."
    )
    assert body["request_id"]
