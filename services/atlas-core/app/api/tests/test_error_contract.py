from app.main import app
from app.testing import ASGITestClient

client = ASGITestClient(app)


def assert_error_contract(
    response,
    *,
    status: int,
    code: str,
) -> dict:
    assert response.status_code == status

    body = response.json()

    assert body["error"]["status"] == status
    assert body["error"]["code"] == code
    assert isinstance(body["error"]["message"], str)
    assert "details" in body["error"]

    assert isinstance(body["request_id"], str)
    assert body["request_id"]
    assert response.headers["X-Request-ID"] == body["request_id"]

    return body


def test_unknown_provider_uses_error_contract() -> None:
    response = client.get(
        "/api/v1/providers/does-not-exist"
    )

    body = assert_error_contract(
        response,
        status=404,
        code="not_found",
    )

    assert "does-not-exist" in body["error"]["message"]


def test_validation_error_uses_error_contract() -> None:
    response = client.post(
        "/api/v1/providers/open-webui/actions/health",
        json={"parameters": "invalid"},
    )

    body = assert_error_contract(
        response,
        status=422,
        code="validation_error",
    )

    assert body["error"]["details"]["errors"]


def test_client_request_id_is_preserved() -> None:
    response = client.get(
        "/api/v1/providers/does-not-exist",
        headers={"X-Request-ID": "atlas-test-request"},
    )

    assert response.headers["X-Request-ID"] == (
        "atlas-test-request"
    )
    assert response.json()["request_id"] == (
        "atlas-test-request"
    )


def test_success_response_keeps_existing_payload() -> None:
    response = client.get("/api/v1")

    assert response.status_code == 200
    assert response.json()["name"] == "Atlas Core API"
    assert response.json()["version"] == "v1"
    assert "error" not in response.json()
    assert response.headers["X-Request-ID"]
