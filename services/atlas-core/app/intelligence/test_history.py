from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from app.intelligence.history import IntelligenceTelemetryHistory
from app.intelligence.report import (
    IntelligenceTelemetry,
    ProviderCollectionTiming,
)
from app.routes.intelligence import intelligence_telemetry_history


def telemetry(duration_ms: float) -> IntelligenceTelemetry:
    return IntelligenceTelemetry(
        provider_collection_duration_ms=duration_ms,
        provider_timeout_seconds=10,
        providers=[
            ProviderCollectionTiming(
                provider_id="frigate",
                provider_name="Frigate",
                status="completed",
                duration_ms=duration_ms,
                finding_count=1,
            ),
        ],
    )


def test_history_is_persistent_and_newest_first(
    tmp_path: Path,
) -> None:
    database = tmp_path / "telemetry.db"
    now = datetime.now(UTC)
    history = IntelligenceTelemetryHistory(database)
    oldest = history.append(
        telemetry(10),
        collected_at=now - timedelta(minutes=1),
    )
    newest = history.append(telemetry(20), collected_at=now)
    history.close()

    reopened = IntelligenceTelemetryHistory(database)
    snapshots = reopened.list()
    reopened.close()

    assert [snapshot.id for snapshot in snapshots] == [
        newest.id,
        oldest.id,
    ]
    assert (
        snapshots[0].telemetry.provider_collection_duration_ms
        == 20
    )


def test_history_enforces_entry_and_retention_bounds() -> None:
    history = IntelligenceTelemetryHistory(
        max_entries=2,
        retention_days=1,
    )
    now = datetime.now(UTC)
    history.append(
        telemetry(1),
        collected_at=now - timedelta(days=2),
    )
    history.append(telemetry(2), collected_at=now)
    history.append(
        telemetry(3),
        collected_at=now + timedelta(seconds=1),
    )
    history.append(
        telemetry(4),
        collected_at=now + timedelta(seconds=2),
    )

    snapshots = history.list()
    history.close()

    assert [
        snapshot.telemetry.provider_collection_duration_ms
        for snapshot in snapshots
    ] == [4, 3]


@pytest.mark.parametrize("limit", [0, 501])
def test_history_limit_is_bounded(limit: int) -> None:
    history = IntelligenceTelemetryHistory()

    with pytest.raises(ValueError):
        history.list(limit=limit)

    history.close()


def test_history_route_returns_persisted_snapshots(
    isolated_intelligence_history,
) -> None:
    isolated_intelligence_history.append(telemetry(25))

    snapshots = intelligence_telemetry_history(limit=10)

    assert len(snapshots) == 1
    assert (
        snapshots[0].telemetry.provider_collection_duration_ms
        == 25
    )
