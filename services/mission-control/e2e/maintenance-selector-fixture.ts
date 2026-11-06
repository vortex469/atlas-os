import type { OperationalCapabilityDescriptor, OperatorIntentResource } from "../src/types/operatorIntent";

export const capability: OperationalCapabilityDescriptor = {
    capability_id: "restart-service--proxmox--qemu", execution_intent: "restart-service",
    provider_id: "proxmox", resource_type: "qemu", effect_kind: "operational_action",
    required_approval_level: "standard", selector_available: true,
    selector_kind: "authoritative_resource", selector_id: "restart-service--proxmox--qemu",
    disruption_kind: "brief_service_interruption", verification_kind: "authoritative_state_and_health",
    core_gate_enabled: true, handler_registered: true, production_enabled: true,
    consistency: "consistent", label: "Restart service", description: "Graceful restart.",
};
export const resource: OperatorIntentResource = {
    provider_id: "proxmox", resource_id: "110", resource_type: "qemu",
    display_name: "Browser fixture VM", node: "fixture-node", current_state: "running",
    authoritative_identity_present: true, template: false, locked: false, migrating: false,
    operational_target_fingerprint: `operational-target-fingerprint-v1:${"a".repeat(64)}`,
    requestable: true, reason: null,
};

