import asyncio
from types import SimpleNamespace

import pytest

from app import main


@pytest.mark.parametrize("enabled", [False, True])
def test_application_lifespan_honors_dynamic_discovery_activation(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
    enabled: bool,
) -> None:
    events: list[str] = []

    class FakeActivation:
        @classmethod
        async def start(cls):
            events.append("dynamic-start")
            return cls()

        async def aclose(self) -> None:
            events.append("dynamic-close")

    class FakeLedger:
        def __init__(self, database) -> None:
            pass

        def reconcile_startup(self):
            return SimpleNamespace()

    class FakeLifecycle:
        def __init__(self, **kwargs) -> None:
            pass

        def schedule_startup_recovery(self) -> bool:
            return False

        async def close(self) -> None:
            events.append("lifecycle-close")

    settings = SimpleNamespace(
        dynamic_discovery=SimpleNamespace(enabled=enabled),
        provider_intents=SimpleNamespace(),
            operator_auth=SimpleNamespace(
                enabled=False,
                intent_database=str(tmp_path / "intents.db"),
                installation_selection_database=str(tmp_path / "selections.db"),
                installation_candidate_record_database=str(tmp_path / "candidates.db"),
                installation_approval_intent_database=str(
                    tmp_path / "approval-intents.db"
                ),
                trusted_origins=(),
            ),
        operational_dispatch=SimpleNamespace(
            database=str(tmp_path / "dispatch.db"),
            agent_auth_file=str(tmp_path / "agent-token"),
        ),
    )
    monkeypatch.setattr(main, "settings", settings)
    monkeypatch.setattr(main, "DynamicDiscoveryActivation", FakeActivation)
    monkeypatch.setattr(main, "assert_restore_state_clean", lambda path: None)
    monkeypatch.setattr(main, "validate_configuration", lambda: None)
    monkeypatch.setattr(main, "validate_provider_intent_activation", lambda value: object())
    monkeypatch.setattr(main, "configure_monitoring_intent_authority", lambda *args: object())
    monkeypatch.setattr(main, "development_fixture_enabled_and_validated", lambda: False)
    monkeypatch.setattr(main, "OperatorIntentStore", lambda path: object())
    monkeypatch.setattr(main, "load_provider_registry", lambda: None)
    monkeypatch.setattr(main.provider_registry, "get", lambda provider_id: None)
    monkeypatch.setattr(main, "OperationalDispatchLedger", FakeLedger)
    monkeypatch.setattr(main, "OperationalDispatchAuthenticator", lambda path: object())
    monkeypatch.setattr(main, "OperationalDispatchService", lambda **kwargs: object())
    monkeypatch.setattr(main, "OperationalLifecycleService", FakeLifecycle)

    async def exercise() -> None:
        async with main.lifespan(main.app):
            events.append("serving")

    asyncio.run(exercise())

    if enabled:
        assert events == ["dynamic-start", "serving", "dynamic-close", "lifecycle-close"]
    else:
        assert events == ["serving", "lifecycle-close"]
