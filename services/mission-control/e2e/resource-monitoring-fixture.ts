import type { ProviderManagementV2 } from "../src/types/providerManagement";

export const resource = {
    provider_id: "proxmox", resource_id: "110", resource_type: "qemu",
    display_name: "security-camera-archive-with-a-long-unbroken-resource-name",
    current_state: "running", missing: false,
};
export const management: ProviderManagementV2 = {
    schema_version: "provider-management-v2", provider_id: "proxmox", provider_name: "Proxmox",
    sections: (["connection", "discovery", "resources", "monitoring", "diagnostics", "actions"] as const).map(section => ({
        section, availability: "available", read_only_descriptor: true, grants_permission: false, grants_execution: false,
    })),
    resource_types: [], provider_intent_activation: "activated", provider_intent_authority_status: "available",
    grants_permission: false, grants_execution: false,
    resources: [{ ...resource, identity_assurance: "authoritative",
        management_fingerprint: `provider-management-fingerprint-v1:${"a".repeat(64)}`,
        intent_authority: "provider_intent", intent_status: "needs_review", intent_reason: "no_active_intent",
        expectation: null, record_version: null, legacy_review_available: false, legacy_expectation: null,
        replacement_detected: false, mutation_available: false, operationally_requestable: false, grants_execution: false }],
};

export function operatorManagement(state: ProviderManagementV2 = management) {
    return { ...state, schema_version: "provider-management-v3", caller_has_provider_intent_update: true,
        resources: state.resources.map(resource => {
            const { mutation_available, ...facts } = resource;
            void mutation_available;
            return { ...facts, resource_live: !resource.missing, provider_intent_mutation_supported: true,
                mutation_readiness: "ready", editable_in_principle: true, caller_can_mutate: true };
        }),
    };
}
