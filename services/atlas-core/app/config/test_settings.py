import pytest
from pydantic import ValidationError

import app.config.settings as settings_module
from app.config.settings import (
    DynamicDiscoverySettings,
    IntelligenceSettings,
    OperatorAuthSettings,
    ProviderIntentActivation,
    ProviderIntentSettings,
    load_settings,
)

IMPORT_ID = "provider-intent-legacy-policy-import-v1:" + "a" * 64


def test_provider_intelligence_timeout_defaults_to_ten_seconds() -> None:
    settings = IntelligenceSettings()

    assert settings.provider_timeout_seconds == 10
    assert settings.telemetry_max_entries == 10_000
    assert settings.telemetry_retention_days == 30


@pytest.mark.parametrize("timeout", [0, 61])
def test_provider_intelligence_timeout_is_bounded(
    timeout: float,
) -> None:
    with pytest.raises(ValidationError):
        IntelligenceSettings(
            provider_timeout_seconds=timeout,
        )


@pytest.mark.parametrize(
    "overrides",
    [
        {"telemetry_max_entries": 0},
        {"telemetry_retention_days": 0},
    ],
)
def test_provider_intelligence_history_is_bounded(
    overrides: dict,
) -> None:
    with pytest.raises(ValidationError):
        IntelligenceSettings(**overrides)


def test_operator_auth_is_disabled_safely_by_default() -> None:
    assert OperatorAuthSettings().enabled is False
    assert OperatorAuthSettings().trusted_origins == ()
    assert OperatorAuthSettings().installation_selection_database == (
        "/opt/atlas/data/installation_destination_selections.db"
    )


@pytest.mark.parametrize("database", [":memory:", "relative/selections.db", ""])
def test_installation_selection_database_requires_durable_absolute_path(
    database: str,
) -> None:
    with pytest.raises(ValidationError, match="absolute"):
        OperatorAuthSettings(installation_selection_database=database)


def test_dynamic_discovery_refresh_is_disabled_safely_by_default() -> None:
    assert DynamicDiscoverySettings().enabled is False


@pytest.mark.parametrize("value", ["1", "true", "yes", "on", "TRUE"])
def test_dynamic_discovery_refresh_environment_is_explicitly_opt_in(
    monkeypatch: pytest.MonkeyPatch,
    value: str,
) -> None:
    monkeypatch.setattr(
        settings_module,
        "load_yaml_config",
        lambda: {
            "atlas": {"release": "test"},
            "infrastructure": {},
            "proxmox": {"host": "test", "node": "test"},
            "home_assistant": {"url": "http://test"},
            "docker": {},
            "inventory": {"file": "/tmp/inventory.yaml"},
        },
    )
    monkeypatch.setenv("ATLAS_ENABLE_DISCOVERY_DYNAMIC_REFRESH", value)

    assert load_settings().dynamic_discovery.enabled is True


def test_enabled_operator_auth_requires_exact_https_origin() -> None:
    with pytest.raises(ValidationError):
        OperatorAuthSettings(enabled=True)
    for origin in (
        "http://atlas.test",
        "https://*.atlas.test",
        "https://atlas.test/path",
        "https://user@atlas.test",
    ):
        with pytest.raises(ValidationError):
            OperatorAuthSettings(enabled=True, trusted_origins=(origin,))
    configured = OperatorAuthSettings(
        enabled=True,
        trusted_origins=("https://atlas.test/",),
    )
    assert configured.trusted_origins == ("https://atlas.test",)


def test_provider_intent_activation_is_closed_and_inactive_by_default() -> None:
    configured = ProviderIntentSettings()
    assert configured.activation is ProviderIntentActivation.NOT_ACTIVATED
    assert configured.database == "/opt/atlas/data/provider_intents.db"
    assert configured.expected_legacy_import_id is None
    with pytest.raises(ValidationError):
        ProviderIntentSettings(activation="shadow")


def test_provider_intent_activation_configuration_invariants() -> None:
    with pytest.raises(ValidationError, match="cannot expect"):
        ProviderIntentSettings(expected_legacy_import_id=IMPORT_ID)
    with pytest.raises(ValidationError, match="requires"):
        ProviderIntentSettings(activation=ProviderIntentActivation.ACTIVATED)
    with pytest.raises(ValidationError, match="absolute"):
        ProviderIntentSettings(database="relative/provider_intents.db")
    activated = ProviderIntentSettings(
        activation=ProviderIntentActivation.ACTIVATED,
        database="/tmp/provider_intents.db",
        expected_legacy_import_id=IMPORT_ID,
    )
    assert activated.activation is ProviderIntentActivation.ACTIVATED


def test_empty_provider_intent_activation_environment_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        settings_module,
        "load_yaml_config",
        lambda: {
            "atlas": {"release": "test"},
            "infrastructure": {},
            "proxmox": {"host": "test", "node": "test"},
            "home_assistant": {"url": "http://test"},
            "docker": {},
            "inventory": {"file": "/tmp/inventory.yaml"},
        },
    )
    monkeypatch.setenv("ATLAS_PROVIDER_INTENT_ACTIVATION", "")
    monkeypatch.delenv("ATLAS_PROVIDER_INTENT_DATABASE", raising=False)
    monkeypatch.delenv(
        "ATLAS_PROVIDER_INTENT_EXPECTED_LEGACY_IMPORT_ID", raising=False
    )

    with pytest.raises(RuntimeError, match="configuration validation failed"):
        load_settings()
