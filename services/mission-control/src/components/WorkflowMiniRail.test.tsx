import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { WorkflowMiniRail } from "./WorkflowMiniRail";
import {
    WORKFLOW_STATES,
    workflowActionRequired,
    workflowNextStepLabel,
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

        expect(screen.getByText("Proposal")).toBeInTheDocument();
        expect(screen.getByText("Plan")).toBeInTheDocument();
        expect(screen.getByText("Apply change")).toBeInTheDocument();
        expect(screen.getByText("Verify change")).toBeInTheDocument();
        const items = screen.getAllByRole("listitem");
        expect(within(items[4]).getByText("Failed")).toBeInTheDocument();
        expect(within(items[5]).getByText("Blocked")).toBeInTheDocument();
        expect(within(items[6]).getByText("Not started")).toBeInTheDocument();
    });

    it("keeps an unrecognized stage status unavailable instead of showing it as not started", () => {
        const stages = workflowRailStages({
            workflow_state: "blocked",
            timeline: fullTimeline.map((stage) => stage.name === "Execution" ? { ...stage, status: "unexpected" } : stage),
        });
        render(<WorkflowMiniRail stages={stages} />);

        const applyChange = screen.getByText("Apply change").closest("li");
        expect(within(applyChange as HTMLElement).getByText("Status unavailable")).toBeInTheDocument();
    });

    it("maps every backend workflow state deterministically", () => {
        const labels = WORKFLOW_STATES.map((state) => workflowStageLabel(state));
        const groups = WORKFLOW_STATES.map((state) => workflowStatusGroup(state));

        expect(labels).toEqual([
            "Prepare change",
            "Change approval",
            "Apply change",
            "Verify change",
            "Verify change",
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

    it("gives a safe next step for each operator action state", () => {
        expect(workflowNextStepLabel("awaiting_approval")).toBe("Prepare the change for review.");
        expect(workflowNextStepLabel("awaiting_implementation_approval")).toBe("Review the change; resume it if approved.");
        expect(workflowNextStepLabel("awaiting_implementation_approval", "operational_action")).toBe("Review the maintenance request; run it only after approval.");
        expect(workflowNextStepLabel("awaiting_verification_approval")).toBe("Review the checks; resume to run them if approved.");
        expect(workflowNextStepLabel("awaiting_commit_approval")).toBe("Review the commit; resume to record it if approved.");
        expect(workflowNextStepLabel("executing")).toBeNull();
    });
});
