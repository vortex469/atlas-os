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


PolicySeverity = Literal["info", "warning", "critical"]


class OPNsensePolicy(BaseModel):
    pending_update_warning_threshold: int | None = Field(
        default=None,
        ge=1,
    )
    reboot_required_severity: PolicySeverity = "warning"


class FrigateCameraPolicy(BaseModel):
    expected: Literal["active", "inactive"] = "active"
    minimum_camera_fps: float = Field(default=0, ge=0)
    minimum_process_fps: float = Field(default=0, ge=0)


class FrigatePolicy(BaseModel):
    cameras: dict[str, FrigateCameraPolicy] = Field(
        default_factory=dict
    )
    stalled_camera_severity: PolicySeverity = "warning"


class ObsidianPolicy(BaseModel):
    minimum_note_count: int = Field(default=1, ge=0)
    stale_after_days: int | None = Field(default=None, ge=1)
    insufficient_notes_severity: PolicySeverity = "warning"
    stale_severity: PolicySeverity = "info"
    scan_truncated_severity: PolicySeverity = "warning"


class Policies(BaseModel):
    proxmox: ProxmoxPolicy = Field(default_factory=ProxmoxPolicy)
    docker: DockerPolicy = Field(default_factory=DockerPolicy)
    homeassistant: HomeAssistantPolicy = Field(
        default_factory=HomeAssistantPolicy
    )
    opnsense: OPNsensePolicy = Field(
        default_factory=OPNsensePolicy,
    )
    frigate: FrigatePolicy = Field(default_factory=FrigatePolicy)
    obsidian: ObsidianPolicy = Field(
        default_factory=ObsidianPolicy
    )
