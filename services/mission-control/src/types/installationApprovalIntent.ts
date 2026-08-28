export const INSTALLATION_APPROVAL_STATEMENT = "operator_approved_exact_non_executable_candidate" as const;

export interface InstallationApprovalSubjectV1 {
    candidate_record_id: string;
    candidate_envelope_fingerprint: string;
    admission_fingerprint: string;
    candidate_record_fingerprint: string;
}

export interface InstallationApprovalIntentV1 {
    schema: "installation-approval-intent-v1";
    approval_intent_id: string;
    operator_id: string;
    recorded_at: string;
    approved_subject: InstallationApprovalSubjectV1;
    statement: typeof INSTALLATION_APPROVAL_STATEMENT;
    intent_fingerprint: string;
}

export interface InstallationApprovalIntentCollectionV1 {
    approval_intents: InstallationApprovalIntentV1[];
}
