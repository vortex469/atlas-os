import type { InstallationReadinessBlockerV1 } from "./installationReadinessReview";

export const EVIDENCE_ORDER = [
    ["v0.20", "candidate_record"], ["v0.21", "approval_intent"],
    ["v0.22", "agent_install_container_validation"], ["v0.23", "execution_request"],
    ["v0.24", "dispatch_handoff"], ["v0.25", "agent_intake_simulation"],
    ["v0.26", "simulated_handoff_delivery"], ["v0.27", "real_agent_intake"],
    ["v0.28", "dormant_delivery_wiring"], ["v0.29", "delivery_activation_preflight"],
    ["v0.30", "operator_delivery_enablement"], ["v0.31", "live_delivery_send"],
    ["v0.32", "agent_live_intake_admission"], ["v0.33", "inert_delivery_receipt"],
] as const;
export const BLOCKER_ORDER: readonly InstallationReadinessBlockerV1[] = [
    "missing_evidence", "ownership_mismatch", "linkage_mismatch", "fingerprint_mismatch",
    "invalid_evidence", "stale_evidence", "expired_evidence", "terminal_ambiguity",
    "agent_evidence_unavailable", "source_unavailable",
    "installation_capability_unsupported", "execution_admission_not_defined",
];
export const LINKAGE_KEYS = [
    "candidate_record_id", "candidate_envelope_fingerprint", "candidate_record_fingerprint",
    "approval_intent_id", "approval_intent_fingerprint", "agent_request_id",
    "agent_request_fingerprint", "agent_validation_fingerprint",
    "agent_audit_evidence_fingerprint", "destination_fingerprint",
    "source_plan_fingerprint", "artifact_policy_fingerprint", "execution_request_id",
    "execution_request_fingerprint", "dispatch_envelope_id", "dispatch_envelope_fingerprint",
    "simulation_request_id", "intake_record_id", "intake_record_fingerprint",
    "intake_simulation_evidence_fingerprint", "simulated_delivery_id",
    "simulated_delivery_fingerprint", "delivery_record_fingerprint",
    "simulated_delivery_evidence_fingerprint", "simulated_acknowledgement_id",
    "simulated_acknowledgement_fingerprint", "simulated_acknowledgement_evidence_fingerprint",
    "intake_request_id", "delivery_attempt_id", "dormant_preparation_fingerprint",
    "delivery_preparation_id", "preparation_fingerprint", "preflight_id",
    "preflight_fingerprint", "enablement_id", "enablement_fingerprint", "send_attempt_id",
    "attempt_fingerprint", "v031_send_receipt_fingerprint", "v032_envelope_fingerprint",
    "v032_agent_result_fingerprint", "v032_admission_id", "v032_admission_fingerprint",
    "v032_acknowledgement_id", "v032_acknowledgement_fingerprint",
    "v032_agent_receipt_exported", "v032_agent_receipt_atomicity_relied_upon",
    "v033_receipt_id", "v033_receipt_fingerprint", "v033_verification_fingerprint",
    "v033_linkage_fingerprint",
] as const;
