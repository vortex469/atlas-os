import type { WorkflowOperationalActionRequestSummary } from "../types/atlasAgent";

/** Read the existing sanitized display contract; it never grants authority. */
export function operationalRequest(value: unknown): WorkflowOperationalActionRequestSummary | null {
    if (typeof value !== "object" || value === null || Array.isArray(value)) return null;
    const request = value as Record<string, unknown>;
    if (typeof request.verification !== "object" || request.verification === null || Array.isArray(request.verification)) return null;
    const verification = request.verification as Record<string, unknown>;
    const fields = [request.request_id, request.request_digest, request.provider_id, request.resource_id,
        request.resource_type, request.target_fingerprint, request.expected_pre_state, request.intended_action,
        request.disruption_scope, request.generated_at, request.expires_at, verification.pre_state,
        verification.expected_post_state, verification.health_requirement, verification.unknown_outcome_policy];
    if (!fields.every((field) => typeof field === "string" && field.trim().length > 0)
        || (request.target_version !== null && typeof request.target_version !== "string")
        || request.execution_enabled !== false || verification.pre_state !== request.expected_pre_state) return null;
    return value as WorkflowOperationalActionRequestSummary;
}
