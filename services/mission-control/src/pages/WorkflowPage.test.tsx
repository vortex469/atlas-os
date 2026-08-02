import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import {
    getWorkflowDetail,
    submitWorkflowImplementationApproval,
} from "../api/atlas-agent";
import { WorkflowPage } from "./WorkflowPage";
import type { WorkflowDetailResponse } from "../types/atlasAgent";

vi.mock("../api/atlas-agent", () => ({
    getAtlasAgentErrorMessage: (error: unknown, fallback: string) => error instanceof Error ? error.message : fallback,
    getWorkflowDetail: vi.fn(),
    submitWorkflowImplementationApproval: vi.fn(),
}));

const mockedGetWorkflowDetail = vi.mocked(getWorkflowDetail);
const mockedSubmitWorkflowImplementationApproval = vi.mocked(submitWorkflowImplementationApproval);

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
        affected_files: ["compose.yaml", "services/demo/Dockerfile"],
        implementation_request: {
            immutable_request_id: "impl-request-123",
            tool: "docker-compose",
            working_directory: "/opt/atlas/services/demo",
            affected_files: ["compose.yaml", "services/demo/Dockerfile"],
            repository: "/opt/atlas",
            translator_version: "candidate-translator-v1",
        },
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

function renderPage(path = "/workflows/workflow-123") {
    return render(
        <MemoryRouter initialEntries={[path]}>
            <Routes>
                <Route path="/workflows/:workflowId" element={<WorkflowPage />} />
            </Routes>
        </MemoryRouter>,
    );
}

describe("WorkflowPage", () => {
    beforeEach(() => {
        vi.clearAllMocks();
        mockedGetWorkflowDetail.mockResolvedValue(workflow());
    });

    it("renders workflow and immutable implementation request details", async () => {
        renderPage();

        expect(await screen.findByRole("heading", { name: /Workflow workflow-123/i })).toBeInTheDocument();
        expect(screen.getByText("candidate-plan-123")).toBeInTheDocument();
        expect(screen.getByText("candidate-123")).toBeInTheDocument();
        expect(screen.getByText("candidate-fingerprint-123")).toBeInTheDocument();
        expect(screen.getByText("plan-fingerprint-123")).toBeInTheDocument();
        expect(screen.getAllByText("/opt/atlas").length).toBeGreaterThan(0);
        expect(screen.getAllByText("/opt/atlas/services/demo").length).toBeGreaterThan(0);
        expect(screen.getAllByText("candidate-translator-v1").length).toBeGreaterThan(0);
        expect(screen.getByText("impl-request-123")).toBeInTheDocument();
        expect(screen.getByText("docker-compose")).toBeInTheDocument();
        expect(screen.getAllByText("compose.yaml, services/demo/Dockerfile").length).toBeGreaterThan(0);
    });

    it("submits approve with only workflow id and decision", async () => {
        mockedSubmitWorkflowImplementationApproval.mockResolvedValue({
            workflow_id: "workflow-123",
            workflow_state: "awaiting_execution",
            implementation_approval_status: "approved",
            message: null,
        });
        renderPage();

        fireEvent.click(await screen.findByRole("button", { name: "Approve Implementation" }));

        await screen.findByText("Implementation approved. Execution is now available.");
        expect(mockedSubmitWorkflowImplementationApproval).toHaveBeenCalledTimes(1);
        expect(mockedSubmitWorkflowImplementationApproval).toHaveBeenCalledWith("workflow-123", "approve");
        expect(JSON.stringify(mockedSubmitWorkflowImplementationApproval.mock.calls[0])).not.toMatch(/argv|command|repository|working_directory|implementation_request|candidate_snapshot/);
    });

    it("submits reject with only workflow id and decision", async () => {
        mockedSubmitWorkflowImplementationApproval.mockResolvedValue({
            workflow_id: "workflow-123",
            workflow_state: "implementation_rejected",
            implementation_approval_status: "rejected",
            message: null,
        });
        renderPage();

        fireEvent.click(await screen.findByRole("button", { name: "Reject" }));

        await screen.findByText("Approval rejected.");
        expect(mockedSubmitWorkflowImplementationApproval).toHaveBeenCalledWith("workflow-123", "reject");
    });

    it("shows pending state and blocks duplicate submissions", async () => {
        let resolveApproval: (value: Awaited<ReturnType<typeof submitWorkflowImplementationApproval>>) => void = () => undefined;
        mockedSubmitWorkflowImplementationApproval.mockReturnValue(new Promise((resolve) => {
            resolveApproval = resolve;
        }));
        renderPage();

        const approve = await screen.findByRole("button", { name: "Approve Implementation" });
        fireEvent.click(approve);
        fireEvent.click(approve);

        expect(await screen.findByText("Submitting approval...")).toBeInTheDocument();
        expect(mockedSubmitWorkflowImplementationApproval).toHaveBeenCalledTimes(1);
        resolveApproval({
            workflow_id: "workflow-123",
            workflow_state: "awaiting_execution",
            implementation_approval_status: "approved",
            message: null,
        });
        await screen.findByText("Implementation approved. Execution is now available.");
    });

    it("hides approval controls outside awaiting implementation approval", async () => {
        mockedGetWorkflowDetail.mockResolvedValue(workflow({
            workflow_state: "awaiting_execution",
            implementation_approval_status: "approved",
        }));
        renderPage();

        expect(await screen.findByText(/Approval controls are unavailable/i)).toBeInTheDocument();
        expect(screen.queryByRole("button", { name: "Approve Implementation" })).not.toBeInTheDocument();
        expect(screen.queryByRole("button", { name: "Reject" })).not.toBeInTheDocument();
    });

    it("renders workflow rail and no execution, verification, or commit controls", async () => {
        renderPage();

        expect(await screen.findByText("Implementation ✔")).toBeInTheDocument();
        expect(screen.getByText("Execution ✔")).toBeInTheDocument();
        expect(screen.getByText("Verification ○")).toBeInTheDocument();
        expect(screen.getByText("Commit ○")).toBeInTheDocument();
        expect(screen.queryByRole("button", { name: /execute/i })).not.toBeInTheDocument();
        expect(screen.queryByRole("button", { name: /verify/i })).not.toBeInTheDocument();
        expect(screen.queryByRole("button", { name: /commit/i })).not.toBeInTheDocument();
        expect(screen.queryByRole("textbox")).not.toBeInTheDocument();
    });

    it("shows workflow not found", async () => {
        mockedGetWorkflowDetail.mockResolvedValue(null);
        renderPage();

        expect(await screen.findByRole("alert")).toHaveTextContent("Workflow not found");
    });

    it("maps approval error states", async () => {
        mockedSubmitWorkflowImplementationApproval.mockRejectedValue(new Error("approval already approved"));
        renderPage();

        fireEvent.click(await screen.findByRole("button", { name: "Approve Implementation" }));

        expect(await screen.findByRole("alert")).toHaveTextContent("Approval already approved.");
    });
});
