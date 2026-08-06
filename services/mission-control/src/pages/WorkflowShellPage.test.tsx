import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { createCandidateImplementationRequest } from "../api/atlas-agent";
import type {
    CandidateImplementationTranslationResponse,
    CandidateWorkflowResponse,
} from "../types/atlasAgent";
import { WorkflowShellPage } from "./WorkflowShellPage";

vi.mock("../api/atlas-agent", () => ({
    createCandidateImplementationRequest: vi.fn(),
    getAtlasAgentErrorMessage: (error: unknown, fallback: string) =>
        error instanceof Error ? error.message : fallback,
}));

const mockedCreateCandidateImplementationRequest = vi.mocked(createCandidateImplementationRequest);

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

function implementationTranslationResponse(
    overrides: Partial<CandidateImplementationTranslationResponse> = {},
): CandidateImplementationTranslationResponse {
    return {
        candidate_planning_session_id: "candidate-plan-1",
        workflow_session_id: "workflow-1",
        translation_status: "implementation_ready",
        implementation_request_id: "implementation-1",
        exact_approval_request_id: "approval-1",
        candidate_fingerprint: "fingerprint-1",
        plan_fingerprint: "plan-fingerprint-1",
        repository_head: "head-1",
        translator_version: "candidate-update-compose-stack-v1",
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
                <Route path="/workflows/:workflowId" element={<div>Workflow detail</div>} />
            </Routes>
        </MemoryRouter>,
    );
}

describe("WorkflowShellPage", () => {
    beforeEach(() => {
        vi.resetAllMocks();
        mockedCreateCandidateImplementationRequest.mockResolvedValue(
            implementationTranslationResponse(),
        );
    });

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

    it("renders a create implementation request button for awaiting_approval shells", async () => {
        const user = userEvent.setup();
        const currentWorkflow = workflow({
            workflow_status: "awaiting_approval",
            conversion_status: "workflow_created",
            implementation_approval_request_id: "approval-shell",
        });
        renderPage({ workflow: currentWorkflow });

        expect(screen.getByText("Create implementation request")).toBeInTheDocument();
        const button = screen.getByRole("button", { name: /create implementation request/i });

        await user.click(button);

        expect(mockedCreateCandidateImplementationRequest).toHaveBeenCalledWith(
            "candidate-plan-1",
            {
                expected_candidate_fingerprint: currentWorkflow.candidate_fingerprint,
                expected_plan_fingerprint: currentWorkflow.candidate_plan_fingerprint,
            },
        );
        expect(await screen.findByText("Workflow detail")).toBeInTheDocument();
    });

    it("blocks duplicate implementation request submissions", async () => {
        const user = userEvent.setup();
        let resolveRequest!: (value: CandidateImplementationTranslationResponse) => void;
        mockedCreateCandidateImplementationRequest.mockReturnValue(
            new Promise((resolve) => {
                resolveRequest = resolve;
            }),
        );

        renderPage({
            workflow: workflow({
                workflow_status: "awaiting_approval",
                implementation_approval_request_id: "approval-shell",
            }),
        });

        const button = screen.getByRole("button", { name: /create implementation request/i });
        await user.dblClick(button);

        expect(mockedCreateCandidateImplementationRequest).toHaveBeenCalledTimes(1);
        expect(screen.getByRole("button", { name: /creating implementation request/i })).toBeDisabled();
        resolveRequest(implementationTranslationResponse());
    });

    it("shows an error when creating the implementation request fails", async () => {
        const user = userEvent.setup();
        mockedCreateCandidateImplementationRequest.mockRejectedValueOnce(new Error("Implementation unavailable"));

        renderPage({
            workflow: workflow({
                workflow_status: "awaiting_approval",
                implementation_approval_request_id: "approval-shell",
            }),
        });

        await user.click(screen.getByRole("button", { name: /create implementation request/i }));

        expect(await screen.findByRole("alert")).toHaveTextContent("Implementation unavailable");
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
