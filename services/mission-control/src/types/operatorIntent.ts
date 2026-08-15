import type { ExecutionCandidate } from "./executionCandidates";

export type OperatorIntentResourceReason =
    | "identity_unavailable"
    | "unsupported_resource_type"
    | "stopped"
    | "template"
    | "locked"
    | "migrating"
    | "unavailable_state";

export type OperatorIntentResource = {
    provider_id: string;
    resource_id: string;
    resource_type: string;
    display_name: string;
    node: string;
    current_state: string;
    authoritative_identity_present: boolean;
    template: boolean;
    locked: boolean;
    migrating: boolean;
    operational_target_fingerprint: string | null;
    requestable: boolean;
    reason: OperatorIntentResourceReason | null;
};

export type OperatorIntentResourceCollection = {
    execution_intent: "restart-service";
    provider_id: "proxmox";
    resource_type: "qemu";
    generated_at: string;
    resources: OperatorIntentResource[];
};

export type OperationalCapabilityDescriptor = {
    capability_id: string;
    execution_intent: "restart-service";
    provider_id: "proxmox";
    resource_type: "qemu";
    effect_kind: "operational_action";
    required_approval_level: string;
    selector_available: boolean;
    selector_kind: "authoritative_resource";
    selector_id: string;
    disruption_kind: string;
    verification_kind: string;
    core_gate_enabled: boolean;
    handler_registered: boolean;
    production_enabled: boolean;
    consistency: "consistent" | "mismatch";
    label: string;
    description: string;
};

export type OperationalCapabilityCollection = {
    capabilities: OperationalCapabilityDescriptor[];
};

export type OperatorIntentCreationResponse = {
    outcome: "created" | "reused";
    candidate_id: string;
    candidate: ExecutionCandidate;
};
