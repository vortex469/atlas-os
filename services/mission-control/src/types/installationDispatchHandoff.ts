import type { ContractFingerprint } from "./atlasAgent";

export interface InstallationDispatchHandoffCreateV1 {
    schema: "installation-dispatch-handoff-create-v1";
    execution_request_id: string;
}
export interface InstallationDispatchRecipientV1 {
    service: "atlas-agent";
    intake_contract: "agent-installation-dispatch-intake-v1";
}

export interface InstallationDispatchLinkageV1 {
    candidate_record_id: string;
    candidate_envelope_fingerprint: ContractFingerprint;
    admission_fingerprint: ContractFingerprint;
    candidate_record_fingerprint: ContractFingerprint;
    approval_intent_id: string;
    approval_intent_fingerprint: ContractFingerprint;
    agent_request_id: string;
    agent_request_fingerprint: ContractFingerprint;
    agent_validation_fingerprint: ContractFingerprint;
    agent_evidence_fingerprint: ContractFingerprint;
    destination_fingerprint: string;
    source_plan_fingerprint: ContractFingerprint;
    artifact_policy_fingerprint: ContractFingerprint;
    execution_request_id: string;
    execution_request_fingerprint: ContractFingerprint;
}

export interface InstallationDispatchHandoffV1 {
    schema: "installation-dispatch-envelope-v1";
    dispatch_envelope_id: string;
    prepared_at: string;
    valid_until: string;
    operation: "install-container";
    mode: "handoff-only";
    recipient: InstallationDispatchRecipientV1;
    linkage: InstallationDispatchLinkageV1;
    statement: "core_prepared_non_executing_agent_handoff";
    delivery_authorized: false;
    agent_admission_authorized: false;
    execution_authorized: false;
    mutation_authorized: false;
    replay_allowed: false;
    dispatch_envelope_fingerprint: ContractFingerprint;
    lifecycle_state: "prepared" | "expired";
    evidence_provenance: "core_prepared_not_delivered";
}
