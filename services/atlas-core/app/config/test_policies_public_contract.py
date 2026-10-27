import json
from pathlib import Path

from app.config.policy_models import Policies


def _expected_fixture() -> list[dict[str, object]]:
    return [
        Policies().model_dump(mode="json"),
        Policies.model_validate(
            {
                "proxmox": {
                    "guests": {
                        "110": {"expected": "running"},
                        "111": {"expected": "stopped"},
                        "112": {"expected": "ignored"},
                    }
                },
                "docker": {"containers": {"atlas": {"expected": "stopped"}}},
                "homeassistant": {"ignored_entities": ["sensor.power"]},
                "opnsense": {
                    "pending_update_warning_threshold": 3,
                    "reboot_required_severity": "critical",
                },
                "frigate": {
                    "cameras": {
                        "front": {
                            "expected": "inactive",
                            "minimum_camera_fps": 2.5,
                            "minimum_process_fps": 0,
                        }
                    }
                },
                "obsidian": {"minimum_note_count": 0, "stale_after_days": 7},
                "qdrant": {"expected_collections": ["notes"]},
                "n8n": {"expected_active_workflows": ["backup"]},
                "intelligence": {
                    "providers": {
                        "proxmox": {
                            "maximum_collection_duration_ms": 2.5,
                            "severity": "info",
                        }
                    }
                },
            }
        ).model_dump(mode="json"),
    ]


def test_mission_control_policy_fixture_matches_public_model() -> None:
    fixture = (
        Path(__file__).resolve().parents[4]
        / "services/mission-control/src/test/policies.fixture.json"
    )
    assert json.loads(fixture.read_text()) == _expected_fixture()
