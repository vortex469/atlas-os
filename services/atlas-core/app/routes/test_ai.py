from fastapi.testclient import TestClient

from app.main import app
from app.providers.loader import load_provider_registry


client = TestClient(app)


def setup_module() -> None:
    load_provider_registry()


def test_ai_status_returns_aggregated_state() -> None:
    response = client.get("/ai/status")

    assert response.status_code == 200

    data = response.json()

    assert data["provider"]["id"] == "ollama"
    assert "online" in data["provider"]
    assert "health" in data
    assert "models" in data
    assert "installed_count" in data["models"]
    assert "running_count" in data["models"]
