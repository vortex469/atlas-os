from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient

from app.actions import provider_action_history
from app.main import app
from app.providers.loader import load_provider_registry


client = TestClient(app)


@pytest.fixture(autouse=True)
def reset_action_history() -> Generator[None, None, None]:
    provider_action_history.clear()
    load_provider_registry()
    yield
    provider_action_history.clear()


def test_executed_action_is_available_in_history() -> None:
    response = client.post(
        "/api/v1/providers/hermes/actions/run-diagnostics",
        headers={"X-Request-ID": "audit-request-123"},
        json={
            "confirmed": False,
            "parameters": {
                "sensitive": "must-not-be-recorded",
            },
        },
    )

    assert response.status_code == 200

    history_response = client.get("/api/v1/ops/actions")

    assert history_response.status_code == 200
    entries = history_response.json()
    assert len(entries) == 1

    entry = entries[0]
    assert entry["provider_id"] == "hermes"
    assert entry["action_id"] == "run-diagnostics"
    assert entry["status"] == "succeeded"
    assert entry["request_id"] == "audit-request-123"
    assert entry["parameter_names"] == ["sensitive"]
    assert "parameters" not in entry
    assert "must-not-be-recorded" not in history_response.text


def test_action_history_status_filter_is_validated() -> None:
    response = client.get(
        "/api/v1/ops/actions",
        params={"status": "not-a-status"},
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == (
        "validation_error"
    )
