import type { WorkflowImplementationRequestSummary } from "../types/atlasAgent";

/** Validate the existing display contract; approval authority stays with Agent. */
export function repositoryImplementationRequest(value: unknown): WorkflowImplementationRequestSummary | null {
    if (typeof value !== "object" || value === null || Array.isArray(value)) return null;
    const request = value as Record<string, unknown>;
    const readable = (field: unknown): field is string => typeof field === "string" && field.trim().length > 0;
    if (![request.immutable_request_id, request.tool, request.working_directory, request.repository].every(readable)
        || !Array.isArray(request.affected_files) || !request.affected_files.every(readable)
        || (request.translator_version !== null && typeof request.translator_version !== "string")) return null;
    return value as WorkflowImplementationRequestSummary;
}
