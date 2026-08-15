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

const REASON_TEXT: Record<NonNullable<WorkflowRecoveryDiagnostic["controlled_reason"]>, string> = {
    not_applicable: "Operational recovery diagnostics do not apply to this workflow.",
    core_unavailable: "Atlas Core lifecycle evidence is currently unavailable.",
    missing_core_record: "Agent has an execution reference but no matching Core record was found.",
    immutable_request_mismatch: "Agent and Core do not agree on the immutable operational request.",
    invalid_transition_sequence: "The durable Core transition sequence does not match the allowed lifecycle ordering.",
    dispatch_outcome_unknown: "The dispatch barrier was crossed, but the provider outcome is not known.",
    dispatch_failed: "Core recorded a failed dispatch result.",
    verification_pending: "Read-only verification has not reached a terminal result.",
    verification_failed: "The approved verification specification did not pass.",
    target_replaced: "Verification observed a different authoritative target identity.",
    terminal_state_disagreement: "Agent and Core disagree about whether the lifecycle is terminal.",
};

const SAFE_ACTION_TEXT: Record<WorkflowRecoveryDiagnostic["safe_next_action"], string> = {
    none: "No recovery action is required.",
    wait_for_verification: "Wait for Atlas verification to complete; do not replay the operation.",
    restore_core_availability: "Restore Atlas Core availability and refresh the read-only lifecycle.",
    inspect_target_read_only: "Inspect the target using read-only status information.",
    preserve_evidence: "Preserve the current lifecycle and support evidence before changing system state.",
    operator_review_required: "Operator review is required before any new maintenance request.",
    new_request_only_after_terminal: "Do not create a replacement request until the current lifecycle is terminal.",
};

export function recoveryPresentation(diagnostic: WorkflowRecoveryDiagnostic): RecoveryPresentation {
    const status = STATUS_PRESENTATION[diagnostic.diagnostic_status];
    return {
        ...status,
        reason: diagnostic.controlled_reason ? REASON_TEXT[diagnostic.controlled_reason] : "No controlled recovery concern is recorded.",
        safeNextAction: SAFE_ACTION_TEXT[diagnostic.safe_next_action],
    };
}

export function recoveryLabel(value: string | null): string {
    return value ? value.replaceAll("_", " ") : "Not reported";
}
