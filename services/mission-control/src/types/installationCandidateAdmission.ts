export type InstallationCandidateAdmissionStatus =
    | "admitted_but_non_executable"
    | "not_admitted";

export type InstallationCandidateAdmissionReason =
    | "input_invalid"
    | "input_unavailable"
    | "installation_plan_not_review_ready"
    | "destination_selection_not_active"
    | "destination_selection_expired"
    | "destination_identity_unavailable"
    | "destination_replaced_or_moved"
    | "capability_assessment_stale"
    | "capability_assessment_mismatched"
    | "capability_assessment_not_admissible"
    | "authority_invariant_violated";

export interface InstallationCandidateRecordV1 {
    schema: "installation-candidate-record-v1";
    item_id: string;
    catalog_entry_id: string;
    plan_fingerprint: string;
    selection_id: string;
    selected_destination_fingerprint: string;
    current_destination_fingerprint: string;
    capability_assessment_fingerprint: string;
    provider_fact_set_fingerprint: string;
    evaluated_at: string;
    valid_until: string;
    approved: false;
    executable: false;
    deployable: false;
    dispatchable: false;
    agent_execution_supported: false;
    record_fingerprint: string;
}

export interface InstallationCandidateAdmissionV1 {
    schema: "installation-candidate-admission-v1";
    plan_fingerprint: string;
    selection_fingerprint: string;
    selected_destination_fingerprint: string;
    current_destination_fingerprint: string;
    capability_assessment_fingerprint: string;
    provider_fact_set_fingerprint: string;
    evaluated_at: string;
    status: InstallationCandidateAdmissionStatus;
    reason_codes: InstallationCandidateAdmissionReason[];
    candidate_record: InstallationCandidateRecordV1 | null;
    approved: false;
    executable: false;
    deployable: false;
    dispatchable: false;
    agent_execution_supported: false;
    candidate_creation_allowed: false;
    admission_fingerprint: string;
}
