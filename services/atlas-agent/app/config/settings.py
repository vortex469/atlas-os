"""Runtime settings for Atlas Agent."""

import os
from dataclasses import dataclass
from pathlib import Path

_DEFAULT_REPOSITORY_ROOT = Path(__file__).resolve().parents[4]
_DEFAULT_STATE_DIR = Path(
    os.getenv("XDG_STATE_HOME", str(Path.home() / ".local" / "state"))
) / "atlas-agent"
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
_ALLOWED_EXECUTION_BACKENDS = frozenset({"local", "worker"})


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

def _load_planning_mode() -> str:
    """Load and validate the configured planning mode."""

    planning_mode = os.getenv(
        "ATLAS_AGENT_PLANNING_MODE",
        "deterministic",
    ).strip().lower()

    if planning_mode not in ("deterministic", "model-assisted"):
        supported = "deterministic, model-assisted"
        raise ValueError(
            "ATLAS_AGENT_PLANNING_MODE must be one of: "
            f"{supported}"
        )

    return planning_mode


def _load_review_mode() -> str:
    """Load and validate the configured review mode."""

    review_mode = os.getenv(
        "ATLAS_AGENT_REVIEW_MODE",
        "deterministic",
    ).strip().lower()

    if review_mode not in ("deterministic", "model-assisted"):
        supported = "deterministic, model-assisted"
        raise ValueError(
            "ATLAS_AGENT_REVIEW_MODE must be one of: "
            f"{supported}"
        )

    return review_mode


def _load_execution_backend() -> str:
    """Load the explicitly selected execution backend."""

    backend = os.getenv("ATLAS_EXECUTION_BACKEND", "local").strip().lower()
    if backend not in _ALLOWED_EXECUTION_BACKENDS:
        supported = ", ".join(sorted(_ALLOWED_EXECUTION_BACKENDS))
        raise ValueError(f"ATLAS_EXECUTION_BACKEND must be one of: {supported}")
    return backend


def _load_atlas_core_required() -> bool:
    """Load whether workflows require Atlas Core context."""

    raw_value = os.getenv("ATLAS_CORE_REQUIRED", "false").strip().lower()
    values = {
        "true": True,
        "false": False,
    }
    try:
        return values[raw_value]
    except KeyError as exc:
        raise ValueError(
            "ATLAS_CORE_REQUIRED must be one of: false, true"
        ) from exc


def _load_atlas_core_port() -> int:
    """Load and validate the configured Atlas Core port."""

    raw_port = os.getenv("ATLAS_CORE_PORT", "8643")

    try:
        port = int(raw_port)
    except ValueError as exc:
        raise ValueError(
            "ATLAS_CORE_PORT must be an integer"
        ) from exc

    if not 1 <= port <= 65535:
        raise ValueError(
            "ATLAS_CORE_PORT must be between 1 and 65535"
        )

    return port


def _load_atlas_core_timeout_seconds() -> float:
    """Load and validate the configured Atlas Core timeout."""

    raw_timeout = os.getenv("ATLAS_CORE_TIMEOUT_SECONDS", "10.0")

    try:
        timeout = float(raw_timeout)
    except ValueError as exc:
        raise ValueError(
            "ATLAS_CORE_TIMEOUT_SECONDS must be numeric"
        ) from exc

    if timeout <= 0:
        raise ValueError(
            "ATLAS_CORE_TIMEOUT_SECONDS must be greater than zero"
        )

    return timeout


@dataclass(frozen=True, slots=True)
class Settings:
    """Atlas Agent runtime settings."""

    app_name: str = "Atlas Agent"
    environment: str = "development"
    log_level: str = "INFO"
    host: str = "127.0.0.1"
    port: int = 8090
    repository_root: Path = _DEFAULT_REPOSITORY_ROOT
    state_dir: Path = _DEFAULT_STATE_DIR
    atlas_core_host: str = "127.0.0.1"
    atlas_core_port: int = 8643
    atlas_core_timeout_seconds: float = 10.0
    atlas_core_required: bool = False
    ollama_base_url: str = "http://127.0.0.1:11434"
    ollama_default_model: str = "qwen3-coder-atlas:latest"
    planning_mode: str = "deterministic"
    review_mode: str = "deterministic"
    execution_backend: str = "local"
    execution_worker_repository_token: str = "atlas-repository"
    execution_worker_socket: Path = Path("/run/atlas-execution-worker/worker.sock")

    @classmethod
    def from_environment(cls) -> "Settings":
        """Load validated settings from Atlas Agent environment variables."""

        repository_root = Path(
            os.getenv(
                "ATLAS_AGENT_REPOSITORY_ROOT",
                str(_DEFAULT_REPOSITORY_ROOT),
            )
        ).expanduser().resolve()

        state_dir = Path(
            os.getenv(
                "ATLAS_AGENT_STATE_DIR",
                str(_DEFAULT_STATE_DIR),
            )
        ).expanduser().resolve()

        return cls(
            app_name=os.getenv("ATLAS_AGENT_APP_NAME", "Atlas Agent"),
            environment=_load_environment(),
            log_level=_load_log_level(),
            planning_mode=_load_planning_mode(),
            review_mode=_load_review_mode(),
            execution_backend=_load_execution_backend(),
            execution_worker_repository_token=os.getenv(
                "ATLAS_EXECUTION_WORKER_REPOSITORY_TOKEN",
                "atlas-repository",
            ),
            execution_worker_socket=Path(
                os.getenv(
                    "ATLAS_EXECUTION_WORKER_SOCKET",
                    "/run/atlas-execution-worker/worker.sock",
                )
            ),
            host=os.getenv("ATLAS_AGENT_HOST", "127.0.0.1"),
            port=_load_port(),
            repository_root=repository_root,
            state_dir=state_dir,
            atlas_core_host=os.getenv("ATLAS_CORE_HOST", "127.0.0.1"),
            atlas_core_port=_load_atlas_core_port(),
            atlas_core_timeout_seconds=_load_atlas_core_timeout_seconds(),
            atlas_core_required=_load_atlas_core_required(),
            ollama_base_url=os.getenv(
                "ATLAS_AGENT_OLLAMA_BASE_URL",
                "http://127.0.0.1:11434",
            ),
            ollama_default_model=os.getenv(
                "ATLAS_AGENT_OLLAMA_DEFAULT_MODEL",
                "qwen3-coder-atlas:latest",
            ),
        )


def load_settings() -> Settings:
    """Return the current Atlas Agent settings."""

    return Settings.from_environment()
