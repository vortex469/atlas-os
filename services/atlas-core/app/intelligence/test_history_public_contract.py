import json
from datetime import UTC, datetime
from pathlib import Path

from app.intelligence.report import (
    IntelligenceTelemetry,
    IntelligenceTelemetrySnapshot,
    ProviderCollectionTiming,
)


def _expected_fixture() -> list[dict[str, object]]:
    rows = [
        IntelligenceTelemetrySnapshot(
            id=f"snapshot-{status}",
            collected_at=datetime(2026, 1, 1, 12, minute, tzinfo=UTC),
            telemetry=IntelligenceTelemetry(
                provider_collection_duration_ms=37.25,
                provider_timeout_seconds=3,
                providers=[
                    ProviderCollectionTiming(
                        provider_id="proxmox",
                        provider_name="Proxmox",
                        status=status,
                        duration_ms=21.25,
                        finding_count=2,
                    )
                ],
            ),
        )
        for minute, status in enumerate(["completed", "timed_out", "failed"])
    ]
    rows.append(
        IntelligenceTelemetrySnapshot(
            id="native-defaults",
            collected_at=datetime(2026, 1, 1, 12, tzinfo=UTC).replace(tzinfo=None),
            telemetry=IntelligenceTelemetry(),
        )
    )
    return [row.model_dump(mode="json") for row in rows]


def test_mission_control_history_fixture_matches_public_models() -> None:
    fixture = (
        Path(__file__).resolve().parents[4]
        / "services/mission-control/src/test/intelligenceHistory.fixture.json"
    )
    assert json.loads(fixture.read_text()) == _expected_fixture()
