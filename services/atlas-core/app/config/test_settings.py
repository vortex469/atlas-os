import pytest
from pydantic import ValidationError

from app.config.settings import IntelligenceSettings, OperatorAuthSettings


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
