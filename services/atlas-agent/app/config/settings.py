"""Runtime settings for Atlas Agent."""

import os
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Settings:
    """Atlas Agent runtime settings."""

    app_name: str = "Atlas Agent"
    environment: str = "development"
    log_level: str = "INFO"
    host: str = "127.0.0.1"
    port: int = 8090

    @classmethod
    def from_environment(cls) -> "Settings":
        """Load settings from Atlas Agent environment variables."""

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
        )


def load_settings() -> Settings:
    """Return the current Atlas Agent settings."""

    return Settings.from_environment()
