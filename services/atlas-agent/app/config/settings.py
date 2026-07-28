"""Runtime settings for Atlas Agent."""

import os
from dataclasses import dataclass
from pathlib import Path

_DEFAULT_REPOSITORY_ROOT = Path(__file__).resolve().parents[4]


@dataclass(frozen=True, slots=True)
class Settings:
    """Atlas Agent runtime settings."""

    app_name: str = "Atlas Agent"
    environment: str = "development"
    log_level: str = "INFO"
    host: str = "127.0.0.1"
    port: int = 8090
    repository_root: Path = _DEFAULT_REPOSITORY_ROOT

    @classmethod
    def from_environment(cls) -> "Settings":
        """Load settings from Atlas Agent environment variables."""

        repository_root = Path(
            os.getenv(
                "ATLAS_AGENT_REPOSITORY_ROOT",
                str(_DEFAULT_REPOSITORY_ROOT),
            )
        ).expanduser().resolve()

        return cls(
            app_name=os.getenv("ATLAS_AGENT_APP_NAME", "Atlas Agent"),
            environment=os.getenv(
                "ATLAS_AGENT_ENVIRONMENT",
                "development",
            ),
            log_level=os.getenv(
                "ATLAS_AGENT_LOG_LEVEL",
                "INFO",
            ),
            host=os.getenv("ATLAS_AGENT_HOST", "127.0.0.1"),
            port=int(os.getenv("ATLAS_AGENT_PORT", "8090")),
            repository_root=repository_root,
        )


def load_settings() -> Settings:
    """Return the current Atlas Agent settings."""

    return Settings.from_environment()
