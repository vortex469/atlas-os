from app.config.validation import (
    REQUIRED_ENVIRONMENT_VARIABLES,
    validate_environment,
)


def test_environment_validation_accepts_injected_values(
    monkeypatch,
) -> None:
    for variable in REQUIRED_ENVIRONMENT_VARIABLES:
        monkeypatch.setenv(variable, "configured")

    assert validate_environment() == []


def test_environment_validation_reports_missing_values(
    monkeypatch,
) -> None:
    for variable in REQUIRED_ENVIRONMENT_VARIABLES:
        monkeypatch.delenv(variable, raising=False)

    assert validate_environment() == [
        "Missing environment variables: "
        + ", ".join(REQUIRED_ENVIRONMENT_VARIABLES)
    ]
