export type ProspectiveInstallationDestinationV1 = {
    schema_version: "prospective-installation-destination-v1";
    provider: "proxmox";
    resource_type: "qemu";
    placement_kind: "existing-guest";
    resource_id: string;
    destination_fingerprint: string;
    enumeration_token: string;
};

export type InstallationDestinationSelectionV1 = {
    schema_version: "installation-destination-selection-v1";
    selection_id: string;
    provider: "proxmox";
    resource_type: "qemu";
    placement_kind: "existing-guest";
    resource_id: string;
    selected_destination_fingerprint: string;
    selected_at: string;
    expires_at: string;
    selected_by: string;
    request_digest: string;
    selection_fingerprint: string;
    status: "active" | "cancelled" | "expired" | "stale";
    terminated_at: string | null;
};

export type InstallationAdmissionReasonCode =
    | "installation_plan_conflicted"
    | "installation_plan_missing_deployment_artifact"
    | "installation_plan_incompatible"
    | "installation_plan_stale_evidence"
    | "installation_plan_insufficient_information"
    | "destination_selection_missing"
    | "destination_selection_expired"
    | "destination_unavailable"
    | "destination_identity_unavailable"
    | "destination_replaced_or_moved"
    | "destination_installation_capability_unknown"
    | "installation_interest_missing"
    | "installation_interest_expired"
    | "installation_interest_plan_stale"
    | "installation_interest_destination_stale"
    | "agent_install_container_unsupported";

export type InstallationAdmissionAssessmentV1 = {
    schema_version: "installation-admission-assessment-v1";
    item_id: string;
    catalog_entry_id: string;
    plan_fingerprint: string;
    selection_id: string | null;
    selected_destination_fingerprint: string | null;
    current_destination_fingerprint: string | null;
    interest_fingerprint: string | null;
    assessment_status: "blocked" | "preconditions_satisfied_but_unsupported";
    reason_codes: InstallationAdmissionReasonCode[];
    candidate_eligibility_evaluated: false;
    assessment_fingerprint: string;
};

export type ProspectiveInstallationDestinationCollectionV1 = {
    destinations: ProspectiveInstallationDestinationV1[];
};
