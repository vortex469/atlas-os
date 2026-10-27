import type { WorkflowVerificationPlanSummary } from "../types/atlasAgent";

/** Read an identified public plan; verification authority stays with Agent. */
export function repositoryVerificationPlan(value: unknown): WorkflowVerificationPlanSummary | null {
    if (typeof value !== "object" || value === null || Array.isArray(value)) return null;
    const plan = value as Record<string, unknown>;
    const readable = (field: unknown): field is string => typeof field === "string" && field.trim().length > 0;
    if (!readable(plan.verification_plan_id) || !readable(plan.verification_status)
        || !Array.isArray(plan.verification_check_ids) || !plan.verification_check_ids.every(readable)
        || !Array.isArray(plan.command_backed_checks) || !plan.command_backed_checks.every(readable)
        || ![plan.verifier_version, plan.changed_files_digest, plan.working_directory, plan.repository].every(field => field === null || typeof field === "string")) return null;
    return value as WorkflowVerificationPlanSummary;
}
