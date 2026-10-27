import json
from pathlib import Path

from app.models.contracts import AceSummary


def _expected_fixture() -> list[dict[str, object]]:
    return [
        AceSummary(
            score=100, status="healthy", summary="No findings reported."
        ).model_dump(mode="json"),
        AceSummary.model_validate(
            {
                "score": 120,
                "status": "future_status",
                "summary": "Provider evidence reported.",
                "findings": [
                    {
                        "id": "reported-finding",
                        "severity": "future_severity",
                        "category": "availability",
                        "source": "proxmox",
                        "title": "Reported issue",
                        "message": "Review the reported evidence.",
                        "affects_health": False,
                        "score_penalty": -1,
                        "details": {
                            "unavailable_entities": [
                                {"name": {"nested": "not a display string"}},
                                {"entity_id": "sensor.power", "state": "unknown"},
                            ]
                        },
                    }
                ],
                "assessments": [
                    {"title": "Review evidence", "priority": "future_priority"}
                ],
                "recommendations": [
                    {
                        "title": "Review provider issue",
                        "reason": "Reported evidence requires review.",
                        "priority": "future_priority",
                        "confidence": 1.25,
                        "estimated_effort": "operator review",
                        "component": "proxmox",
                    }
                ],
                "telemetry": {
                    "provider_collection_duration_ms": 10,
                    "provider_timeout_seconds": 3,
                    "providers": [
                        {
                            "provider_id": "proxmox",
                            "provider_name": "Proxmox",
                            "status": status,
                            "duration_ms": 2.5,
                            "finding_count": 1,
                        }
                        for status in ["completed", "timed_out", "failed"]
                    ],
                },
            }
        ).model_dump(mode="json"),
    ]


def test_mission_control_summary_fixture_matches_public_model() -> None:
    fixture = (
        Path(__file__).resolve().parents[4]
        / "services/mission-control/src/test/aceSummary.fixture.json"
    )
    assert json.loads(fixture.read_text()) == _expected_fixture()
