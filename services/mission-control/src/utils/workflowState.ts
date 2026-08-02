import type { WorkflowTimelineStage } from "../types/atlasAgent";

export type WorkflowRailStatus = "completed" | "current" | "waiting" | "blocked" | "failed";

export interface WorkflowRailStage {
    label: string;
    status: WorkflowRailStatus;
}

export interface WorkflowStateInput {
    workflow_state: string;
    timeline?: WorkflowTimelineStage[];
}

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

const EMPTY_RAIL: WorkflowRailStage[] = [
    { label: "Candidate", status: "waiting" },
    { label: "Plan", status: "waiting" },
    { label: "Workflow", status: "waiting" },
    { label: "Implementation", status: "waiting" },
    { label: "Execution", status: "waiting" },
    { label: "Verification", status: "waiting" },
    { label: "Review", status: "waiting" },
    { label: "Commit", status: "waiting" },
];

const STATUS_PRIORITY: WorkflowRailStatus[] = [
    "failed",
    "blocked",
    "current",
    "waiting",
    "completed",
];

export function formatWorkflowLabel(value: string | null | undefined): string {
    if (!value) return "Not exposed";
    return value
        .split("_")
        .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
        .join(" ");
}

export function workflowStageLabel(state: string): string {
    switch (state) {
        case "awaiting_approval":
            return "Workflow";
        case "awaiting_implementation_approval":
            return "Implementation";
        case "executing":
            return "Execution";
        case "awaiting_verification_approval":
        case "verifying":
            return "Verification";
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
    return "waiting";
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
            label: "Candidate",
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
            label: "Implementation",
            status: normalizeStatus(stageByName.get("Implementation Approval")?.status ?? "waiting"),
        },
        {
            label: "Execution",
            status: normalizeStatus(stageByName.get("Execution")?.status ?? "waiting"),
        },
        {
            label: "Verification",
            status: normalizeStatus(stageByName.get("Verification")?.status ?? "waiting"),
        },
        {
            label: "Review",
            status: normalizeStatus(stageByName.get("Review")?.status ?? "waiting"),
        },
        {
            label: "Commit",
            status: normalizeStatus(stageByName.get("Commit")?.status ?? "waiting"),
        },
    ];
}
