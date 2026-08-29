import type { ContractFingerprint } from "./atlasAgent";

export const DELIVERY_ENABLEMENT_CONFIRMATION = "I enable this exact delivery for later consideration only. This does not send, install, or execute anything." as const;

export interface DeliveryEnablementCreateV1 {
    schema: "operator-controlled-delivery-enablement-create-v1";
    preflight_id: string;
    preflight_fingerprint: ContractFingerprint;
    confirmation: typeof DELIVERY_ENABLEMENT_CONFIRMATION;
}

export interface DeliveryEnablementLinkageV1 {
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
    delivery_preparation_id: string;
    preparation_fingerprint: ContractFingerprint;
    preflight_id: string;
    preflight_fingerprint: ContractFingerprint;
}

export type DeliveryEnablementLifecycle = "enabled" | "expired" | "unavailable";

export interface DeliveryEnablementRecordV1 {
    schema: "operator-controlled-delivery-enablement-record-v1";
    enablement_id: string;
    enabled_at: string;
    expires_at: string;
    preflight_id: string;
    preflight_fingerprint: ContractFingerprint;
    delivery_preparation_id: string;
    preparation_fingerprint: ContractFingerprint;
    linkage: DeliveryEnablementLinkageV1;
    status_at_creation: "operator_enabled_for_later_delivery_consideration";
    confirmation: typeof DELIVERY_ENABLEMENT_CONFIRMATION;
    statement: "operator_enablement_evidence_only_no_delivery_activation";
    source: "core_operator_controlled_delivery_enablement_v1";
    default_enabled: false;
    operator_enabled: true;
    agent_contacted: false;
    credentials_loaded: false;
    production_transport_registered: false;
    delivery_activated: false;
    delivery_sent: false;
    delivery_authorized: false;
    execution_admission_granted: false;
    execution_authorized: false;
    dispatch_allowed: false;
    worker_allowed: false;
    workflow_allowed: false;
    installation_allowed: false;
    deployment_allowed: false;
    mutation_allowed: false;
    replay_allowed: false;
    enablement_fingerprint: ContractFingerprint;
}

export interface DeliveryEnablementStatusV1 {
    schema: "operator-controlled-delivery-enablement-status-v1";
    enablement_id: string;
    enablement_fingerprint: ContractFingerprint;
    observed_at: string;
    lifecycle: DeliveryEnablementLifecycle;
    operator_enabled: true;
    delivery_activated: false;
    delivery_sent: false;
    delivery_authorized: false;
    execution_authorized: false;
    replay_allowed: false;
}

export interface DeliveryEnablementAuditEvidenceV1 {
    schema: "operator-controlled-delivery-enablement-audit-evidence-v1";
    enablement_id: string;
    enablement_fingerprint: ContractFingerprint;
    preflight_id: string;
    preflight_fingerprint: ContractFingerprint;
    delivery_preparation_id: string;
    preparation_fingerprint: ContractFingerprint;
    enabled_at: string;
    expires_at: string;
    lifecycle: DeliveryEnablementLifecycle;
    status: "operator_enabled_for_later_delivery_consideration";
    confirmation: typeof DELIVERY_ENABLEMENT_CONFIRMATION;
    provenance: "core_operator_controlled_delivery_enablement_v1";
    delivery_activated: false;
    delivery_sent: false;
    delivery_authorized: false;
    execution_authorized: false;
    mutation_allowed: false;
    replay_allowed: false;
    evidence_fingerprint: ContractFingerprint;
}

export interface DeliveryEnablementOperationV1 {
    disposition: "created" | "exact_replay";
    record: DeliveryEnablementRecordV1;
    status: DeliveryEnablementStatusV1;
    audit_evidence: DeliveryEnablementAuditEvidenceV1;
    error: null;
    default_enabled: false;
    agent_contacted: false;
    credentials_loaded: false;
    delivery_activated: false;
    delivery_sent: false;
    delivery_authorized: false;
    execution_attempted: false;
    mutation_attempted: false;
    replay_allowed: false;
}

export interface DeliveryEnablementRedactedErrorV1 {
    schema: "operator-controlled-delivery-enablement-error-v1";
    error_code: "malformed" | "not_found" | "unauthenticated" | "unauthorized" | "confirmation_mismatch" | "linkage_mismatch" | "fingerprint_mismatch" | "preflight_not_eligible" | "not_current" | "replay_conflict" | "quota_exceeded" | "unavailable";
    correlation_id: string;
    preflight_id: string | null;
    preflight_fingerprint: ContractFingerprint | null;
    redacted: true;
}
