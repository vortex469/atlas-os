import type { WorkflowCommitRequestSummary } from "../types/atlasAgent";

/** Read the existing display contract without granting commit authority. */
export function repositoryCommitRequest(value: unknown): WorkflowCommitRequestSummary | null {
    if (typeof value !== "object" || value === null || Array.isArray(value)) return null;
    const request = value as Record<string, unknown>;
    const readable = (field: unknown): field is string => typeof field === "string" && field.trim().length > 0;
    if (![request.commit_request_id, request.commit_message, request.reviewed_content_fingerprint, request.commit_approval_status].every(readable)
        || !Array.isArray(request.reviewed_files) || !request.reviewed_files.every(readable)
        || ![request.repository, request.branch, request.expected_head].every(field => field === null || typeof field === "string")) return null;
    return value as WorkflowCommitRequestSummary;
}
