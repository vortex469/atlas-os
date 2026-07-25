import pytest
from pydantic import ValidationError

from app.config.settings import IntelligenceSettings


def test_provider_intelligence_timeout_defaults_to_ten_seconds() -> None:
    settings = IntelligenceSettings()

    assert settings.provider_timeout_seconds == 10


@pytest.mark.parametrize("timeout", [0, 61])
def test_provider_intelligence_timeout_is_bounded(
    timeout: float,
) -> None:
    with pytest.raises(ValidationError):
        IntelligenceSettings(
            provider_timeout_seconds=timeout,
        )
