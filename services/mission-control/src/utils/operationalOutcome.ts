import type { WorkflowOperationalLifecycle } from "../types/atlasAgent";

export interface OutcomeGuidance {
    title: string;
    known: string;
    unknown: string;
    guidance: string;
    retryProhibited: boolean;
}

export function operationalOutcome(lifecycle: WorkflowOperationalLifecycle): OutcomeGuidance {
    if (lifecycle.consistency_status === "mismatch") return { title: "Maintenance records do not match", known: "Atlas found different request details in its records.", unknown: "Atlas cannot confirm the maintenance result.", guidance: "Ask an Atlas administrator to review these records.", retryProhibited: true };
    if (lifecycle.consistency_status === "core_unavailable") return { title: "Maintenance status unavailable", known: "Atlas still has the request and approval details.", unknown: "The latest service run and follow-up checks could not be confirmed.", guidance: "Restore Atlas Core, then refresh this page.", retryProhibited: true };
    if (lifecycle.agent_execution_stage === "submission_outcome_unknown") return { title: "Request result unknown", known: "Atlas cannot confirm whether the request was accepted.", unknown: "Maintenance may or may not have started.", guidance: "Check the current target and request status.", retryProhibited: true };
    if (lifecycle.controlled_reason === "target_replaced" || lifecycle.verification_status === "target_replaced") return { title: "Approved target changed", known: "The service identifier changed while Atlas checked the result.", unknown: "The approved target is no longer the current resource.", guidance: "Confirm the current target before making a new maintenance request.", retryProhibited: true };
    if (lifecycle.controlled_reason === "outcome_unknown" || lifecycle.verification_status === "outcome_unknown") return { title: "Run result unknown", known: "Atlas kept the request and run records.", unknown: "Atlas cannot confirm whether the service changed or passed its checks.", guidance: "Check the current target and status.", retryProhibited: true };
    if (lifecycle.controlled_reason === "verification_failed" || lifecycle.verification_status === "verification_failed") return { title: "Verification failed", known: "Atlas recorded the run, but the follow-up check did not pass.", unknown: "Atlas cannot confirm that the service is healthy.", guidance: "Review the service status.", retryProhibited: true };
    if (lifecycle.verification_status === "succeeded" && lifecycle.terminal) return { title: "Verified", known: "The approved request passed its follow-up checks.", unknown: "This approval does not allow any additional changes.", guidance: "Keep this status for your records.", retryProhibited: false };
    if (lifecycle.agent_execution_stage === "verification_pending" || lifecycle.core_record_state === "verifying") return { title: "Verification in progress", known: "Atlas has started a read-only check after the run.", unknown: "The final result is not available yet.", guidance: "Wait a moment and refresh.", retryProhibited: true };
    return { title: "Run status not yet recorded", known: "Atlas has the request and approval details.", unknown: "A service run has not been recorded yet.", guidance: "Check the approval status and refresh after the request runs.", retryProhibited: lifecycle.action_request_id !== null };
}
