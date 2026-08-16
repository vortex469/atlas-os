export type ProviderMonitoringExpectation = "running" | "stopped" | "ignored";

export type ProviderIntentStatus =
    | "configured"
    | "needs_review"
    | "missing"
    | "unsupported"
    | "unavailable";

export type ProviderIntentReason =
    | "legacy_policy_match"
    | "no_legacy_policy"
    | "matching_active_intent"
    | "no_active_intent"
    | "legacy_unbound_evidence"
    | "incarnation_mismatch"
    | "identity_unavailable"
    | "resource_missing"
    | "resource_type_unsupported"
    | "authority_store_unavailable";

export type ProviderIntentMutationReadiness =
    | "ready"
    | "not_activated"
    | "authority_unavailable"
    | "store_migration_required"
    | "store_unavailable"
    | "resource_missing"
    | "identity_unavailable"
    | "resource_type_unsupported";

export type ProviderManagementSection =
    | "connection"
    | "discovery"
    | "resources"
    | "monitoring"
    | "diagnostics"
    | "actions";

export type ProviderManagementSectionDescriptor = {
    section: ProviderManagementSection;
    availability: "available" | "unavailable";
    read_only_descriptor: true;
    grants_permission: false;
    grants_execution: false;
};

export type ProviderResourceManagementSupportV2 = {
    provider_id: string;
    resource_type: string;
    resource_readable: boolean;
    authoritative_identity_supported: boolean;
    provider_intent_capability_supported: boolean;
    provider_intent_mutation_available: false;
    supported_expectations: ProviderMonitoringExpectation[];
    operationally_requestable: false;
    grants_permission: false;
    grants_execution: false;
};

export type ManagedProviderResourceV2 = {
    provider_id: string;
    resource_id: string;
    resource_type: string;
    display_name: string;
    current_state: string;
    missing: boolean;
    identity_assurance: "authoritative" | "unavailable" | "unsupported";
    management_fingerprint: string | null;
    intent_authority: "legacy_policy" | "provider_intent";
    intent_status: ProviderIntentStatus;
    intent_reason: ProviderIntentReason;
    expectation: ProviderMonitoringExpectation | null;
    record_version: number | null;
    legacy_review_available: boolean;
    legacy_expectation: ProviderMonitoringExpectation | null;
    replacement_detected: boolean;
    mutation_available: false;
    operationally_requestable: false;
    grants_execution: false;
};

export type ProviderManagementV2 = {
    schema_version: "provider-management-v2";
    provider_id: string;
    provider_name: string;
    sections: ProviderManagementSectionDescriptor[];
    resource_types: ProviderResourceManagementSupportV2[];
    resources: ManagedProviderResourceV2[];
    provider_intent_activation: "not_activated" | "activated";
    provider_intent_authority_status: "available" | "unavailable";
    grants_permission: false;
    grants_execution: false;
};

export type ManagedProviderResourceV3 = {
    provider_id: string;
    resource_id: string;
    resource_type: string;
    display_name: string;
    current_state: string;
    missing: boolean;
    resource_live: boolean;
    identity_assurance: "authoritative" | "unavailable" | "unsupported";
    management_fingerprint: string | null;
    intent_authority: "legacy_policy" | "provider_intent";
    intent_status: ProviderIntentStatus;
    intent_reason: ProviderIntentReason;
    expectation: ProviderMonitoringExpectation | null;
    record_version: number | null;
    legacy_review_available: boolean;
    legacy_expectation: ProviderMonitoringExpectation | null;
    replacement_detected: boolean;
    provider_intent_mutation_supported: boolean;
    mutation_readiness: ProviderIntentMutationReadiness;
    editable_in_principle: boolean;
    caller_can_mutate: boolean;
    operationally_requestable: false;
    grants_permission: false;
    grants_execution: false;
};

export type ProviderManagementV3 = {
    schema_version: "provider-management-v3";
    provider_id: string;
    provider_name: string;
    sections: ProviderManagementSectionDescriptor[];
    resource_types: Array<{
        provider_id: string;
        resource_type: string;
        resource_readable: boolean;
        authoritative_identity_supported: boolean;
        provider_intent_capability_supported: boolean;
        provider_intent_mutation_supported: boolean;
        supported_expectations: ProviderMonitoringExpectation[];
        operationally_requestable: false;
        grants_permission: false;
        grants_execution: false;
    }>;
    resources: ManagedProviderResourceV3[];
    provider_intent_activation: "not_activated" | "activated";
    provider_intent_authority_status: "available" | "unavailable";
    caller_has_provider_intent_update: boolean;
    grants_permission: false;
    grants_execution: false;
};

export type ProviderIntentMutationRequest = {
    request_id: string;
    expected_management_fingerprint: string;
    expectation: ProviderMonitoringExpectation;
    expected_record_version: number;
    acknowledge_monitoring_suppression: boolean;
};

export type ProviderIntentMutationResult = {
    outcome: "created" | "updated" | "rebound";
    request_id: string;
    provider_id: "proxmox";
    resource_type: "qemu";
    resource_id: string;
    management_fingerprint: string;
    expectation: ProviderMonitoringExpectation;
    record_version: number;
    superseded_previous_incarnation: boolean;
};

export type ProviderMonitoringIntentSuggestionV1 = {
    schema_version: "provider-monitoring-intent-suggestion-v1";
    suggestion_id: `provider-monitoring-intent-suggestion-id-v1:${string}`;
    provider_id: "proxmox";
    resource_type: "qemu";
    resource_id: string;
    management_fingerprint: `provider-management-fingerprint-v1:${string}`;
    suggested_expectation: "running";
    base_record_version: 0;
    source: "provider_intelligence_rule";
    source_rule: "qemu-observed-running-no-active-intent-v1";
    reason: "observed_running_without_active_intent";
    advisory_only: true;
    grants_permission: false;
    grants_execution: false;
};
