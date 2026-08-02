import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it } from "vitest";

import type { CandidateWorkflowResponse } from "../types/atlasAgent";
import { WorkflowShellPage } from "./WorkflowShellPage";

function workflow(overrides: Partial<CandidateWorkflowResponse> = {}): CandidateWorkflowResponse {
    return {
        candidate_planning_session_id: "candidate-plan-1",
        candidate_id: "candidate-1",
        candidate_fingerprint: "fingerprint-1",
        candidate_plan_id: "plan-1",
        candidate_plan_fingerprint: "plan-fingerprint-1",
        workflow_session_id: "workflow-1",
        workflow_status: "approval_pending",
        implementation_approval_request_id: "approval-1",
        conversion_status: "workflow_created",
        core_revalidation_status: "accepted_for_planning",
        reason_codes: [],
        failure: null,
        ...overrides,
    };
}

function renderPage(state?: { workflow: CandidateWorkflowResponse }) {
    return render(
        <MemoryRouter initialEntries={[{ pathname: "/candidate-planning/candidate-plan-1/workflow", state }]}>
            <Routes>
                <Route path="/candidate-planning/:sessionId/workflow" element={<WorkflowShellPage />} />
            </Routes>
        </MemoryRouter>,
    );
}

describe("WorkflowShellPage", () => {
    it("renders a read-only workflow summary from route state", () => {
        renderPage({ workflow: workflow() });

        expect(screen.getByRole("heading", { name: "Workflow workflow-1" })).toBeInTheDocument();
        expect(screen.getAllByText("Workflow created.").length).toBeGreaterThan(0);
        expect(screen.getByText("workflow-1")).toBeInTheDocument();
        expect(screen.getByText("Atlas Agent candidate planning")).toBeInTheDocument();
        expect(screen.getAllByText("Approval Pending").length).toBeGreaterThan(0);
        expect(screen.getByText("candidate-1")).toBeInTheDocument();
        expect(screen.getByText("fingerprint-1")).toBeInTheDocument();
        expect(screen.getByText("plan-fingerprint-1")).toBeInTheDocument();
        expect(screen.getByText("Pending")).toBeInTheDocument();
        expect(screen.getByText("candidate-plan-1")).toBeInTheDocument();
        expect(screen.getByText("Not exposed by Atlas Agent API")).toBeInTheDocument();
        expect(screen.getByText("Workflow ✔")).toBeInTheDocument();
        expect(screen.getByText("Implementation ○")).toBeInTheDocument();
        expect(screen.getByText("Verification ○")).toBeInTheDocument();
        expect(screen.getByText("Review ○")).toBeInTheDocument();
        expect(screen.getByText("Commit ○")).toBeInTheDocument();
        expect(screen.queryByRole("button", { name: /approve|execute|implementation|verify|review|commit/i })).not.toBeInTheDocument();
        expect(screen.queryByText(/argv|commands|execution metadata/i)).not.toBeInTheDocument();
    });

    it("renders an unavailable state when opened without creation response", () => {
        renderPage();

        expect(screen.getByRole("alert")).toHaveTextContent("Workflow summary unavailable");
        expect(screen.getByRole("link", { name: "Back to planning session" })).toHaveAttribute(
            "href",
            "/candidate-planning/candidate-plan-1",
        );
    });

    it("renders workflow conversion failure summaries without controls", () => {
        renderPage({
            workflow: workflow({
                workflow_session_id: null,
                workflow_status: null,
                conversion_status: "stale_before_workflow",
                implementation_approval_request_id: null,
                reason_codes: ["stale"],
                failure: { code: "candidate_stale", message: "Candidate changed" },
            }),
        });

        expect(screen.getByRole("heading", { name: "Workflow not created" })).toBeInTheDocument();
        expect(screen.getByText("Stale candidate.")).toBeInTheDocument();
        expect(screen.getByText("Reason codes: stale")).toBeInTheDocument();
        expect(screen.getByText("Failure: candidate_stale - Candidate changed")).toBeInTheDocument();
        expect(screen.queryByRole("button", { name: /approve|execute|implementation|commit/i })).not.toBeInTheDocument();
    });
});
