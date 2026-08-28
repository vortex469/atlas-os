import type { ContractFingerprint, InstallContainerValidation } from "./atlasAgent";

export const INSTALLATION_EXECUTION_REQUEST_STATEMENT = "operator_requested_future_execution_of_exact_validated_candidate" as const;

export interface AgentInstallContainerRequestV1 {
    schema: "agent-install-container-request-v1";
    operation: "install-container";
    mode: "validate-only";
    request_id: string;
    issued_at: string;
    expires_at: string;
    subject: Record<string, unknown>;
    approval: Record<string, unknown>;
    artifact: Record<string, unknown>;
    limits: Record<string, unknown>;
    request_fingerprint: ContractFingerprint;
}

export interface InstallationExecutionRequestCreateV1 {
    schema: "installation-execution-request-create-v1";
    candidate_record_id: string;
    approval_intent_id: string;
    agent_request: AgentInstallContainerRequestV1;
    agent_validation: InstallContainerValidation;
}

export interface InstallationExecutionRequestLinkageV1 {
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
}

export interface InstallationExecutionRequestV1 {
    schema: "installation-execution-request-v1";
    execution_request_id: string;
    recorded_at: string;
    valid_until: string;
    operation: "install-container";
    mode: "record-only";
    linkage: InstallationExecutionRequestLinkageV1;
    statement: typeof INSTALLATION_EXECUTION_REQUEST_STATEMENT;
    execution_authorized: false;
    dispatch_allowed: false;
    agent_invocation_allowed: false;
    mutation_allowed: false;
    replay_allowed: false;
    execution_request_fingerprint: ContractFingerprint;
    lifecycle_state: "recorded" | "expired";
    evidence_provenance: "operator_submitted_agent_validation_evidence";
}

export interface InstallationExecutionRequestCollectionV1 {
    execution_requests: InstallationExecutionRequestV1[];
}
