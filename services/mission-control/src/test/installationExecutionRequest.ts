export const executionRequestFixture = {
    schema: "installation-execution-request-v1", execution_request_id: "00000000-0000-4000-8000-000000000001", recorded_at: "2026-08-28T12:00:00Z", valid_until: "2026-08-28T12:05:00Z", operation: "install-container", mode: "record-only",
    linkage: { candidate_record_id: "00000000-0000-4000-8000-000000000002", candidate_envelope_fingerprint: fp("a"), admission_fingerprint: fp("b"), candidate_record_fingerprint: fp("c"), approval_intent_id: "00000000-0000-4000-8000-000000000003", approval_intent_fingerprint: fp("d"), agent_request_id: "00000000-0000-4000-8000-000000000004", agent_request_fingerprint: fp("e"), agent_validation_fingerprint: fp("f"), agent_evidence_fingerprint: fp("1"), destination_fingerprint: "2".repeat(64), source_plan_fingerprint: fp("3"), artifact_policy_fingerprint: fp("4") },
    statement: "operator_requested_future_execution_of_exact_validated_candidate", execution_authorized: false, dispatch_allowed: false, agent_invocation_allowed: false, mutation_allowed: false, replay_allowed: false, execution_request_fingerprint: fp("5"), lifecycle_state: "recorded", evidence_provenance: "operator_submitted_agent_validation_evidence",
};

function fp(value: string) { return { algorithm: "sha256", canonicalization: "atlas-jcs-nfc-v1", value: value.repeat(64) }; }
