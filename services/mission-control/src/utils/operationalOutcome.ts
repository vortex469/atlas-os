import type { WorkflowOperationalLifecycle } from "../types/atlasAgent";

export interface OutcomeGuidance {
    title: string;
    known: string;
    unknown: string;
    guidance: string;
    retryProhibited: boolean;
}

export function operationalOutcome(lifecycle: WorkflowOperationalLifecycle): OutcomeGuidance {
    if (lifecycle.consistency_status === "mismatch") return { title: "Immutable lifecycle mismatch", known: "Agent and Core returned lifecycle records that do not share the approved immutable identity.", unknown: "Atlas cannot safely determine a unified outcome.", guidance: "Review durable lifecycle evidence and contact an Atlas administrator.", retryProhibited: true };
    if (lifecycle.consistency_status === "core_unavailable") return { title: "Core lifecycle unavailable", known: "The Agent workflow remains available.", unknown: "Current durable Core dispatch and verification state could not be read.", guidance: "Restore Core availability, then refresh this read-only lifecycle.", retryProhibited: true };
    if (lifecycle.agent_execution_stage === "submission_outcome_unknown") return { title: "Submission outcome unknown", known: "Atlas cannot prove whether Core accepted the request.", unknown: "A provider mutation may or may not have started.", guidance: "Inspect durable Core evidence and current target state; do not submit another mutation.", retryProhibited: true };
    if (lifecycle.controlled_reason === "target_replaced" || lifecycle.verification_status === "target_replaced") return { title: "Target replaced", known: "Verification observed a different authoritative target identity.", unknown: "The approved target can no longer be treated as the current resource.", guidance: "Resolve the current target again before considering a new bounded request.", retryProhibited: true };
    if (lifecycle.controlled_reason === "outcome_unknown" || lifecycle.verification_status === "outcome_unknown") return { title: "Outcome unknown", known: "Atlas preserved the durable request and exactly-once evidence.", unknown: "The final provider or verification outcome is not known.", guidance: "Inspect the current target state and durable evidence. Never retry this mutation.", retryProhibited: true };
    if (lifecycle.controlled_reason === "verification_failed" || lifecycle.verification_status === "verification_failed") return { title: "Verification failed", known: "Dispatch evidence exists, but the approved verification policy did not pass.", unknown: "A successful service outcome cannot be asserted.", guidance: "Review observed state and health. Do not retry the prior mutation.", retryProhibited: true };
    if (lifecycle.verification_status === "succeeded" && lifecycle.terminal) return { title: "Verified", known: "Core recorded a terminal verification success for the approved request.", unknown: "No additional mutation is implied or authorized.", guidance: "Retain this lifecycle as the authoritative operational record.", retryProhibited: false };
    if (lifecycle.agent_execution_stage === "verification_pending" || lifecycle.core_record_state === "verifying") return { title: "Verification pending", known: "The dispatch lifecycle reached read-only verification.", unknown: "The terminal verification outcome is not available yet.", guidance: "Wait for reconciliation and refresh the lifecycle. Do not issue another mutation.", retryProhibited: true };
    return { title: "Agent-only lifecycle", known: "Agent has preserved workflow and approval context.", unknown: "No durable Core lifecycle is currently available.", guidance: "Review approval state and wait for normal submission or Core correlation.", retryProhibited: lifecycle.action_request_id !== null };
}
