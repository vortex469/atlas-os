"""Tests for the Atlas Agent health endpoint."""

from fastapi.testclient import TestClient

from app.main import create_app


def test_health() -> None:
    """The health endpoint reports that Atlas Agent is healthy."""

    client = TestClient(create_app())

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "healthy",
        "service": "atlas-agent",
    }
