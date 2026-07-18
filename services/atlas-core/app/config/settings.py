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


class Settings(BaseModel):
    atlas: AtlasSettings
    infrastructure: InfrastructureSettings
    proxmox: ProxmoxSettings
    home_assistant: HomeAssistantSettings
    docker: DockerSettings
    inventory: InventorySettings


def load_yaml_config() -> dict[str, Any]:
    if not CONFIG_FILE.exists():
        raise RuntimeError(
            f"Atlas configuration file not found: {CONFIG_FILE}"
        )

    with CONFIG_FILE.open("r", encoding="utf-8") as config_file:
        config = yaml.safe_load(config_file)

    if not isinstance(config, dict):
        raise RuntimeError(
            f"Atlas configuration is invalid: {CONFIG_FILE}"
        )

    return config


def load_settings() -> Settings:
    try:
        return Settings.model_validate(load_yaml_config())
    except ValidationError as error:
        raise RuntimeError(
            f"Atlas configuration validation failed:\n{error}"
        ) from error


settings = load_settings()
