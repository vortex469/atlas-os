from datetime import datetime, timedelta, timezone
from pathlib import Path

from app.actions import (
    ProviderActionAuditEntry,
    ProviderActionHistory,
)


def make_entry(
    entry_id: str,
    *,
    provider_id: str = "ollama",
    status: str = "succeeded",
    timestamp: datetime | None = None,
) -> ProviderActionAuditEntry:
    recorded_at = timestamp or datetime.now(timezone.utc)

    return ProviderActionAuditEntry(
        id=entry_id,
        provider_id=provider_id,
        provider_name=provider_id.title(),
        action_id="run-diagnostics",
        action_label="Run Diagnostics",
        status=status,
        success=status == "succeeded",
        message="Action completed.",
        confirmed=False,
        destructive=False,
        parameter_names=[],
        started_at=recorded_at,
        completed_at=recorded_at,
        duration_ms=1,
    )


def test_history_is_newest_first_and_bounded() -> None:
    history = ProviderActionHistory(max_entries=2)

    history.append(make_entry("first"))
    history.append(make_entry("second"))
    history.append(make_entry("third"))

    assert [
        entry.id
        for entry in history.list()
    ] == ["third", "second"]


def test_history_filters_without_exposing_parameters() -> None:
    history = ProviderActionHistory()
    history.append(
        make_entry(
            "ollama-success",
            provider_id="ollama",
        ),
    )
    history.append(
        make_entry(
            "docker-failure",
            provider_id="docker",
            status="failed",
        ),
    )

    entries = history.list(
        provider_id="docker",
        status="failed",
    )

    assert [entry.id for entry in entries] == [
        "docker-failure",
    ]
    assert not hasattr(entries[0], "parameters")


def test_history_persists_between_repository_instances(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "history.db"
    history = ProviderActionHistory(database_path)
    history.append(make_entry("persistent"))
    history.close()

    reopened_history = ProviderActionHistory(database_path)

    assert [
        entry.id
        for entry in reopened_history.list()
    ] == ["persistent"]

    reopened_history.close()


def test_history_prunes_entries_older_than_retention() -> None:
    history = ProviderActionHistory(retention_days=30)
    history.append(
        make_entry(
            "expired",
            timestamp=datetime.now(timezone.utc)
            - timedelta(days=31),
        ),
    )

    assert history.list() == []

    history.close()
