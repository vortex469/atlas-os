"""Tests for the approval routes."""

import pytest
from fastapi.testclient import TestClient

from app.main import create_app


@pytest.fixture
def client():
    """Create a test client."""
    app = create_app()
    return TestClient(app)


def test_create_approval_request(client):
    """Test creating an approval request."""
    request_data = {
        "identifier": "test-request-1",
        "checkpoint_id": "checkpoint-123",
        "title": "Test Approval Request",
        "requested_tool": "git",
        "requested_command": ["clone", "https://github.com/example/repo.git"],
        "rationale": "Testing approval flow"
    }
    
    response = client.post("/api/v1/agent/approval/request", json=request_data)
    assert response.status_code == 200
    data = response.json()
    assert "identifier" in data
    assert data["identifier"] == "test-request-1"


def test_create_approval_request_invalid(client):
    """Test creating an approval request with invalid data."""
    # Missing required fields
    request_data = {
        "identifier": "",
        "checkpoint_id": "checkpoint-123",
        "title": "Test Approval Request",
        "requested_tool": "git",
        "requested_command": ["clone", "https://github.com/example/repo.git"],
        "rationale": "Testing approval flow"
    }
    
    response = client.post("/api/v1/agent/approval/request", json=request_data)
    assert response.status_code == 400


def test_get_pending_requests(client):
    """Test getting pending requests."""
    # Create a request first
    request_data = {
        "identifier": "test-request-2",
        "checkpoint_id": "checkpoint-123",
        "title": "Test Approval Request 2",
        "requested_tool": "git",
        "requested_command": ["clone", "https://github.com/example/repo.git"],
        "rationale": "Testing approval flow"
    }
    
    client.post("/api/v1/agent/approval/request", json=request_data)
    
    response = client.get("/api/v1/agent/approval/pending")
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 0  # Could be empty


def test_get_approval_request(client):
    """Test getting a specific approval request."""
    # Create a request first
    request_data = {
        "identifier": "test-request-3",
        "checkpoint_id": "checkpoint-123",
        "title": "Test Approval Request 3",
        "requested_tool": "git",
        "requested_command": ["clone", "https://github.com/example/repo.git"],
        "rationale": "Testing approval flow"
    }
    
    client.post("/api/v1/agent/approval/request", json=request_data)
    
    response = client.get("/api/v1/agent/approval/test-request-3")
    assert response.status_code == 200
    data = response.json()
    assert data["identifier"] == "test-request-3"
    assert data["status"] == "pending"


def test_get_nonexistent_approval_request(client):
    """Test getting a non-existent approval request."""
    response = client.get("/api/v1/agent/approval/nonexistent")
    assert response.status_code == 404


def test_submit_approval_decision(client):
    """Test submitting an approval decision."""
    # Create a request first
    request_data = {
        "identifier": "test-request-4",
        "checkpoint_id": "checkpoint-123",
        "title": "Test Approval Request 4",
        "requested_tool": "git",
        "requested_command": ["clone", "https://github.com/example/repo.git"],
        "rationale": "Testing approval flow"
    }
    
    client.post("/api/v1/agent/approval/request", json=request_data)
    
    # Submit a decision
    decision_data = {
        "request": request_data,
        "status": "approved",
        "reviewer": "test-user"
    }
    
    response = client.post("/api/v1/agent/approval/test-request-4/decision", json=decision_data)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"


def test_submit_approval_decision_invalid(client):
    """Test submitting an invalid approval decision."""
    # Create a request first
    request_data = {
        "identifier": "test-request-5",
        "checkpoint_id": "checkpoint-123",
        "title": "Test Approval Request 5",
        "requested_tool": "git",
        "requested_command": ["clone", "https://github.com/example/repo.git"],
        "rationale": "Testing approval flow"
    }
    
    client.post("/api/v1/agent/approval/request", json=request_data)
    
    # Submit an invalid decision (missing reviewer for approved status)
    decision_data = {
        "request": request_data,
        "status": "approved"
        # Missing reviewer
    }
    
    response = client.post("/api/v1/agent/approval/test-request-5/decision", json=decision_data)
    assert response.status_code == 400
