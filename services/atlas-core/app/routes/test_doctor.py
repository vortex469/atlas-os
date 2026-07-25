from datetime import datetime, timezone

from fastapi.testclient import TestClient

from app.doctor import DoctorCheck, DoctorReport
from app.main import app
from app.routes import ops


client = TestClient(app)


def test_doctor_report_is_available_from_ops(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        ops,
        "run_atlas_doctor",
        lambda: DoctorReport(
            status="degraded",
            score=95,
            checked_at=datetime.now(timezone.utc),
            configuration_ok=True,
            checks=[
                DoctorCheck(name="Docker", passed=True),
            ],
            warnings=["Optional service offline."],
        ),
    )

    response = client.get("/api/v1/ops/doctor")

    assert response.status_code == 200
    assert response.json()["status"] == "degraded"
    assert response.json()["score"] == 95
    assert response.json()["checks"] == [
        {
            "name": "Docker",
            "passed": True,
            "error": None,
        },
    ]
