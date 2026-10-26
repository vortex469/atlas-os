from datetime import datetime, timezone

from app.doctor import DoctorCheck, DoctorReport, run_diagnostics
from app.main import app
from app.routes import ops
from app.testing import ASGITestClient

client = ASGITestClient(app)


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


def test_doctor_http_report_does_not_reflect_native_error_text(monkeypatch) -> None:
    def unavailable() -> None:
        raise RuntimeError("Authorization: Bearer doctor-http-private-canary")

    monkeypatch.setattr(
        ops,
        "run_atlas_doctor",
        lambda: run_diagnostics(
            configuration_check=lambda: None,
            infrastructure_checks=(("Proxmox", unavailable),),
        ),
    )
    response = client.get("/api/v1/ops/doctor")
    assert response.status_code == 200
    assert "doctor-http-private-canary" not in response.text
    report = response.json()
    assert report["status"] == "critical"
    assert report["score"] == 80
    assert report["checks"] == [
        {
            "name": "Proxmox",
            "passed": False,
            "error": "Check unavailable. Review its configuration and access, then run Doctor again.",
        }
    ]
