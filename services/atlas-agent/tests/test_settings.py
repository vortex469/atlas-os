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
        "ATLAS_AGENT_STATE_DIR",
        "ATLAS_AGENT_OLLAMA_BASE_URL",
        "ATLAS_AGENT_OLLAMA_DEFAULT_MODEL",
        "ATLAS_AGENT_PLANNING_MODE",
        "ATLAS_AGENT_REVIEW_MODE",
        "ATLAS_CORE_REQUIRED",
    ):
        monkeypatch.delenv(variable, raising=False)


def test_settings_use_defaults(monkeypatch) -> None:
    clear_validated_environment(monkeypatch)

    settings = Settings.from_environment()

    assert settings.environment == "development"
    assert settings.log_level == "INFO"
    assert settings.port == 8090
    assert settings.repository_root.is_absolute()
    assert settings.state_dir.is_absolute()
    assert settings.state_dir.name == "atlas-agent"
    assert settings.ollama_base_url == "http://127.0.0.1:11434"
    assert settings.ollama_default_model == "qwen3-coder-atlas:latest"
    assert settings.review_mode == "deterministic"
    assert settings.atlas_core_required is False


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
    state_dir = tmp_path / "state"
    monkeypatch.setenv(
        "ATLAS_AGENT_STATE_DIR",
        str(state_dir),
    )
    monkeypatch.setenv(
        "ATLAS_AGENT_OLLAMA_BASE_URL",
        "http://ollama.example:11434",
    )
    monkeypatch.setenv(
        "ATLAS_AGENT_OLLAMA_DEFAULT_MODEL",
        "test-model:latest",
    )
    monkeypatch.setenv(
        "ATLAS_AGENT_PLANNING_MODE",
        "Model-Assisted",
    )
    monkeypatch.setenv(
        "ATLAS_AGENT_REVIEW_MODE",
        "Model-Assisted",
    )

    settings = Settings.from_environment()

    assert settings.environment == "production"
    assert settings.log_level == "WARNING"
    assert settings.port == 9000
    assert settings.repository_root == repository.resolve()
    assert settings.state_dir == state_dir.resolve()
    assert settings.ollama_base_url == "http://ollama.example:11434"
    assert settings.ollama_default_model == "test-model:latest"
    assert settings.planning_mode == "model-assisted"
    assert settings.review_mode == "model-assisted"

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


def test_settings_reject_invalid_planning_mode(monkeypatch) -> None:
    clear_validated_environment(monkeypatch)
    monkeypatch.setenv(
        "ATLAS_AGENT_PLANNING_MODE",
        "autonomous",
    )

    with pytest.raises(
        ValueError,
        match="ATLAS_AGENT_PLANNING_MODE must be one of:",
    ):
        Settings.from_environment()


def test_settings_reject_invalid_review_mode(monkeypatch) -> None:
    clear_validated_environment(monkeypatch)
    monkeypatch.setenv(
        "ATLAS_AGENT_REVIEW_MODE",
        "autonomous",
    )

    with pytest.raises(
        ValueError,
        match="ATLAS_AGENT_REVIEW_MODE must be one of:",
    ):
        Settings.from_environment()


def test_settings_accept_atlas_core_required(monkeypatch) -> None:
    clear_validated_environment(monkeypatch)
    monkeypatch.setenv("ATLAS_CORE_REQUIRED", "true")

    assert Settings.from_environment().atlas_core_required is True


def test_settings_reject_invalid_atlas_core_required(monkeypatch) -> None:
    clear_validated_environment(monkeypatch)
    monkeypatch.setenv("ATLAS_CORE_REQUIRED", "sometimes")

    with pytest.raises(
        ValueError,
        match="ATLAS_CORE_REQUIRED must be one of: false, true",
    ):
        Settings.from_environment()
