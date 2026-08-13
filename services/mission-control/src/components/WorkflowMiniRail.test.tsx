import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { WorkflowMiniRail } from "./WorkflowMiniRail";
import {
    WORKFLOW_STATES,
    workflowActionRequired,
    workflowRailStages,
    workflowStageLabel,
    workflowStatusGroup,
} from "../utils/workflowState";

const fullTimeline = [
    { name: "Execution Candidate", status: "completed" },
    { name: "Planning Session", status: "completed" },
    { name: "Candidate Plan", status: "completed" },
    { name: "Workflow", status: "completed" },
    { name: "Implementation Approval", status: "completed" },
    { name: "Execution", status: "failed" },
    { name: "Verification", status: "blocked" },
    { name: "Review", status: "waiting" },
    { name: "Commit", status: "waiting" },
];

describe("WorkflowMiniRail", () => {
    it("renders compact rail stages with text statuses", () => {
        render(<WorkflowMiniRail stages={workflowRailStages({ workflow_state: "blocked", timeline: fullTimeline })} />);

        expect(screen.getByText("Candidate")).toBeInTheDocument();
        expect(screen.getByText("Plan")).toBeInTheDocument();
        expect(screen.getByText("Execution")).toBeInTheDocument();
        expect(screen.getByText("Verification")).toBeInTheDocument();
        const items = screen.getAllByRole("listitem");
        expect(within(items[4]).getByText("failed")).toBeInTheDocument();
        expect(within(items[5]).getByText("blocked")).toBeInTheDocument();
    });

    it("maps every backend workflow state deterministically", () => {
        const labels = WORKFLOW_STATES.map((state) => workflowStageLabel(state));
        const groups = WORKFLOW_STATES.map((state) => workflowStatusGroup(state));

        expect(labels).toEqual([
            "Workflow",
            "Implementation",
            "Execution",
            "Verification",
            "Verification",
            "Commit",
            "Commit",
            "Blocked",
            "Completed",
        ]);
        expect(groups).toEqual([
            "waiting_approval",
            "waiting_implementation_approval",
            "running",
            "waiting_verification_approval",
            "running",
            "waiting_commit_approval",
            "running",
            "blocked",
            "completed",
        ]);
    });

    it("marks waiting approval states as action required", () => {
        expect(workflowActionRequired("awaiting_implementation_approval")).toBe(true);
        expect(workflowActionRequired("awaiting_verification_approval")).toBe(true);
        expect(workflowActionRequired("awaiting_commit_approval")).toBe(true);
        expect(workflowActionRequired("executing")).toBe(false);
        expect(workflowActionRequired("completed")).toBe(false);
    });
});
