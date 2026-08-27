import type { InstallationCandidateRecordV1 } from "./installationCandidateAdmission";

export type InstallationCandidateLifecycleState = "active" | "expired";

export interface InstallationCandidateRecordEnvelopeV1 {
    schema: "installation-candidate-record-envelope-v1";
    candidate_record_id: string;
    created_at: string;
    admission_fingerprint: string;
    candidate_record: InstallationCandidateRecordV1;
    envelope_fingerprint: string;
    lifecycle_state: InstallationCandidateLifecycleState;
}

export interface InstallationCandidateRecordCollectionV1 {
    records: InstallationCandidateRecordEnvelopeV1[];
}
