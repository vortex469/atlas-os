import type { ContractFingerprint } from "./atlasAgent";

export interface DeliveryActivationPreflightCreateV1 {
    schema: "delivery-activation-preflight-create-v1";
    delivery_preparation_id: string;
    preparation_fingerprint: ContractFingerprint;
}

export interface DeliveryActivationPreflightLinkageV1 {
    candidate_record_id: string;
    candidate_envelope_fingerprint: ContractFingerprint;
    candidate_record_fingerprint: ContractFingerprint;
    approval_intent_id: string;
    approval_intent_fingerprint: ContractFingerprint;
    agent_request_id: string;
    agent_request_fingerprint: ContractFingerprint;
    agent_validation_fingerprint: ContractFingerprint;
    agent_audit_evidence_fingerprint: ContractFingerprint;
    destination_fingerprint: ContractFingerprint;
    source_plan_fingerprint: ContractFingerprint;
    artifact_policy_fingerprint: ContractFingerprint;
    execution_request_id: string;
    execution_request_fingerprint: ContractFingerprint;
    dispatch_envelope_id: string;
    dispatch_envelope_fingerprint: ContractFingerprint;
    simulation_request_id: string;
    intake_record_id: string;
    intake_record_fingerprint: ContractFingerprint;
    intake_simulation_evidence_fingerprint: ContractFingerprint;
    simulated_delivery_id: string;
    simulated_delivery_fingerprint: ContractFingerprint;
    delivery_record_fingerprint: ContractFingerprint;
    simulated_delivery_evidence_fingerprint: ContractFingerprint;
    simulated_acknowledgement_id: string;
    simulated_acknowledgement_fingerprint: ContractFingerprint;
    simulated_acknowledgement_evidence_fingerprint: ContractFingerprint;
    intake_request_id: string;
    delivery_attempt_id: string;
    dormant_preparation_fingerprint: ContractFingerprint;
}

export type DeliveryActivationPreflightLifecycle = "eligible" | "expired" | "ineligible" | "unavailable";

export interface DeliveryActivationPreflightResultV1 {
    schema: "delivery-activation-preflight-result-v1";
    preflight_id: string;
    evaluated_at: string;
    expires_at: string;
    delivery_preparation_id: string;
    preparation_fingerprint: ContractFingerprint;
    endpoint_fingerprint: ContractFingerprint;
    linkage: DeliveryActivationPreflightLinkageV1;
    decision: "eligible_for_later_activation" | "ineligible";
    reason_codes: string[];
    lifecycle_at_evaluation: "eligible" | "ineligible";
    statement: "local_evidence_preflight_only_no_delivery_activation";
    source: "core_delivery_activation_preflight_v1";
    default_enabled: false;
    agent_contacted: false;
    credentials_loaded: false;
    production_transport_registered: false;
    delivery_activated: false;
    delivery_authorized: false;
    execution_admission_granted: false;
    execution_authorized: false;
    worker_allowed: false;
    mutation_allowed: false;
    replay_allowed: false;
    preflight_fingerprint: ContractFingerprint;
}

export interface DeliveryActivationPreflightStatusV1 {
    schema: "delivery-activation-preflight-status-v1";
    preflight_id: string;
    preflight_fingerprint: ContractFingerprint;
    observed_at: string;
    lifecycle: DeliveryActivationPreflightLifecycle;
    delivery_activated: false;
    delivery_authorized: false;
    replay_allowed: false;
}

export interface DeliveryActivationPreflightAuditEvidenceV1 {
    schema: "delivery-activation-preflight-audit-evidence-v1";
    preflight_id: string;
    preflight_fingerprint: ContractFingerprint;
    delivery_preparation_id: string;
    preparation_fingerprint: ContractFingerprint;
    intake_request_id: string;
    delivery_attempt_id: string;
    evaluated_at: string;
    expires_at: string;
    lifecycle: DeliveryActivationPreflightLifecycle;
    decision: "eligible_for_later_activation" | "ineligible";
    reason_codes: string[];
    provenance: "core_delivery_activation_preflight_v1";
    delivery_activated: false;
    delivery_authorized: false;
    execution_authorized: false;
    mutation_allowed: false;
    replay_allowed: false;
    evidence_fingerprint: ContractFingerprint;
}

export interface DeliveryActivationPreflightOperationV1 {
    disposition: "created" | "exact_replay";
    result: DeliveryActivationPreflightResultV1;
    status: DeliveryActivationPreflightStatusV1;
    audit_evidence: DeliveryActivationPreflightAuditEvidenceV1;
    error: null;
    default_enabled: false;
    agent_contacted: false;
    credentials_loaded: false;
    delivery_activated: false;
    delivery_authorized: false;
    execution_attempted: false;
    mutation_attempted: false;
    replay_allowed: false;
}
