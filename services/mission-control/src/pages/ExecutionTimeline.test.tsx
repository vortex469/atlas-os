import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { WorkflowDetailResponse } from "../types/atlasAgent";
import { ExecutionTimeline } from "./ExecutionTimeline";

function workflow(overrides: Partial<WorkflowDetailResponse> = {}): WorkflowDetailResponse {
    return {
        workflow_id: "workflow-123",
        workflow_source: "candidate",
        workflow_state: "awaiting_implementation_approval",
        planning_session_id: "candidate-plan-123",
        candidate_id: "candidate-123",
        candidate_fingerprint: "candidate-fingerprint-123",
        plan_fingerprint: "plan-fingerprint-123",
        implementation_approval_status: "pending",
        repository: "/opt/atlas",
        working_directory: "/opt/atlas/services/demo",
        translator_version: "candidate-translator-v1",
        affected_files: ["compose.yaml"],
        implementation_request: null,
        timeline: [
            { name: "Execution Candidate", status: "completed" },
            { name: "Planning Session", status: "completed" },
            { name: "Candidate Plan", status: "completed" },
            { name: "Workflow", status: "completed" },
            { name: "Implementation Approval", status: "current" },
            { name: "Execution", status: "waiting" },
            { name: "Verification", status: "waiting" },
            { name: "Review", status: "waiting" },
            { name: "Commit", status: "waiting" },
        ],
        execution: {
            execution_status: null,
            started_at: null,
            completed_at: null,
            result: null,
            changed_files_count: 0,
            tool: null,
            working_directory: null,
            repository: "/opt/atlas",
            changed_files: [],
            execution_request_id: null,
        },
        ...overrides,
    };
}

function renderTimeline(workflowDetail: WorkflowDetailResponse, options: { isRefreshing?: boolean; onRefresh?: () => void } = {}) {
    return render(
        <ExecutionTimeline workflow={workflowDetail} isRefreshing={options.isRefreshing ?? false} onRefresh={options.onRefresh ?? vi.fn()} />,
    );
}

describe("ExecutionTimeline", () => {
    it("renders all authoritative timeline stages", () => {
        renderTimeline(workflow());

        for (const stage of ["Execution Candidate", "Planning Session", "Candidate Plan", "Workflow", "Implementation Approval", "Execution", "Verification", "Review", "Commit"]) {
            expect(screen.getAllByText(stage).length).toBeGreaterThan(0);
        }
    });

    it("renders waiting state", () => {
        renderTimeline(workflow());

        expect(screen.getAllByText("Waiting for implementation approval.").length).toBeGreaterThan(0);
    });

    it("renders running state", () => {
        renderTimeline(workflow({
            workflow_state: "executing",
            implementation_approval_status: "approved",
            timeline: workflow().timeline.map((stage) => stage.name === "Execution" ? { ...stage, status: "current" } : stage),
        }));

        expect(screen.getAllByText("Execution running...").length).toBeGreaterThan(0);
    });

    it("renders successful execution result", () => {
        renderTimeline(workflow({
            workflow_state: "awaiting_verification_approval",
            implementation_approval_status: "approved",
            timeline: workflow().timeline.map((stage) => stage.name === "Execution" ? { ...stage, status: "completed" } : stage),
            execution: {
                execution_status: "succeeded",
                started_at: null,
                completed_at: null,
                result: "succeeded",
                changed_files_count: 2,
                tool: "docker-compose",
                working_directory: "/opt/atlas/services/demo",
                repository: "/opt/atlas",
                changed_files: ["compose.yaml", "services/demo/Dockerfile"],
                execution_request_id: "exec-123",
            },
        }));

        expect(screen.getAllByText("Execution complete.").length).toBeGreaterThan(0);
        expect(screen.getAllByText("Succeeded").length).toBeGreaterThan(0);
        expect(screen.getByText("2")).toBeInTheDocument();
        expect(screen.getByText("docker-compose")).toBeInTheDocument();
        expect(screen.getByText("exec-123")).toBeInTheDocument();
        expect(screen.getByText("compose.yaml, services/demo/Dockerfile")).toBeInTheDocument();
    });

    it("renders blocked state from backend stage status", () => {
        renderTimeline(workflow({
            implementation_approval_status: "rejected",
            timeline: workflow().timeline.map((stage) => stage.name === "Implementation Approval" ? { ...stage, status: "blocked" } : stage),
        }));

        expect(screen.getByText("Blocked")).toBeInTheDocument();
    });

    it("renders failed execution state", () => {
        renderTimeline(workflow({
            implementation_approval_status: "approved",
            timeline: workflow().timeline.map((stage) => stage.name === "Execution" ? { ...stage, status: "failed" } : stage),
            execution: {
                execution_status: "failed",
                started_at: null,
                completed_at: null,
                result: "failed",
                changed_files_count: 0,
                tool: "docker-compose",
                working_directory: "/opt/atlas/services/demo",
                repository: "/opt/atlas",
                changed_files: [],
                execution_request_id: "exec-123",
            },
        }));

        expect(screen.getByText("Execution failed.")).toBeInTheDocument();
        expect(screen.getAllByText("Failed").length).toBeGreaterThan(0);
    });

    it("refreshes and blocks duplicate refresh while pending", () => {
        const onRefresh = vi.fn();
        const { rerender } = render(
            <ExecutionTimeline workflow={workflow()} isRefreshing={false} onRefresh={onRefresh} />,
        );

        fireEvent.click(screen.getByRole("button", { name: "Refresh" }));
        expect(onRefresh).toHaveBeenCalledTimes(1);

        rerender(<ExecutionTimeline workflow={workflow()} isRefreshing={true} onRefresh={onRefresh} />);
        fireEvent.click(screen.getByRole("button", { name: "Refreshing..." }));
        expect(onRefresh).toHaveBeenCalledTimes(1);
    });

    it("does not render execution, verification, review, or commit controls", () => {
        renderTimeline(workflow());

        expect(screen.queryByRole("button", { name: /execute/i })).not.toBeInTheDocument();
        expect(screen.queryByRole("button", { name: /verify/i })).not.toBeInTheDocument();
        expect(screen.queryByRole("button", { name: /review/i })).not.toBeInTheDocument();
        expect(screen.queryByRole("button", { name: /commit/i })).not.toBeInTheDocument();
        expect(screen.queryByRole("textbox")).not.toBeInTheDocument();
    });
});
