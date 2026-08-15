"""Sanitized read-only descriptors projected from closed Core capability sources."""

from enum import StrEnum

from pydantic import BaseModel, ConfigDict

from app.operational_dispatch.service import OperationalDispatchService

RESTART_PROXMOX_QEMU_CAPABILITY_ID = "restart-service--proxmox--qemu"


class OperationalSelectorKind(StrEnum):
    AUTHORITATIVE_RESOURCE = "authoritative_resource"


class OperationalCapabilityConsistency(StrEnum):
    CONSISTENT = "consistent"
    MISMATCH = "mismatch"


class OperationalCapabilityDescriptor(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    capability_id: str
    execution_intent: str
    provider_id: str
    resource_type: str
    effect_kind: str
    required_approval_level: str
    selector_available: bool
    selector_kind: OperationalSelectorKind
    selector_id: str
    disruption_kind: str
    verification_kind: str
    core_gate_enabled: bool
    handler_registered: bool
    production_enabled: bool
    consistency: OperationalCapabilityConsistency
    label: str
    description: str


class OperationalCapabilityCollection(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    capabilities: tuple[OperationalCapabilityDescriptor, ...]


def project_operational_capabilities(
    service: OperationalDispatchService,
) -> OperationalCapabilityCollection:
    """Project the one closed production tuple from independent Core facts."""

    core_gate, handler = service.capability_boundary(
        "restart-service", "proxmox", "qemu"
    )
    consistent = core_gate == handler
    descriptor = OperationalCapabilityDescriptor(
        capability_id=RESTART_PROXMOX_QEMU_CAPABILITY_ID,
        execution_intent="restart-service",
        provider_id="proxmox",
        resource_type="qemu",
        effect_kind="operational_action",
        required_approval_level="standard",
        selector_available=True,
        selector_kind=OperationalSelectorKind.AUTHORITATIVE_RESOURCE,
        selector_id=RESTART_PROXMOX_QEMU_CAPABILITY_ID,
        disruption_kind="brief_service_interruption",
        verification_kind="authoritative_state_and_health",
        core_gate_enabled=core_gate,
        handler_registered=handler,
        production_enabled=core_gate and handler,
        consistency=(
            OperationalCapabilityConsistency.CONSISTENT
            if consistent
            else OperationalCapabilityConsistency.MISMATCH
        ),
        label="Restart service",
        description="Gracefully restart one authoritative Proxmox QEMU resource after exact approval.",
    )
    return OperationalCapabilityCollection(capabilities=(descriptor,))
