import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { getWorkflowAudit } from "../api/atlas-agent";
import type { WorkflowAuditResponse } from "../types/atlasAgent";
import { WorkflowAuditPage } from "./WorkflowAuditPage";

vi.mock("../api/atlas-agent", () => ({
    getAtlasAgentErrorMessage: (error: unknown, fallback: string) => error instanceof Error ? error.message : fallback,
    getWorkflowAudit: vi.fn(),
}));

const mockedGetWorkflowAudit = vi.mocked(getWorkflowAudit);

function audit(overrides: Partial<WorkflowAuditResponse> = {}): WorkflowAuditResponse {
    return {
        workflow_id: "workflow-123",
        workflow_state: "completed",
        workflow_source: "candidate",
        validation: {
            valid: true,
            failure_code: null,
            failure_stage: null,
        },
        timeline: [
            { name: "candidate", status: "completed" },
            { name: "planning", status: "completed" },
            { name: "plan", status: "completed" },
            { name: "workflow", status: "completed" },
            { name: "implementation", status: "completed" },
            { name: "approvals", status: "completed" },
            { name: "execution", status: "completed" },
            { name: "verification", status: "completed" },
            { name: "review", status: "completed" },
            { name: "commit", status: "completed" },
        ],
        candidate: {
            status: "completed",
            candidate_id: "candidate-123",
            candidate_fingerprint: "cand-fingerprint",
            source_recommendation_id: "rec-123",
            target_id: "target-1",
            target_type: "service",
        },
        planning: {
            status: "completed",
            planning_session_id: "plan-session-123",
            planning_state: "completed",
            planning_status: "approved",
            created_at: "2026-08-01T10:00:00Z",
            planning_completed_at: "2026-08-01T10:00:30Z",
            candidate_plan_id: "candidate-plan-123",
            candidate_plan_fingerprint: "plan-fingerprint",
        },
        plan: {
            status: "completed",
            plan_id: "plan-123",
            candidate_plan_fingerprint: "plan-fingerprint",
            likely_affected_files: ["compose.yaml", "services/demo/Dockerfile"],
        },
        workflow: {
            status: "completed",
            workflow_id: "workflow-123",
            workflow_source: "candidate",
            workflow_state: "completed",
        },
        implementation: {
            status: "completed",
            implementation_request_id: "impl-123",
            execution_intent: "compose up",
            tool: "docker-compose",
            repository_root: "/opt/atlas",
            repository_head: "abc123",
            repository_branch: "feature/atlas-agent",
            working_directory: "/opt/atlas/services/demo",
            affected_files: ["compose.yaml", "services/demo/Dockerfile"],
            translator_version: "translator-v1",
        },
        approvals: {
            status: "completed",
            implementation: {
                status: "approved",
                approval_id: "approval-impl-123",
            },
            verification: {
                status: "approved",
                approval_id: "approval-verif-123",
            },
            commit: {
                status: "approved",
                approval_id: "approval-commit-123",
            },
        },
        execution: {
            status: "completed",
            execution_request_id: "exec-123",
            execution_status: "succeeded",
            changed_files_count: 2,
            changed_files: ["compose.yaml", "services/demo/Dockerfile"],
            tool: "docker-compose",
            repository: "/opt/atlas",
        },
        verification: {
            status: "completed",
            verification_plan_id: "ver-plan-123",
            verification_evidence_id: "ver-evidence-123",
            verification_status: "passed",
            changed_files_digest: "digest-123",
            verification_check_ids: ["check-a", "check-b"],
            repository_head: "abc123",
            verification_started_at: "2026-08-01T10:01:00Z",
            verification_completed_at: "2026-08-01T10:02:00Z",
        },
        review: {
            status: "completed",
            review_result_id: "rev-123",
            review_report_id: "rep-123",
            review_status: "approved",
            reviewed_content_fingerprint: "review-fingerprint",
            changed_files: ["compose.yaml"],
        },
        commit: {
            status: "completed",
            commit_request_id: "commit-req-123",
            reviewed_files: ["compose.yaml"],
            reviewed_content_fingerprint: "review-fingerprint",
            expected_branch: "feature/atlas-agent",
            expected_head: "abc123",
            commit_message: "feat(compose): update",
            commit_sha: "def456",
            committed_files: ["compose.yaml"],
        },
        ...overrides,
    };
}

function renderAuditPage(path = "/workflows/workflow-123/audit") {
    return render(
        <MemoryRouter initialEntries={[path]}>
            <Routes>
                <Route path="/workflows/:workflowId/audit" element={<WorkflowAuditPage />} />
            </Routes>
        </MemoryRouter>,
    );
}

describe("WorkflowAuditPage", () => {
    beforeEach(() => {
        vi.clearAllMocks();
        mockedGetWorkflowAudit.mockResolvedValue(audit());
    });

    it("renders completed audit chain", async () => {
        renderAuditPage();

        expect(await screen.findByRole("heading", { name: /Workflow workflow-123/i })).toBeInTheDocument();
        expect(screen.getByText("Workflow Audit")).toBeInTheDocument();
        expect(screen.getByText("candidate-123")).toBeInTheDocument();
        expect(screen.getByText("def456")).toBeInTheDocument();
        expect(screen.getByText("Commit SHA")).toBeInTheDocument();
        expect(screen.getAllByText("Completed").length).toBeGreaterThan(0);
    });

    it("shows in-progress stages as Not reached", async () => {
        mockedGetWorkflowAudit.mockResolvedValue(audit({
            workflow_state: "awaiting_verification_approval",
            timeline: [
                { name: "candidate", status: "completed" },
                { name: "planning", status: "completed" },
                { name: "plan", status: "completed" },
                { name: "workflow", status: "completed" },
                { name: "implementation", status: "completed" },
                { name: "approvals", status: "completed" },
                { name: "execution", status: "completed" },
                { name: "verification", status: "current" },
                { name: "review", status: "not_reached" },
                { name: "commit", status: "not_reached" },
            ],
        }));
        renderAuditPage();

        expect(await screen.findByText("Stage status")).toBeInTheDocument();
        expect(screen.getAllByText(/Not reached/i).length).toBeGreaterThan(0);
        expect(screen.getAllByText(/Review Result/i).length).toBeGreaterThan(0);
    });

    it("shows missing artifact alert", async () => {
        mockedGetWorkflowAudit.mockResolvedValue(audit({
            timeline: [
                { name: "candidate", status: "completed" },
                { name: "planning", status: "completed" },
                { name: "plan", status: "completed" },
                { name: "workflow", status: "completed" },
                { name: "implementation", status: "missing" },
                { name: "approvals", status: "not_reached" },
                { name: "execution", status: "not_reached" },
                { name: "verification", status: "not_reached" },
                { name: "review", status: "not_reached" },
                { name: "commit", status: "not_reached" },
            ],
            implementation: {
                ...audit().implementation,
                implementation_request_id: null,
            },
        }));
        renderAuditPage();

        expect(await screen.findByText("Required artifact is missing.")).toBeInTheDocument();
    });

    it("shows inconsistent alert for failed validation", async () => {
        mockedGetWorkflowAudit.mockResolvedValue(audit({
            validation: {
                valid: false,
                failure_code: "candidate_plan_mismatch",
                failure_stage: "candidate",
            },
            timeline: [
                { name: "candidate", status: "invalid" },
                { name: "planning", status: "current" },
                { name: "plan", status: "not_reached" },
                { name: "workflow", status: "not_reached" },
                { name: "implementation", status: "not_reached" },
                { name: "approvals", status: "not_reached" },
                { name: "execution", status: "not_reached" },
                { name: "verification", status: "not_reached" },
                { name: "review", status: "not_reached" },
                { name: "commit", status: "not_reached" },
            ],
        }));
        renderAuditPage();

        expect(await screen.findByText(/Inconsistent audit:\s*candidate_plan_mismatch/i)).toBeInTheDocument();
        expect(screen.getByText("This stage is inconsistent with audit-chain validation.")).toBeInTheDocument();
        expect((await screen.findAllByText(/Inconsistent/i)).length).toBeGreaterThan(1);
    });

    it("shows workflow not found", async () => {
        mockedGetWorkflowAudit.mockResolvedValue(null);
        renderAuditPage("/workflows/workflow-missing/audit");

        expect(await screen.findByRole("alert")).toHaveTextContent("Workflow not found");
    });

    it("shows agent unavailable alert", async () => {
        mockedGetWorkflowAudit.mockRejectedValue(new Error("Atlas Agent unavailable."));
        renderAuditPage();

        expect(await screen.findByRole("alert")).toHaveTextContent("Atlas Agent unavailable.");
    });

    it("renders back to workflow link", async () => {
        renderAuditPage();

        expect(await screen.findByRole("link", { name: "← Back to Workflow" })).toHaveAttribute(
            "href",
            "/workflows/workflow-123",
        );
    });

    it("renders no mutation controls", async () => {
        renderAuditPage();

        expect(await screen.findByRole("heading", { name: "Candidate" })).toBeInTheDocument();
        expect(screen.queryByRole("button", { name: /approve/i })).not.toBeInTheDocument();
        expect(screen.queryByRole("button", { name: /reject/i })).not.toBeInTheDocument();
        expect(screen.queryByRole("button", { name: /execute/i })).not.toBeInTheDocument();
        expect(screen.queryByRole("button", { name: /resume/i })).not.toBeInTheDocument();
        expect(screen.queryByRole("button", { name: /commit/i })).not.toBeInTheDocument();
    });
});
