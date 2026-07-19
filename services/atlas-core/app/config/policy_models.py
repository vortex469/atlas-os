from typing import Literal

from pydantic import BaseModel, Field


ExpectedState = Literal["running", "stopped"]


class GuestPolicy(BaseModel):
    expected: ExpectedState


class ProxmoxPolicy(BaseModel):
    guests: dict[str, GuestPolicy] = Field(default_factory=dict)


class ContainerPolicy(BaseModel):
    expected: ExpectedState


class DockerPolicy(BaseModel):
    containers: dict[str, ContainerPolicy] = Field(default_factory=dict)


class HomeAssistantPolicy(BaseModel):
    ignored_entities: list[str] = Field(default_factory=list)


class Policies(BaseModel):
    proxmox: ProxmoxPolicy = Field(default_factory=ProxmoxPolicy)
    docker: DockerPolicy = Field(default_factory=DockerPolicy)
    homeassistant: HomeAssistantPolicy = Field(
        default_factory=HomeAssistantPolicy
    )