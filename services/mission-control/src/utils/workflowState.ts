import type { WorkflowTimelineStage } from "../types/atlasAgent";

export type WorkflowRailStatus = "completed" | "current" | "waiting" | "blocked" | "failed" | "unknown";

export interface WorkflowRailStage {
    label: string;
    status: WorkflowRailStatus;
}

export interface WorkflowStateInput {
    workflow_state: string;
    timeline?: WorkflowTimelineStage[];
}

export type WorkflowStatusGroup =
    | "running"
    | "waiting_approval"
    | "waiting_implementation_approval"
    | "waiting_verification_approval"
    | "waiting_commit_approval"
    | "blocked"
    | "completed"
    | "unknown";

export type WorkflowLifecycleState =
    | "awaiting_approval"
    | "awaiting_implementation_approval"
    | "executing"
    | "awaiting_verification_approval"
    | "verifying"
    | "awaiting_commit_approval"
    | "committing"
    | "blocked"
    | "completed";

export const WORKFLOW_STATE_UNKNOWN = "unknown" as const;

export const WORKFLOW_STATES = [
    "awaiting_approval",
    "awaiting_implementation_approval",
    "executing",
    "awaiting_verification_approval",
    "verifying",
    "awaiting_commit_approval",
    "committing",
    "blocked",
    "completed",
] as const;

const EMPTY_VALUE = "Not exposed";
const NOT_AVAILABLE_VALUE = "Not available";

export function formatWorkflowValue(value: string | null | undefined, fallback: string = EMPTY_VALUE): string {
    return value === null || value === undefined || value === "" ? fallback : value;
}

export function formatWorkflowResultSummary(value: string | null | undefined): string {
    return formatWorkflowValue(value, "No result reported yet").replaceAll(/[_-]+/g, " ");
}

export function formatFingerprint(value: string | null | undefined): string {
    return formatWorkflowValue(value, "Not exposed");
}

export function formatWorkflowStatus(value: string | null | undefined): string {
    return value === null || value === undefined || value === ""
        ? NOT_AVAILABLE_VALUE
        : value
            .replaceAll("_", " ")
            .replaceAll("-", " ")
            .replace(/\b\w/g, (letter) => letter.toUpperCase())
            .replace("Not reached", "Not reached")
            .replace("Not_available", "Not available");
}

export function formatWorkflowLabel(value: string | null | undefined): string {
    return formatWorkflowStatus(value);
}

const EMPTY_RAIL: WorkflowRailStage[] = [
    { label: "Proposal", status: "waiting" },
    { label: "Plan", status: "waiting" },
    { label: "Workflow", status: "waiting" },
    { label: "Change approval", status: "waiting" },
    { label: "Apply change", status: "waiting" },
    { label: "Verify change", status: "waiting" },
    { label: "Review results", status: "waiting" },
    { label: "Commit", status: "waiting" },
];

const STATUS_PRIORITY: WorkflowRailStatus[] = [
    "failed",
    "blocked",
    "unknown",
    "current",
    "waiting",
    "completed",
];

export function workflowStageLabel(state: string, effectKind?: string): string {
    if (effectKind === "operational_action" && state === "awaiting_implementation_approval") {
        return "Maintenance request approval";
    }
    switch (state) {
        case "awaiting_approval":
            return "Prepare change";
        case "awaiting_implementation_approval":
            return "Change approval";
        case "executing":
            return "Apply change";
        case "awaiting_verification_approval":
        case "verifying":
            return "Verify change";
        case "awaiting_commit_approval":
        case "committing":
            return "Commit";
        case "blocked":
            return "Blocked";
        case "completed":
            return "Completed";
        default:
            return formatWorkflowLabel(state);
    }
}

export function workflowStateFilterLabel(state: string): string {
    switch (state) {
        case "awaiting_approval": return "Prepare change for review";
        case "awaiting_implementation_approval": return "Review change, then run if approved";
        case "executing": return "Applying change";
        case "awaiting_verification_approval": return "Review checks, then run if approved";
        case "verifying": return "Running checks";
        case "awaiting_commit_approval": return "Review commit, then record if approved";
        case "committing": return "Recording commit";
        case "blocked": return "Blocked";
        case "completed": return "Completed";
        default: return "Status unavailable";
    }
}

export function workflowNextStepLabel(state: string, effectKind?: string): string | null {
    switch (state) {
        case "awaiting_approval":
            return "Prepare the change for review.";
        case "awaiting_implementation_approval":
            return effectKind === "operational_action"
                ? "Review the maintenance request. If approved, choose Run approved maintenance."
                : "Review the change. If approved, choose Run approved change.";
        case "awaiting_verification_approval":
            return "Review the checks. If approved, choose Run approved checks.";
        case "awaiting_commit_approval":
            return "Review the commit. If approved, choose Record approved commit.";
        case "blocked":
            return "Open the workflow to review what is blocked.";
        default:
            return null;
    }
}

export function workflowStageStatusLabel(status: string): string {
    switch (status) {
        case "completed": return "Done";
        case "current": return "Current step";
        case "waiting": return "Not started";
        case "blocked": return "Blocked";
        case "failed": return "Failed";
        default: return "Status unavailable";
    }
}

export function workflowStatusGroup(state: string): string {
    switch (state) {
        case "executing":
        case "verifying":
        case "committing":
            return "running";
        case "awaiting_implementation_approval":
            return "waiting_implementation_approval";
        case "awaiting_verification_approval":
            return "waiting_verification_approval";
        case "awaiting_commit_approval":
            return "waiting_commit_approval";
        case "blocked":
            return "blocked";
        case "completed":
            return "completed";
        case "awaiting_approval":
            return "waiting_approval";
        default:
            return "unknown";
    }
}

export function workflowActionRequired(state: string): boolean {
    return [
        "awaiting_approval",
        "awaiting_implementation_approval",
        "awaiting_verification_approval",
        "awaiting_commit_approval",
    ].includes(state);
}

export function isActiveWorkflowState(state: string): boolean {
    return ["executing", "verifying", "committing"].includes(state);
}

function normalizeStatus(status: string): WorkflowRailStatus {
    if (["completed", "current", "waiting", "blocked", "failed"].includes(status)) {
        return status as WorkflowRailStatus;
    }
    return "unknown";
}

function pickCombinedStatus(stages: Array<WorkflowTimelineStage | undefined>): WorkflowRailStatus {
    const statuses = stages.map((stage) => normalizeStatus(stage?.status ?? "waiting"));
    return STATUS_PRIORITY.find((status) => statuses.includes(status)) ?? "waiting";
}

export function fallbackWorkflowRailStages(): WorkflowRailStage[] {
    return EMPTY_RAIL.map((stage) => ({ ...stage }));
}

export function workflowRailStages(input: WorkflowStateInput | null | undefined): WorkflowRailStage[] {
    if (!input?.timeline || input.timeline.length === 0) {
        return fallbackWorkflowRailStages();
    }

    const stageByName = new Map(input.timeline.map((stage) => [stage.name, stage]));
    return [
        {
            label: "Proposal",
            status: normalizeStatus(stageByName.get("Execution Candidate")?.status ?? "waiting"),
        },
        {
            label: "Plan",
            status: pickCombinedStatus([
                stageByName.get("Planning Session"),
                stageByName.get("Candidate Plan"),
            ]),
        },
        {
            label: "Workflow",
            status: normalizeStatus(stageByName.get("Workflow")?.status ?? "waiting"),
        },
        {
            label: "Change approval",
            status: normalizeStatus(stageByName.get("Implementation Approval")?.status ?? "waiting"),
        },
        {
            label: "Apply change",
            status: normalizeStatus(stageByName.get("Execution")?.status ?? "waiting"),
        },
        {
            label: "Verify change",
            status: normalizeStatus(stageByName.get("Verification")?.status ?? "waiting"),
        },
        {
            label: "Review results",
            status: normalizeStatus(stageByName.get("Review")?.status ?? "waiting"),
        },
        {
            label: "Commit",
            status: normalizeStatus(stageByName.get("Commit")?.status ?? "waiting"),
        },
    ];
}
