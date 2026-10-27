import { fireEvent, render, screen } from "@testing-library/react";
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

        expect(screen.getAllByText("Execution failed.")).toHaveLength(2);
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
    it.each([
        { status: "failed", message: "Execution failed." },
        { status: "timed_out", message: "Execution timed out." },
        { status: "launch_failed", message: "Execution could not start." },
        { status: "unknown", message: "Worker outcome unknown. Check the original result; do not resubmit." },
        { status: "future_status", message: "Execution status is not recognized. Refresh to check its status." },
    ])("keeps the $status outcome consistent without a green completion message", ({ status, message }) => {
        const current = workflow();
        renderTimeline(workflow({ workflow_state: "blocked", implementation_approval_status: "approved", execution: { ...current.execution, execution_status: status, result: status } }));
        expect(screen.getAllByText(message)).toHaveLength(2);
        expect(screen.queryByText("Execution complete.")).not.toBeInTheDocument();
        expect(screen.queryByText("Execution running...")).not.toBeInTheDocument();
        expect(screen.getByRole("heading", { name: "Execution" }).parentElement!.querySelector('.text-emerald-200')).toBeNull();
    });

    it("shows only the reported terminal outcome when workflow state still says executing", () => {
        const current = workflow();
        renderTimeline(workflow({ workflow_state: "executing", implementation_approval_status: "approved", execution: { ...current.execution, execution_status: "succeeded", result: "succeeded" } }));
        expect(screen.getAllByText("Execution complete.")).toHaveLength(2);
        expect(screen.queryByText("Execution running...")).not.toBeInTheDocument();
    });

    it.each([
        { state: "awaiting_implementation_approval", approval: "approved", message: "Implementation approved. Waiting for a separate resume." },
        { state: "blocked", approval: "rejected", message: "Implementation approval was rejected." },
        { state: "blocked", approval: "approved", message: "Workflow is blocked. No execution result is reported." },
        { state: "completed", approval: "pending", message: "No execution result is reported." },
    ])("does not mistake missing execution evidence for approval waiting in $state/$approval", ({ state, approval, message }) => {
        renderTimeline(workflow({ workflow_state: state, implementation_approval_status: approval }));
        expect(screen.getAllByText(message)).toHaveLength(2);
        expect(screen.queryByText("Execution complete.")).not.toBeInTheDocument();
        expect(screen.queryByText("Execution unavailable.")).not.toBeInTheDocument();
    });

});
