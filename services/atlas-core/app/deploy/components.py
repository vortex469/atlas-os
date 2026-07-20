from typing import Any

from pydantic import BaseModel, Field, field_validator

from app.deploy.enums import ComponentKind


class PortBinding(BaseModel):
    """A network port exposed or consumed by a component."""

    container_port: int = Field(ge=1, le=65535)
    host_port: int | None = Field(default=None, ge=1, le=65535)
    protocol: str = "tcp"
    public: bool = False

    @field_validator("protocol")
    @classmethod
    def validate_protocol(cls, value: str) -> str:
        normalized = value.lower()

        if normalized not in {"tcp", "udp"}:
            raise ValueError("protocol must be either 'tcp' or 'udp'")

        return normalized


class StorageMount(BaseModel):
    """Persistent or temporary storage requested by a component."""

    source: str | None = None
    target: str
    read_only: bool = False
    persistent: bool = True


class ApplicationComponent(BaseModel):
    """A provider-independent component of an application."""

    id: str = Field(
        min_length=1,
        pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$",
    )
    name: str = Field(min_length=1)
    kind: ComponentKind = ComponentKind.SERVICE
    image: str | None = None
    version: str | None = None
    command: list[str] = Field(default_factory=list)
    ports: list[PortBinding] = Field(default_factory=list)
    storage: list[StorageMount] = Field(default_factory=list)
    environment: dict[str, str] = Field(default_factory=dict)
    dependencies: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
