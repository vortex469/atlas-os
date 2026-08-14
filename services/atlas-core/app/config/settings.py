import os
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv
from pydantic import BaseModel, Field, ValidationError

ATLAS_ROOT = Path("/opt/atlas")
CONFIG_FILE = ATLAS_ROOT / "config" / "atlas.yaml"
ENV_FILE = ATLAS_ROOT / ".env"

load_dotenv(ENV_FILE)


class AtlasSettings(BaseModel):
    name: str = "Atlas OS"
    release: str
    assistant: str = "Orion"
    host: str = "0.0.0.0"
    port: int = Field(default=8643, ge=1, le=65535)


class InfrastructureSettings(BaseModel):
    domain: str = "home.arpa"


class ProxmoxSettings(BaseModel):
    host: str
    port: int = Field(default=8006, ge=1, le=65535)
    node: str
    verify_ssl: bool = False


class HomeAssistantSettings(BaseModel):
    url: str


class DockerSettings(BaseModel):
    socket: str = "unix:///var/run/docker.sock"


class InventorySettings(BaseModel):
    file: str


class AuditSettings(BaseModel):
    database: str = "/opt/atlas/data/action_history.db"
    max_entries: int = Field(default=5000, ge=1)
    retention_days: int = Field(default=90, ge=1)


class IntelligenceSettings(BaseModel):
    provider_timeout_seconds: float = Field(
        default=10.0,
        gt=0,
        le=60,
    )
    telemetry_database: str = (
        "/opt/atlas/data/provider_intelligence.db"
    )
    telemetry_max_entries: int = Field(default=10_000, ge=1)
    telemetry_retention_days: int = Field(default=30, ge=1)


class OperationalDispatchSettings(BaseModel):
    database: str = "/opt/atlas/data/operational_dispatch.db"
    agent_auth_file: str = "/run/atlas-core-agent-auth/token"


class Settings(BaseModel):
    atlas: AtlasSettings
    infrastructure: InfrastructureSettings
    proxmox: ProxmoxSettings
    home_assistant: HomeAssistantSettings
    docker: DockerSettings
    inventory: InventorySettings
    audit: AuditSettings = Field(default_factory=AuditSettings)
    intelligence: IntelligenceSettings = Field(
        default_factory=IntelligenceSettings,
    )
    operational_dispatch: OperationalDispatchSettings = Field(
        default_factory=OperationalDispatchSettings,
    )


def load_yaml_config() -> dict[str, Any]:
    if not CONFIG_FILE.exists():
        raise RuntimeError(
            f"Atlas configuration file not found: {CONFIG_FILE}"
        )

    with CONFIG_FILE.open("r", encoding="utf-8") as config_file:
        config = yaml.safe_load(config_file)

    if not isinstance(config, dict):
        raise RuntimeError(  # noqa: TRY004 - preserve configuration error contract
            f"Atlas configuration is invalid: {CONFIG_FILE}"
        )

    return config


def load_settings() -> Settings:
    try:
        loaded = Settings.model_validate(load_yaml_config())
        auth_file = os.getenv("ATLAS_OPERATIONAL_DISPATCH_AUTH_FILE")
        if auth_file:
            loaded = loaded.model_copy(
                update={
                    "operational_dispatch": loaded.operational_dispatch.model_copy(
                        update={"agent_auth_file": auth_file}
                    )
                }
            )
        return loaded
    except ValidationError as error:
        raise RuntimeError(
            f"Atlas configuration validation failed:\n{error}"
        ) from error


settings = load_settings()
