import type { WorkflowRecoveryDiagnostic } from "../types/atlasAgent";

export type RecoverySeverity = "success" | "info" | "warning" | "danger" | "unavailable";

export interface RecoveryPresentation {
    title: string;
    severity: RecoverySeverity;
    reason: string;
    safeNextAction: string;
}

const STATUS_PRESENTATION: Record<WorkflowRecoveryDiagnostic["diagnostic_status"], { title: string; severity: RecoverySeverity }> = {
    healthy: { title: "Healthy", severity: "success" },
    pending: { title: "Pending", severity: "info" },
    recovery_in_progress: { title: "Recovery in progress", severity: "info" },
    attention_required: { title: "Attention required", severity: "warning" },
    outcome_uncertain: { title: "Outcome uncertain", severity: "danger" },
    unavailable: { title: "Diagnostic unavailable", severity: "unavailable" },
};

const UNKNOWN_STATUS_PRESENTATION = { title: "Status unavailable", severity: "unavailable" } as const;

const REASON_TEXT: Record<NonNullable<WorkflowRecoveryDiagnostic["controlled_reason"]>, string> = {
    not_applicable: "Maintenance status checks do not apply to this workflow.",
    core_unavailable: "Atlas Core could not provide the latest maintenance status.",
    missing_core_record: "The request is recorded, but no matching service run was found.",
    immutable_request_mismatch: "Atlas found different request details in its records.",
    invalid_transition_sequence: "The recorded status changes are out of order.",
    dispatch_outcome_unknown: "The request was sent, but the service result is unknown.",
    dispatch_failed: "Atlas recorded that the maintenance request failed.",
    verification_pending: "The service check is still running.",
    verification_failed: "The service check did not pass.",
    target_replaced: "The target changed while Atlas checked the result.",
    terminal_state_disagreement: "Atlas has conflicting records about whether the request is finished.",
};

const SAFE_ACTION_TEXT: Record<WorkflowRecoveryDiagnostic["safe_next_action"], string> = {
    none: "No further action is needed.",
    wait_for_verification: "Wait for Atlas to finish checking the service. Do not run the request again.",
    restore_core_availability: "Restore Atlas Core, then refresh this page.",
    inspect_target_read_only: "Check the current service status without changing it.",
    preserve_evidence: "Keep the current request details. Ask an operator to review them before making changes.",
    operator_review_required: "Ask an operator to review this before creating a new maintenance request.",
    new_request_only_after_terminal: "Wait for this request to finish before creating another one.",
};

export function recoveryPresentation(diagnostic: WorkflowRecoveryDiagnostic): RecoveryPresentation {
    const isUnknownStatus = !Object.hasOwn(STATUS_PRESENTATION, diagnostic.diagnostic_status);
    const status = STATUS_PRESENTATION[diagnostic.diagnostic_status] ?? UNKNOWN_STATUS_PRESENTATION;
    return {
        ...status,
        reason: isUnknownStatus
            ? "Mission Control cannot identify this maintenance status."
            : diagnostic.controlled_reason ? REASON_TEXT[diagnostic.controlled_reason] : "No current issue has been reported.",
        safeNextAction: isUnknownStatus
            ? "Do not repeat this request until its status is clear. Ask an operator to review it."
            : SAFE_ACTION_TEXT[diagnostic.safe_next_action],
    };
}

export function isUnavailableDiagnosticStatus(value: string): boolean {
    return value === "unavailable" || !Object.hasOwn(STATUS_PRESENTATION, value);
}

export function recoveryLabel(value: string | null): string {
    return value ? value.replaceAll("_", " ") : "Not reported";
}
