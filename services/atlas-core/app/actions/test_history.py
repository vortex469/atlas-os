import json
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path
from threading import Event

from app.actions import (
    ProviderActionAuditEntry,
    ProviderActionHistory,
)
from app.actions.models import (
    ProviderActionHistoryPage,
    ProviderActionHistoryProvider,
    ProviderActionHistorySummary,
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

def test_page_does_not_mix_retention_snapshots(monkeypatch) -> None:
    history = ProviderActionHistory()
    now = datetime.now(timezone.utc)
    history.append(make_entry("boundary", timestamp=now))
    cutoffs = iter((now - timedelta(seconds=1), now + timedelta(seconds=1)))
    monkeypatch.setattr(history, "_retention_cutoff", lambda: next(cutoffs))
    try:
        first = history.page(limit=25, offset=0)
        assert [entry.id for entry in first.items] == ["boundary"]
        assert first.total == 1
        assert first.has_more is False
        second = history.page(limit=25, offset=0)
        assert second.items == []
        assert second.total == 0
        assert second.has_more is False
    finally:
        history.close()


def test_page_is_consistent_while_another_repository_appends(tmp_path: Path) -> None:
    path = tmp_path / "page-race.db"
    reader = ProviderActionHistory(path)
    writer = ProviderActionHistory(path)
    reader.append(make_entry("before"))
    start_writer = Event()
    writer_attempted = Event()
    observed = []

    def write() -> None:
        if not start_writer.wait(10):
            raise TimeoutError("Page read did not start")
        writer.append(make_entry("after"))

    def trace_reader(statement: str) -> None:
        if "SELECT *" in statement and not start_writer.is_set():
            start_writer.set()
            observed.append(writer_attempted.wait(10))

    def trace_writer(statement: str) -> None:
        if statement.lstrip().startswith("INSERT"):
            writer_attempted.set()

    reader._connection.set_trace_callback(trace_reader)
    writer._connection.set_trace_callback(trace_writer)
    executor = ThreadPoolExecutor(max_workers=1)
    future = executor.submit(write)
    try:
        page = reader.page(limit=25, offset=0)
        assert observed == [True]
        assert [entry.id for entry in page.items] == ["before"]
        assert page.total == 1
        assert page.has_more is False
        future.result(timeout=10)
        assert reader.page(limit=25, offset=0).total == 2
    finally:
        start_writer.set()
        reader._connection.set_trace_callback(None)
        executor.shutdown(wait=True)
        reader.close()
        writer.close()


def test_page_filters_rows_and_totals_with_identical_criteria() -> None:
    history = ProviderActionHistory()
    now = datetime.now(timezone.utc)
    for index, (provider, status, age) in enumerate(
        [
            ("ollama", "succeeded", 0),
            ("ollama", "failed", 0),
            ("docker", "failed", 0),
            ("ollama", "failed", 2),
        ]
    ):
        history.append(
            make_entry(
                str(index),
                provider_id=provider,
                status=status,
                timestamp=now - timedelta(days=age),
            )
        )
    try:
        query = {
            "provider_id": "ollama",
            "status": "failed",
            "completed_from": now - timedelta(days=1),
            "completed_to": now + timedelta(seconds=1),
            "search": "diagnostics",
        }
        page = history.page(limit=1, offset=0, **query)
        assert [entry.id for entry in page.items] == ["1"]
        assert page.total == 1
        assert page.has_more is False
        beyond = history.page(limit=1, offset=1, **query)
        assert beyond.items == []
        assert beyond.total == 1
        assert beyond.has_more is False
    finally:
        history.close()

def test_mission_control_fixture_matches_native_history_dtos() -> None:
    fixture = (
        Path(__file__).resolve().parents[4]
        / "services/mission-control/src/test/actionHistory.fixture.json"
    )
    payload = json.loads(fixture.read_text())
    for key, model in (
        ("entry", ProviderActionAuditEntry),
        ("page", ProviderActionHistoryPage),
        ("summary", ProviderActionHistorySummary),
    ):
        assert (
            model.model_validate(payload[key]).model_dump(mode="json") == payload[key]
        )
    assert [
        ProviderActionHistoryProvider.model_validate(item).model_dump(mode="json")
        for item in payload["providers"]
    ] == payload["providers"]
