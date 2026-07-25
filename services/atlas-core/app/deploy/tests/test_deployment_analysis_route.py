from app.main import app
from app.testing import ASGITestClient


client = ASGITestClient(app)


def test_analyze_compose_deployment() -> None:
    response = client.post(
        "/analysis/deployments",
        json={
            "source": "compose",
            "reference": "test-compose",
            "document": {
                "services": {
                    "web": {
                        "image": "nginx:latest",
                        "ports": ["8080:80"],
                    }
                }
            },
        },
    )

    assert response.status_code == 200

    body = response.json()
    result = body["result"]

    assert result["analysis"]["analyzer"] == "compose"
    assert len(result["analysis"]["plan"]["components"]) == 1
    assert len(result["planning"]["proposal"]["steps"]) >= 1
    assert result["planning"]["proposal"]["approval_required"] is True
