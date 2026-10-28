import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { WorkflowDetailResponse } from "../types/atlasAgent";
import { ExecutionTimeline } from "./ExecutionTimeline";

function workflow(overrides: Partial<WorkflowDetailResponse> = {}): WorkflowDetailResponse {
    return {
        workflow_id: "workflow-123",
        workflow_source: "candidate",
        effect_kind: "repository_change",
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
        operational_action_request: null,
        operational_execution: null,
        approval_presentations: [],
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
        verification_plan: {
            verification_plan_id: null,
            verifier_version: null,
            changed_files_digest: null,
            verification_check_ids: [],
            command_backed_checks: [],
            working_directory: null,
            repository: null,
            verification_status: "not_available",
        },
        verification_evidence: {
            verification_status: null,
            completed_time: null,
            executed_checks: [],
            check_results: [],
            repository_head: null,
            changed_files_digest: null,
        },
        review: {
            review_result: null,
            review_status: null,
            approved: null,
            evidence_summary: null,
            changed_files: [],
            review_fingerprint: null,
            model_assisted_review: "Disabled",
        },
        verification_approval_status: "not_requested",
        commit_request: null,
        commit_result: {
            commit_sha: null,
            commit_message: null,
            committed_files: [],
            completion_time: null,
        },
        commit_approval_status: "not_requested",
        ...overrides,
    };
}

function renderTimeline(workflowDetail: WorkflowDetailResponse, options: { isRefreshing?: boolean; onRefresh?: () => void } = {}) {
    return render(
        <ExecutionTimeline workflow={workflowDetail} isRefreshing={options.isRefreshing ?? false} onRefresh={options.onRefresh ?? vi.fn()} />,
    );
}

describe("ExecutionTimeline", () => {
    it("renders timeline stages with plain-language labels and statuses", () => {
        renderTimeline(workflow());

        const stages = screen.getByRole("list", { name: "Change stages" });
        for (const stage of ["Change proposal", "Planning", "Change plan", "Workflow created", "Change approval", "Apply change", "Verify change", "Review results", "Commit"]) {
            expect(within(stages).getByText(stage, { exact: true })).toBeInTheDocument();
        }
        for (const internalName of ["Execution Candidate", "Planning Session", "Candidate Plan", "Implementation Approval", "Execution"]) {
            expect(within(stages).queryByText(internalName, { exact: true })).not.toBeInTheDocument();
        }
        expect(within(stages).getByText("Current step")).toBeInTheDocument();
        expect(within(stages).getAllByText("Not started").length).toBeGreaterThan(0);
    });

    it("renders waiting state", () => {
        renderTimeline(workflow());

        expect(screen.getAllByText("Waiting for implementation approval.").length).toBeGreaterThan(0);
        expect(within(screen.getByRole("list", { name: "Change stages" })).getAllByText("Not started").length).toBeGreaterThan(0);
    });

    it("does not present an unrecognized server stage status as not started", () => {
        renderTimeline(workflow({
            timeline: workflow().timeline.map((stage) => stage.name === "Execution" ? { ...stage, status: "unexpected" } : stage),
        }));

        const applyChange = screen.getByText("Apply change").closest("li");
        const stage = within(applyChange as HTMLElement);
        expect(stage.getByText("Status unavailable")).toBeInTheDocument();
        expect(stage.queryByText("Not started")).not.toBeInTheDocument();
    });

    it("uses maintenance terms for an operational workflow", () => {
        renderTimeline(workflow({
            effect_kind: "operational_action",
            workflow_state: "awaiting_implementation_approval",
            implementation_approval_status: "pending",
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
        }));

        expect(screen.getByRole("heading", { name: "Maintenance progress" })).toBeInTheDocument();
        const stages = screen.getByRole("list", { name: "Maintenance workflow stages" });
        for (const name of ["Proposal", "Planning", "Maintenance plan", "Workflow", "Maintenance request approval", "Run maintenance", "Verify result"]) {
            expect(within(stages).getByText(name, { exact: true })).toBeInTheDocument();
        }
        expect(within(stages).getAllByRole("listitem")).toHaveLength(7);
        expect(screen.getByText("Waiting for maintenance request approval.")).toBeInTheDocument();
        expect(screen.getByText("Check Maintenance status above for the outcome and verification.")).toBeInTheDocument();
        expect(screen.queryByRole("heading", { name: "Change progress" })).not.toBeInTheDocument();
        for (const internalName of ["Execution Candidate", "Planning Session", "Candidate Plan", "Implementation Approval", "Execution", "Verification", "Review", "Commit"]) {
            expect(within(stages).queryByText(internalName, { exact: true })).not.toBeInTheDocument();
        }
        expect(screen.queryByText(/exact action/i)).not.toBeInTheDocument();
    });

    it("describes a rejected operational decision as a rejected maintenance request", () => {
        renderTimeline(workflow({
            effect_kind: "operational_action",
            implementation_approval_status: "rejected",
        }));

        expect(screen.getByText("Maintenance request rejected.")).toBeInTheDocument();
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

    it("directs a blocked maintenance workflow to its status panel", () => {
        renderTimeline(workflow({ effect_kind: "operational_action", workflow_state: "blocked" }));

        expect(screen.getByText("Maintenance workflow is blocked. Review Maintenance status for details.")).toBeInTheDocument();
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
