import type { OperationalCandidatePlanApiResponse, WorkflowOperationalActionRequestSummary } from "../types/atlasAgent";

export function operationalPlan(overrides: Partial<OperationalCandidatePlanApiResponse> = {}): OperationalCandidatePlanApiResponse {
    const targetFingerprint = `operational-target-fingerprint-v1:${"a".repeat(64)}`;
    return {
        identifier: "operational-plan-1", session_id: "candidate-plan-1", candidate_id: "candidate-1",
        candidate_fingerprint: "fingerprint-1", effect_kind: "operational_action", execution_intent: "restart-service",
        provider_id: "proxmox", resource_id: "110", resource_type: "qemu",
        target_fingerprint: targetFingerprint, target_version: "version-1", expected_pre_state: "running",
        intended_action: "restart-service", disruption_scope: "Temporary service interruption.",
        verification: { pre_state: "running", expected_post_state: "service-running-and-healthy",
            identity_fingerprint: targetFingerprint, health_requirement: "Confirm that the same exact service is healthy.",
            unknown_outcome_policy: "Stop and require operator review when the result cannot be verified." },
        failure_considerations: ["The service may fail to return to a healthy state.", "The action outcome may remain unknown."],
        evidence_ids: ["maintenance-evidence-1"], created_at: "2026-01-01T12:00:00Z",
        revalidated_candidate_fingerprint: "fingerprint-1", ...overrides,
    };
}

export function operationalActionRequest(overrides: Partial<WorkflowOperationalActionRequestSummary> = {}): WorkflowOperationalActionRequestSummary {
    const plan = operationalPlan();
    return {
        request_id: "action-request-123", request_digest: `operational-action-request-v1:${"b".repeat(64)}`,
        provider_id: plan.provider_id, resource_id: plan.resource_id, resource_type: plan.resource_type,
        target_fingerprint: plan.target_fingerprint, target_version: plan.target_version,
        expected_pre_state: plan.expected_pre_state, intended_action: plan.intended_action,
        disruption_scope: plan.disruption_scope, verification: {
            pre_state: plan.verification.pre_state, expected_post_state: plan.verification.expected_post_state,
            health_requirement: plan.verification.health_requirement, unknown_outcome_policy: plan.verification.unknown_outcome_policy,
        },
        generated_at: plan.created_at, expires_at: "2999-01-01T12:00:00Z", execution_enabled: false,
        ...overrides,
    };
}
