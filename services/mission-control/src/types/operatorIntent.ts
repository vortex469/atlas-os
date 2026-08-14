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

export type OperatorIntentCreationResponse = {
    outcome: "created" | "reused";
    candidate_id: string;
    candidate: ExecutionCandidate;
};
