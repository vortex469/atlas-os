import type { CandidateWorkflowResponse } from "../types/atlasAgent";

function isReference(value: unknown): boolean {
    if (typeof value !== "string" || !value || value.trim() !== value || value === "." || value === ".."
        || Array.from(value).some(character => character.charCodeAt(0) < 32 || character.charCodeAt(0) === 127)) return false;
    try {
        encodeURIComponent(value);
        return true;
    } catch {
        return false;
    }
}

// Check the fields rendered or handed to workflow review; unused metadata stays extensible.
export function isReadableWorkflowSummary(workflow: CandidateWorkflowResponse): boolean {
    if (!workflow || typeof workflow !== "object" || Array.isArray(workflow)) return false;
    const nullableText = [workflow.workflow_status, workflow.implementation_approval_request_id,
        workflow.candidate_fingerprint, workflow.candidate_plan_fingerprint];
    const failure = workflow.failure;
    const readableFailure = failure === null || (typeof failure === "object" && !Array.isArray(failure)
        && typeof failure?.code === "string" && typeof failure?.message === "string");
    return isReference(workflow.candidate_planning_session_id) && isReference(workflow.candidate_id)
        && (workflow.workflow_session_id === null || isReference(workflow.workflow_session_id))
        && typeof workflow.conversion_status === "string" && workflow.conversion_status.trim().length > 0
        && nullableText.every(value => value === null || typeof value === "string")
        && Array.isArray(workflow.reason_codes) && workflow.reason_codes.every(value => typeof value === "string")
        && readableFailure;
}
