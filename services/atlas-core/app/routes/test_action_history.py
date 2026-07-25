from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app.actions import (
    ProviderActionAuditEntry,
    ProviderActionHistory,
)
from app.main import app
from app.providers.loader import load_provider_registry


client = TestClient(app)


@pytest.fixture(autouse=True)
def load_test_providers() -> None:
    load_provider_registry()


def test_executed_action_is_available_in_history() -> None:
    response = client.post(
        "/api/v1/providers/hermes/actions/run-diagnostics",
        headers={"X-Request-ID": "audit-request-123"},
        json={
            "confirmed": False,
            "parameters": {
                "sensitive": "must-not-be-recorded",
            },
        },
    )

    assert response.status_code == 200

    history_response = client.get("/api/v1/ops/actions")

    assert history_response.status_code == 200
    entries = history_response.json()
    assert len(entries) == 1

    entry = entries[0]
    assert entry["provider_id"] == "hermes"
    assert entry["action_id"] == "run-diagnostics"
    assert entry["status"] == "succeeded"
    assert entry["request_id"] == "audit-request-123"
    assert entry["parameter_names"] == ["sensitive"]
    assert "parameters" not in entry
    assert "must-not-be-recorded" not in history_response.text


def test_action_history_status_filter_is_validated() -> None:
    response = client.get(
        "/api/v1/ops/actions",
        params={"status": "not-a-status"},
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == (
        "validation_error"
    )


def test_action_history_summary_reports_retention() -> None:
    response = client.get("/api/v1/ops/actions/summary")

    assert response.status_code == 200
    assert response.json() == {
        "entry_count": 0,
        "max_entries": 5000,
        "retention_days": 90,
        "oldest_entry_at": None,
        "newest_entry_at": None,
    }


def test_csv_export_is_sanitized(
    isolated_action_history: ProviderActionHistory,
) -> None:
    timestamp = datetime.now(timezone.utc)
    isolated_action_history.append(
        ProviderActionAuditEntry(
            id="export-entry",
            provider_id="formula-provider",
            provider_name="=FORMULA()",
            action_id="run-diagnostics",
            action_label="+Action",
            status="succeeded",
            success=True,
            message="@Message",
            confirmed=False,
            destructive=False,
            parameter_names=["=secret"],
            request_id="\trequest",
            started_at=timestamp,
            completed_at=timestamp,
            duration_ms=1,
        ),
    )

    response = client.get(
        "/api/v1/ops/actions/export",
        params={"format": "csv"},
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith(
        "text/csv",
    )
    assert "'=FORMULA()" in response.text
    assert "'+Action" in response.text
    assert "'@Message" in response.text
    assert "'=secret" in response.text
    assert "'\trequest" in response.text
    assert "Content-Disposition" in response.headers


def test_pruning_requires_confirmation_and_uses_retention(
    isolated_action_history: ProviderActionHistory,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    timestamp = datetime.now(timezone.utc)
    isolated_action_history.append(
        ProviderActionAuditEntry(
            id="prune-entry",
            provider_id="ollama",
            provider_name="Ollama",
            action_id="run-diagnostics",
            action_label="Run Diagnostics",
            status="succeeded",
            success=True,
            message="Completed.",
            confirmed=False,
            destructive=False,
            parameter_names=[],
            started_at=timestamp,
            completed_at=timestamp,
            duration_ms=1,
        ),
    )

    unconfirmed = client.post(
        "/api/v1/ops/actions/prune",
        json={"confirmed": False},
    )
    assert unconfirmed.status_code == 409

    monkeypatch.setattr(
        isolated_action_history,
        "_retention_cutoff",
        lambda: timestamp + timedelta(seconds=1),
    )
    confirmed = client.post(
        "/api/v1/ops/actions/prune",
        json={"confirmed": True},
    )

    assert confirmed.status_code == 200
    assert confirmed.json()["deleted_entries"] == 1
    assert confirmed.json()["remaining_entries"] == 0
