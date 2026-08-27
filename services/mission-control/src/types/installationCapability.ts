import type { InstallationDestinationSelectionV1, ProspectiveInstallationDestinationV1 } from "./installationDestination";
import type { InstallationPlan } from "./installationPlan";

export type InstallationCapabilityResult = "satisfied" | "not_satisfied" | "unknown" | "not_assessable";
export type ProviderCapabilityFactState = "observed" | "not_observed" | "malformed" | "conflicted" | "unavailable";
export type ProviderCapabilityFactCode =
    | "current_destination_identity" | "current_lifecycle_state" | "configured_cpu_cores"
    | "configured_memory_bytes" | "configured_disk_capacity_bytes" | "guest_agent_configured";
export type InstallationCapabilityReasonCode =
    | "installation_plan_blocked" | "destination_selection_not_current"
    | "destination_identity_not_current" | "provider_facts_not_current"
    | "provider_facts_unknown" | "requirement_not_assessable"
    | "requirement_not_satisfied" | "agent_install_container_unsupported";

export type ProviderCapabilityFactV1 = {
    code: ProviderCapabilityFactCode;
    state: ProviderCapabilityFactState;
    value: boolean | number | "running" | "stopped" | "unknown" | null;
    source: "proxmox-qemu-control-plane";
    observed_at: string;
    destination_fingerprint: string;
};

export type InstallationCapabilityAssessmentV1 = {
    schema_version: "installation-capability-assessment-v1";
    plan: InstallationPlan;
    selection: InstallationDestinationSelectionV1;
    current_destination: ProspectiveInstallationDestinationV1;
    provider_facts: {
        schema_version: "provider-installation-capability-facts-v1";
        provider: "proxmox";
        resource_type: "qemu";
        placement_kind: "existing-guest";
        resource_id: string;
        destination_fingerprint: string;
        observed_at: string;
        fresh_until: string;
        facts: ProviderCapabilityFactV1[];
    };
    comparisons: Array<{
        prerequisite_id: string;
        prerequisite_kind: "storage" | "network" | "platform" | "application" | "operator";
        requirement_kind: "cpu_cores" | "memory" | "storage" | "unsupported";
        requirement: string;
        fact_code: "configured_cpu_cores" | "configured_memory_bytes" | "configured_disk_capacity_bytes" | null;
        fact_state: ProviderCapabilityFactState | null;
        observed_value: number | null;
        result: InstallationCapabilityResult;
    }>;
    assessment_status: "blocked" | "insufficient_provider_facts" | "requirements_satisfied_but_non_authorizing";
    reason_codes: InstallationCapabilityReasonCode[];
    evaluated_at: string;
    candidate_eligibility_evaluated: false;
    candidate_creation_allowed: false;
    agent_execution_supported: false;
    provider_mutation_allowed: false;
    assessment_fingerprint: string;
};
