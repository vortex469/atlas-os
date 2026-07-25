from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator


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


class QdrantPolicy(BaseModel):
    expected_collections: list[str] = Field(default_factory=list)
    missing_collection_severity: PolicySeverity = "warning"
    empty_instance_severity: PolicySeverity = "info"

    @field_validator("expected_collections")
    @classmethod
    def validate_expected_collections(
        cls,
        values: list[str],
    ) -> list[str]:
        if any(not value for value in values):
            raise ValueError(
                "expected_collections must contain non-empty names."
            )
        if len(set(values)) != len(values):
            raise ValueError(
                "expected_collections must not contain duplicates."
            )
        return values


class N8nPolicy(BaseModel):
    expected_active_workflows: list[str] = Field(
        default_factory=list
    )
    inactive_workflow_severity: PolicySeverity = "warning"
    scan_truncated_severity: PolicySeverity = "warning"
    empty_instance_severity: PolicySeverity = "info"

    @field_validator("expected_active_workflows")
    @classmethod
    def validate_expected_active_workflows(
        cls,
        values: list[str],
    ) -> list[str]:
        if any(not value for value in values):
            raise ValueError(
                "expected_active_workflows must contain "
                "non-empty names."
            )
        if len(set(values)) != len(values):
            raise ValueError(
                "expected_active_workflows must not contain "
                "duplicates."
            )
        return values


class ProviderPerformancePolicy(BaseModel):
    maximum_collection_duration_ms: float = Field(gt=0)
    severity: PolicySeverity = "warning"


class IntelligencePolicy(BaseModel):
    providers: dict[str, ProviderPerformancePolicy] = Field(
        default_factory=dict
    )


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
    qdrant: QdrantPolicy = Field(default_factory=QdrantPolicy)
    n8n: N8nPolicy = Field(default_factory=N8nPolicy)
    intelligence: IntelligencePolicy = Field(
        default_factory=IntelligencePolicy
    )


class PolicyReloadHealth(BaseModel):
    status: Literal["healthy", "degraded"]
    source_exists: bool
    checked_at: datetime
    loaded_at: datetime | None = None
    duration_ms: float = Field(ge=0)
    error: str | None = None
    diagnostics: list["PolicyValidationDiagnostic"] = Field(
        default_factory=list
    )


class PolicyValidationDiagnostic(BaseModel):
    path: str
    error_type: str
    message: str
    line: int | None = Field(default=None, ge=1)
    column: int | None = Field(default=None, ge=1)
