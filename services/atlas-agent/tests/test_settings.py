"""Tests for Atlas Agent runtime configuration."""

from pathlib import Path

import pytest

from app.config.settings import Settings


def clear_validated_environment(monkeypatch) -> None:
    """Remove environment variables covered by settings validation."""

    for variable in (
        "ATLAS_AGENT_ENVIRONMENT",
        "ATLAS_AGENT_LOG_LEVEL",
        "ATLAS_AGENT_PORT",
        "ATLAS_AGENT_REPOSITORY_ROOT",
    ):
        monkeypatch.delenv(variable, raising=False)


def test_settings_use_defaults(monkeypatch) -> None:
    clear_validated_environment(monkeypatch)

    settings = Settings.from_environment()

    assert settings.environment == "development"
    assert settings.log_level == "INFO"
    assert settings.port == 8090
    assert settings.repository_root.is_absolute()


def test_settings_accept_valid_environment_overrides(
    tmp_path: Path,
    monkeypatch,
) -> None:
    repository = tmp_path / "repository"
    repository.mkdir()

    monkeypatch.setenv("ATLAS_AGENT_ENVIRONMENT", "Production")
    monkeypatch.setenv("ATLAS_AGENT_LOG_LEVEL", "warning")
    monkeypatch.setenv("ATLAS_AGENT_PORT", "9000")
    monkeypatch.setenv(
        "ATLAS_AGENT_REPOSITORY_ROOT",
        str(repository),
    )

    settings = Settings.from_environment()

    assert settings.environment == "production"
    assert settings.log_level == "WARNING"
    assert settings.port == 9000
    assert settings.repository_root == repository.resolve()


def test_settings_reject_non_integer_port(monkeypatch) -> None:
    clear_validated_environment(monkeypatch)
    monkeypatch.setenv("ATLAS_AGENT_PORT", "not-a-port")

    with pytest.raises(
        ValueError,
        match="ATLAS_AGENT_PORT must be an integer",
    ):
        Settings.from_environment()


@pytest.mark.parametrize("port", ["0", "65536", "-1"])
def test_settings_reject_out_of_range_port(
    port: str,
    monkeypatch,
) -> None:
    clear_validated_environment(monkeypatch)
    monkeypatch.setenv("ATLAS_AGENT_PORT", port)

    with pytest.raises(
        ValueError,
        match="ATLAS_AGENT_PORT must be between 1 and 65535",
    ):
        Settings.from_environment()


def test_settings_reject_invalid_log_level(monkeypatch) -> None:
    clear_validated_environment(monkeypatch)
    monkeypatch.setenv("ATLAS_AGENT_LOG_LEVEL", "VERBOSE")

    with pytest.raises(
        ValueError,
        match="ATLAS_AGENT_LOG_LEVEL must be one of:",
    ):
        Settings.from_environment()


def test_settings_reject_invalid_environment(monkeypatch) -> None:
    clear_validated_environment(monkeypatch)
    monkeypatch.setenv("ATLAS_AGENT_ENVIRONMENT", "staging")

    with pytest.raises(
        ValueError,
        match="ATLAS_AGENT_ENVIRONMENT must be one of:",
    ):
        Settings.from_environment()
