"""Runtime settings for Atlas Agent."""

import os
from dataclasses import dataclass
from pathlib import Path

_DEFAULT_REPOSITORY_ROOT = Path(__file__).resolve().parents[4]
_ALLOWED_ENVIRONMENTS = frozenset(
    {
        "development",
        "testing",
        "production",
    }
)
_ALLOWED_LOG_LEVELS = frozenset(
    {
        "DEBUG",
        "INFO",
        "WARNING",
        "ERROR",
        "CRITICAL",
    }
)


def _load_port() -> int:
    """Load and validate the configured service port."""

    raw_port = os.getenv("ATLAS_AGENT_PORT", "8090")

    try:
        port = int(raw_port)
    except ValueError as exc:
        raise ValueError(
            "ATLAS_AGENT_PORT must be an integer"
        ) from exc

    if not 1 <= port <= 65535:
        raise ValueError(
            "ATLAS_AGENT_PORT must be between 1 and 65535"
        )

    return port


def _load_environment() -> str:
    """Load and validate the configured runtime environment."""

    environment = os.getenv(
        "ATLAS_AGENT_ENVIRONMENT",
        "development",
    ).strip().lower()

    if environment not in _ALLOWED_ENVIRONMENTS:
        supported = ", ".join(sorted(_ALLOWED_ENVIRONMENTS))
        raise ValueError(
            "ATLAS_AGENT_ENVIRONMENT must be one of: "
            f"{supported}"
        )

    return environment


def _load_log_level() -> str:
    """Load and validate the configured logging level."""

    log_level = os.getenv(
        "ATLAS_AGENT_LOG_LEVEL",
        "INFO",
    ).strip().upper()

    if log_level not in _ALLOWED_LOG_LEVELS:
        supported = ", ".join(sorted(_ALLOWED_LOG_LEVELS))
        raise ValueError(
            "ATLAS_AGENT_LOG_LEVEL must be one of: "
            f"{supported}"
        )

    return log_level


@dataclass(frozen=True, slots=True)
class Settings:
    """Atlas Agent runtime settings."""

    app_name: str = "Atlas Agent"
    environment: str = "development"
    log_level: str = "INFO"
    host: str = "127.0.0.1"
    port: int = 8090
    repository_root: Path = _DEFAULT_REPOSITORY_ROOT
    atlas_core_host: str = "127.0.0.1"
    atlas_core_port: int = 8643
    atlas_core_timeout_seconds: float = 10.0

    @classmethod
    def from_environment(cls) -> "Settings":
        """Load validated settings from Atlas Agent environment variables."""

        repository_root = Path(
            os.getenv(
                "ATLAS_AGENT_REPOSITORY_ROOT",
                str(_DEFAULT_REPOSITORY_ROOT),
            )
        ).expanduser().resolve()

        return cls(
            app_name=os.getenv("ATLAS_AGENT_APP_NAME", "Atlas Agent"),
            environment=_load_environment(),
            log_level=_load_log_level(),
            host=os.getenv("ATLAS_AGENT_HOST", "127.0.0.1"),
            port=_load_port(),
            repository_root=repository_root,
            atlas_core_host=os.getenv("ATLAS_CORE_HOST", "127.0.0.1"),
            atlas_core_port=int(os.getenv("ATLAS_CORE_PORT", "8643")),
            atlas_core_timeout_seconds=float(os.getenv("ATLAS_CORE_TIMEOUT_SECONDS", "10.0")),
        )


def load_settings() -> Settings:
    """Return the current Atlas Agent settings."""

    return Settings.from_environment()
