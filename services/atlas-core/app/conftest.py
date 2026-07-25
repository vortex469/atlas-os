from collections.abc import Generator
from pathlib import Path

import pytest

from app.actions import history as history_module
from app.actions.history import ProviderActionHistory
from app.intelligence import history as intelligence_history_module
from app.intelligence.history import IntelligenceTelemetryHistory


@pytest.fixture(autouse=True)
def isolated_action_history(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> Generator[ProviderActionHistory, None, None]:
    history = ProviderActionHistory(
        database_path=tmp_path / "action_history.db",
    )
    monkeypatch.setattr(
        history_module,
        "provider_action_history",
        history,
    )

    yield history

    history.close()


@pytest.fixture(autouse=True)
def isolated_intelligence_history(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> Generator[IntelligenceTelemetryHistory, None, None]:
    history = IntelligenceTelemetryHistory(
        database_path=tmp_path / "intelligence_history.db",
    )
    monkeypatch.setattr(
        intelligence_history_module,
        "intelligence_telemetry_history",
        history,
    )

    yield history

    history.close()
