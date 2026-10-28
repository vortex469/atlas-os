import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { createMemoryRouter, MemoryRouter, Route, RouterProvider, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { StrictMode } from "react";

import {
    getWorkflowDetail,
    getWorkflowOperationalLifecycle,
    getWorkflowRecoveryDiagnostic,
    getWorkflowSupportBundle,
    resumeWorkflow,
    submitWorkflowCommitApproval,
    submitWorkflowImplementationApproval,
    submitWorkflowVerificationApproval,
} from "../api/atlas-agent";
import { WorkflowPage } from "./WorkflowPage";
import type { WorkflowDetailResponse, WorkflowRecoveryDiagnostic } from "../types/atlasAgent";
import { operationalDiagnostic, operationalLifecycle } from "../test/operationalLifecycle";
import { operationalActionRequest } from "../test/operationalPlanning";
import { workflowDetail as workflow } from "../test/workflowDetail";

vi.mock("../api/atlas-agent", () => ({
    getAtlasAgentErrorMessage: (error: unknown, fallback: string) => error instanceof Error ? error.message : fallback,
    getWorkflowDetail: vi.fn(),
    getWorkflowOperationalLifecycle: vi.fn(),
    getWorkflowRecoveryDiagnostic: vi.fn(),
    getWorkflowSupportBundle: vi.fn(),
    resumeWorkflow: vi.fn(),
    submitWorkflowCommitApproval: vi.fn(),
    submitWorkflowImplementationApproval: vi.fn(),
    submitWorkflowVerificationApproval: vi.fn(),
}));

const mockedGetWorkflowDetail = vi.mocked(getWorkflowDetail);
const mockedGetWorkflowOperationalLifecycle = vi.mocked(getWorkflowOperationalLifecycle);
const mockedGetWorkflowRecoveryDiagnostic = vi.mocked(getWorkflowRecoveryDiagnostic);
const mockedGetWorkflowSupportBundle = vi.mocked(getWorkflowSupportBundle);
const mockedResumeWorkflow = vi.mocked(resumeWorkflow);
const mockedSubmitWorkflowCommitApproval = vi.mocked(submitWorkflowCommitApproval);
const mockedSubmitWorkflowImplementationApproval = vi.mocked(submitWorkflowImplementationApproval);
const mockedSubmitWorkflowVerificationApproval = vi.mocked(submitWorkflowVerificationApproval);

function workflowAwaitingCommit(overrides: Partial<WorkflowDetailResponse> = {}): WorkflowDetailResponse {
    return workflow({
        workflow_state: "awaiting_commit_approval",
        commit_approval_status: "pending",
        commit_request: {
            commit_request_id: "approval-commit-workflow-123",
            repository: "/opt/atlas",
            branch: "feature/atlas-agent",
            expected_head: "abc123",
            commit_message: "feat(compose): update stack",
            reviewed_files: ["compose.yaml", "services/demo/Dockerfile"],
            reviewed_content_fingerprint: "reviewed-fingerprint-123",
            commit_approval_status: "pending",
        },
        timeline: [
            { name: "Execution Candidate", status: "completed" },
            { name: "Planning Session", status: "completed" },
            { name: "Candidate Plan", status: "completed" },
            { name: "Workflow", status: "completed" },
            { name: "Implementation Approval", status: "completed" },
            { name: "Execution", status: "completed" },
            { name: "Verification", status: "completed" },
            { name: "Review", status: "completed" },
            { name: "Commit", status: "current" },
        ],
        ...overrides,
    });
}

function workflowAwaitingVerification(overrides: Partial<WorkflowDetailResponse> = {}): WorkflowDetailResponse {
    return workflow({
        workflow_state: "awaiting_verification_approval",
        verification_approval_status: "approved",
        ...overrides,
    });
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
    it.each([
        ["executing", workflow({ workflow_state: "executing" }), "Implementation is running."],
        ["commit approval", workflow({ workflow_state: "awaiting_commit_approval" }), "Commit needs approval."],
        ["completed", workflow({ workflow_state: "completed" }), "Workflow completed."],
        ["unknown", workflow({ workflow_state: "unexpected_state" }), "Current workflow status is unavailable. Review Workflow details."],
    ])("summarizes the %s state in plain language", async (_name, fixture, message) => {
        mockedGetWorkflowDetail.mockResolvedValue(fixture);
        renderPage();

        const summary = within(await screen.findByRole("region", { name: "Workflow summary" }));
        expect(summary.getByText(message, { exact: true })).toBeVisible();
    });

    it("keeps approval and resume controls hidden when workflow details are unreadable", async () => {
        mockedGetWorkflowDetail.mockRejectedValue(new Error("Malformed workflow detail payload."));
        renderPage();

        const alert = await screen.findByRole("alert");
        expect(alert).toHaveTextContent("Workflow unavailable");
        expect(alert).toHaveTextContent("Mission Control could not read this workflow response. Refresh to try again.");
        const technicalDetails = within(alert).getByText("Technical details").closest("details");
        expect(technicalDetails).not.toHaveAttribute("open");
        expect(within(technicalDetails as HTMLElement).getByText("Malformed workflow detail payload.")).not.toBeVisible();
        expect(screen.queryByRole("button", { name: "Approve Implementation" })).not.toBeInTheDocument();
        expect(screen.queryByRole("button", { name: "Resume Approved Implementation" })).not.toBeInTheDocument();
        expect(mockedSubmitWorkflowImplementationApproval).not.toHaveBeenCalled();
        expect(mockedResumeWorkflow).not.toHaveBeenCalled();
    });

    it("keeps workflow request errors in collapsed technical details", async () => {
        mockedGetWorkflowDetail.mockRejectedValue(new Error("Network Error"));
        renderPage();

        const alert = await screen.findByRole("alert");
        expect(alert).toHaveTextContent("Mission Control could not load this workflow, so its current status is unknown.");
        const technicalDetails = within(alert).getByText("Technical details").closest("details");
        expect(technicalDetails).not.toHaveAttribute("open");
        expect(within(technicalDetails as HTMLElement).getByText("Network Error")).not.toBeVisible();
        expect(within(alert).getByRole("button", { name: "Try again" })).toBeVisible();
        expect(screen.getByRole("link", { name: "← All workflows" })).toHaveAttribute("href", "/workflows");
        expect(screen.queryByRole("button", { name: "Approve Implementation" })).not.toBeInTheDocument();
    });

    it("shows the exact maintenance request before offering action approval", async () => {
        mockedGetWorkflowDetail.mockResolvedValue(workflow({ effect_kind: "operational_action" }));
        renderPage();
        await screen.findByRole("heading", { name: "Maintenance request" });
        expect(screen.getByText("Maintenance action needs approval.", { exact: true })).toBeVisible();
        expect(screen.getByText("Temporary service interruption.")).toBeVisible();
        expect(screen.getByText("2999-01-01T12:00:00Z")).toBeVisible();
        expect(screen.getByText(/Stop and require operator review/)).toBeVisible();
        expect(screen.getByRole("button", { name: "Approve maintenance request" })).toBeEnabled();
        expect(screen.getByRole("button", { name: "Reject maintenance request" })).toBeEnabled();
        expect(screen.getByText(/Approval does not run it; choose Run approved maintenance separately/)).toBeVisible();
        expect(mockedSubmitWorkflowImplementationApproval).not.toHaveBeenCalled();
    });

    it.each(["missing", "invalid", "unselected authority"])("does not offer approval when exact maintenance request is %s", async (kind) => {
        const request = kind === "missing" ? null : kind === "invalid"
            ? operationalActionRequest({ verification: { ...operationalActionRequest().verification, pre_state: "different-state" } })
            : { ...operationalActionRequest(), execution_enabled: true } as unknown as WorkflowDetailResponse["operational_action_request"];
        mockedGetWorkflowDetail.mockResolvedValue(workflow({ effect_kind: "operational_action", operational_action_request: request }));
        renderPage();
        await screen.findByRole("heading", { name: "Maintenance request unavailable" });
        expect(screen.queryByRole("button", { name: "Approve maintenance request" })).not.toBeInTheDocument();
        expect(mockedSubmitWorkflowImplementationApproval).not.toHaveBeenCalled();
    });

    it.each(["expired", "historical", "superseded", "preparation-only"])("does not inherit exact action approval from %s presentation", async (kind) => {
        const presentations: WorkflowDetailResponse["approval_presentations"] = [{ approval_id: "other-approval",
            purpose: kind === "preparation-only" ? "candidate_workflow_shell" : "operational_action", decision_status: "pending",
            presentation_state: kind === "preparation-only" ? "actionable" : kind as "expired" | "historical" | "superseded",
            actionable: kind === "preparation-only", reason: "Not a current exact action decision." }];
        mockedGetWorkflowDetail.mockResolvedValue(workflow({ effect_kind: "operational_action", approval_presentations: presentations }));
        renderPage();
        await screen.findByRole("heading", { name: "Maintenance request" });
        expect(screen.queryByRole("button", { name: "Approve maintenance request" })).not.toBeInTheDocument();
        expect(mockedSubmitWorkflowImplementationApproval).not.toHaveBeenCalled();
    });

    it("requires a reviewable exact request before resuming an approved maintenance stage", async () => {
        mockedGetWorkflowDetail.mockResolvedValue(workflow({ effect_kind: "operational_action", operational_action_request: null, implementation_approval_status: "approved" }));
        renderPage();
        await screen.findByRole("heading", { name: "Maintenance request unavailable" });
        expect(screen.queryByRole("button", { name: "Run approved maintenance" })).not.toBeInTheDocument();
        expect(mockedResumeWorkflow).not.toHaveBeenCalled();
    });

    it("pauses maintenance status checks while an approval is pending", async () => {
        vi.useFakeTimers();
        const initial = workflow({ effect_kind: "operational_action" });
        mockedGetWorkflowDetail.mockResolvedValueOnce(initial)
            .mockResolvedValue(workflow({ effect_kind: "operational_action", implementation_approval_status: "approved" }));
        mockedGetWorkflowOperationalLifecycle.mockResolvedValue(operationalLifecycle({ workflow_id: "workflow-123", terminal: false }));
        let resolveApproval!: (value: { workflow_id: string; workflow_state: string; implementation_approval_status: string; message: null }) => void;
        mockedSubmitWorkflowImplementationApproval.mockImplementationOnce(() => new Promise((resolve) => { resolveApproval = resolve; }));
        const view = renderPage();
        try {
            await act(async () => {});
            fireEvent.click(screen.getByRole("button", { name: "Approve maintenance request" }));
            expect(screen.getByRole("button", { name: "Refresh" })).toBeDisabled();
            await act(async () => vi.advanceTimersByTime(10_000));
            expect(mockedGetWorkflowDetail).toHaveBeenCalledTimes(1);
            await act(async () => resolveApproval({ workflow_id: "workflow-123", workflow_state: "awaiting_implementation_approval", implementation_approval_status: "approved", message: null }));
            expect(mockedGetWorkflowDetail).toHaveBeenCalledTimes(2);
            expect(screen.getByText("Maintenance request approved. Run it when you are ready.")).toBeVisible();
            expect(mockedResumeWorkflow).not.toHaveBeenCalled();
        } finally {
            view.unmount();
            vi.useRealTimers();
        }
    });

    it("does not replace the displayed workflow until its companion reads have finished", async () => {
        const initial = workflow({ effect_kind: "operational_action" });
        mockedGetWorkflowDetail.mockResolvedValueOnce(initial).mockResolvedValue(workflow({ effect_kind: "operational_action", workflow_state: "completed" }));
        renderPage();
        await screen.findByRole("button", { name: "Approve maintenance request" });
        let resolveDiagnostic!: (value: WorkflowRecoveryDiagnostic | null) => void;
        mockedGetWorkflowRecoveryDiagnostic.mockImplementationOnce(() => new Promise((resolve) => { resolveDiagnostic = resolve; }));
        fireEvent.click(screen.getByRole("button", { name: "Refresh" }));
        await waitFor(() => expect(mockedGetWorkflowRecoveryDiagnostic).toHaveBeenCalledTimes(2));
        expect(screen.getByRole("button", { name: "Approve maintenance request" })).toBeDisabled();
        await act(async () => resolveDiagnostic(null));
        expect(screen.queryByRole("button", { name: "Approve maintenance request" })).not.toBeInTheDocument();
        expect(screen.queryByText("Loading recovery diagnostic...")).not.toBeInTheDocument();
        expect(mockedSubmitWorkflowImplementationApproval).not.toHaveBeenCalled();
    });

    it.each(["lifecycle", "diagnostic"])("does not display %s evidence from another workflow", async (kind) => {
        mockedGetWorkflowDetail.mockResolvedValue(workflow({ effect_kind: "operational_action" }));
        if (kind === "lifecycle") mockedGetWorkflowOperationalLifecycle.mockResolvedValue(operationalLifecycle({ workflow_id: "different-workflow" }));
        else mockedGetWorkflowRecoveryDiagnostic.mockResolvedValue(operationalDiagnostic());
        renderPage();
        const message = kind === "lifecycle" ? "The operational lifecycle response does not match this workflow." : "The recovery diagnostic response does not match this workflow.";
        const messageElement = await screen.findByText(message);
        if (kind === "lifecycle") {
            expect(messageElement.closest("details")).not.toHaveAttribute("open");
            expect(messageElement).not.toBeVisible();
        } else {
            expect(messageElement).toBeVisible();
        }
        expect(screen.queryByText("different-workflow")).not.toBeInTheDocument();
        expect(screen.queryByText("Loading recovery diagnostic...")).not.toBeInTheDocument();
    });

    it.each(["implementation", "verification", "commit"] as const)("disables %s approval while current status is being checked", async (stage) => {
        const initial = stage === "implementation" ? workflow() : stage === "verification" ? workflowAwaitingVerification({ verification_approval_status: "pending" }) : workflowAwaitingCommit();
        let resolveRead!: (value: WorkflowDetailResponse) => void;
        mockedGetWorkflowDetail.mockResolvedValueOnce(initial).mockImplementationOnce(() => new Promise((resolve) => { resolveRead = resolve; }));
        renderPage();
        const name = stage === "implementation" ? "Approve Implementation" : stage === "verification" ? "Approve Verification" : "Approve Commit";
        const approve = await screen.findByRole("button", { name });
        fireEvent.click(screen.getByRole("button", { name: "Refresh" }));
        await waitFor(() => expect(mockedGetWorkflowDetail).toHaveBeenCalledTimes(2));
        expect(approve).toBeDisabled();
        fireEvent.click(approve);
        expect(mockedSubmitWorkflowImplementationApproval).not.toHaveBeenCalled();
        expect(mockedSubmitWorkflowVerificationApproval).not.toHaveBeenCalled();
        expect(mockedSubmitWorkflowCommitApproval).not.toHaveBeenCalled();
        await act(async () => resolveRead(initial));
        expect(await screen.findByRole("button", { name })).toBeEnabled();
    });

    it.each(["implementation", "verification", "commit"] as const)("refreshes %s state when an approval request errors", async (stage) => {
        let initial: WorkflowDetailResponse;
        let decided: WorkflowDetailResponse;
        let buttonName: string;
        let expectedFailureMessage: string;
        if (stage === "implementation") {
            initial = workflow();
            decided = workflow({ workflow_state: "awaiting_execution", implementation_approval_status: "approved" });
            buttonName = "Approve Implementation";
            expectedFailureMessage = "Mission Control could not confirm the implementation approval decision.";
            mockedSubmitWorkflowImplementationApproval.mockRejectedValueOnce(new Error("Approval already decided"));
        } else if (stage === "verification") {
            initial = workflowAwaitingVerification({ verification_approval_status: "pending" });
            decided = workflowAwaitingVerification({ verification_approval_status: "approved" });
            buttonName = "Approve Verification";
            expectedFailureMessage = "Mission Control could not confirm the verification approval decision.";
            mockedSubmitWorkflowVerificationApproval.mockRejectedValueOnce(new Error("Approval already decided"));
        } else {
            initial = workflowAwaitingCommit();
            decided = workflowAwaitingCommit({ workflow_state: "committing", commit_approval_status: "approved" });
            buttonName = "Approve Commit";
            expectedFailureMessage = "Mission Control could not confirm the commit approval decision.";
            mockedSubmitWorkflowCommitApproval.mockRejectedValueOnce(new Error("Approval already decided"));
        }
        mockedGetWorkflowDetail.mockResolvedValueOnce(initial).mockResolvedValueOnce(decided);
        renderPage();

        fireEvent.click(await screen.findByRole("button", { name: buttonName }));

        expect(await screen.findByText(new RegExp(expectedFailureMessage))).toBeVisible();
        const technicalDetails = screen.getByText("Technical details").closest("details");
        expect(technicalDetails).not.toHaveAttribute("open");
        expect(technicalDetails).toHaveTextContent("Approval already decided");
        await waitFor(() => expect(mockedGetWorkflowDetail).toHaveBeenCalledTimes(2));
        expect(screen.queryByRole("button", { name: buttonName })).not.toBeInTheDocument();
    });

    it.each(["implementation", "verification", "commit"] as const)("disables %s resume while current status is being checked", async (stage) => {
        const initial = stage === "implementation" ? workflow({ implementation_approval_status: "approved" })
            : stage === "verification" ? workflowAwaitingVerification({ verification_approval_status: "approved" })
                : workflowAwaitingCommit({ commit_approval_status: "approved" });
        let resolveRead!: (value: WorkflowDetailResponse) => void;
        mockedGetWorkflowDetail.mockResolvedValueOnce(initial).mockImplementationOnce(() => new Promise((resolve) => { resolveRead = resolve; }));
        renderPage();
        const name = `Resume Approved ${stage[0].toUpperCase()}${stage.slice(1)}`;
        const resume = await screen.findByRole("button", { name });
        fireEvent.click(screen.getByRole("button", { name: "Refresh" }));
        await waitFor(() => expect(mockedGetWorkflowDetail).toHaveBeenCalledTimes(2));
        expect(resume).toBeDisabled();
        fireEvent.click(resume);
        expect(mockedResumeWorkflow).not.toHaveBeenCalled();
        await act(async () => resolveRead(initial));
        expect(await screen.findByRole("button", { name })).toBeEnabled();
    });

    it("waits for a slow automatic read before checking again", async () => {
        vi.useFakeTimers();
        const running = workflow({ workflow_state: "executing", implementation_approval_status: "approved" });
        let resolveRead!: (value: WorkflowDetailResponse) => void;
        mockedGetWorkflowDetail.mockResolvedValueOnce(running)
            .mockImplementationOnce(() => new Promise((resolve) => { resolveRead = resolve; }))
            .mockResolvedValue(workflowAwaitingVerification({ implementation_approval_status: "approved", verification_approval_status: "pending" }));
        const view = renderPage();
        try {
            await act(async () => {});
            expect(mockedGetWorkflowDetail).toHaveBeenCalledTimes(1);
            await act(async () => vi.advanceTimersByTime(5_000));
            expect(mockedGetWorkflowDetail).toHaveBeenCalledTimes(2);
            await act(async () => vi.advanceTimersByTime(10_000));
            expect(mockedGetWorkflowDetail).toHaveBeenCalledTimes(2);
            await act(async () => resolveRead(running));
            await act(async () => vi.advanceTimersByTime(5_000));
            expect(mockedGetWorkflowDetail).toHaveBeenCalledTimes(3);
            expect(screen.getByRole("button", { name: "Approve Verification" })).toBeEnabled();
            expect(mockedResumeWorkflow).not.toHaveBeenCalled();
        } finally {
            view.unmount();
            vi.useRealTimers();
        }
    });

    it("does not announce resumable execution when the refreshed workflow still reports pending approval", async () => {
        mockedSubmitWorkflowImplementationApproval.mockResolvedValue({
            workflow_id: "workflow-123", workflow_state: "awaiting_implementation_approval",
            implementation_approval_status: "approved", message: null,
        });
        renderPage();
        fireEvent.click(await screen.findByRole("button", { name: "Approve Implementation" }));
        await waitFor(() => expect(mockedGetWorkflowDetail).toHaveBeenCalledTimes(2));
        expect(screen.queryByText("Implementation approved. Resume to run this change.")).not.toBeInTheDocument();
        expect(screen.queryByRole("button", { name: "Resume Approved Implementation" })).not.toBeInTheDocument();
        expect(mockedResumeWorkflow).not.toHaveBeenCalled();
    });

    it("loads once under Strict Mode without submitting any action", async () => {
        render(<StrictMode><MemoryRouter initialEntries={["/workflows/workflow-123"]}><Routes>
            <Route path="/workflows/:workflowId" element={<WorkflowPage />} />
        </Routes></MemoryRouter></StrictMode>);
        await screen.findByRole("button", { name: "Approve Implementation" });
        expect(mockedGetWorkflowDetail).toHaveBeenCalledTimes(1);
        expect(mockedSubmitWorkflowImplementationApproval).not.toHaveBeenCalled();
        expect(mockedResumeWorkflow).not.toHaveBeenCalled();
    });

    it("clears the previous workflow and its approval controls while another workflow loads", async () => {
        let resolveNext!: (value: WorkflowDetailResponse) => void;
        mockedGetWorkflowDetail.mockResolvedValueOnce(workflow()).mockImplementationOnce(() => new Promise((resolve) => { resolveNext = resolve; }));
        const router = createMemoryRouter([{ path: "/workflows/:workflowId", element: <WorkflowPage /> }], { initialEntries: ["/workflows/workflow-123"] });
        render(<RouterProvider router={router} />);
        await screen.findByRole("button", { name: "Approve Implementation" });
        await act(() => router.navigate("/workflows/next-workflow"));
        expect(screen.queryByRole("button", { name: "Approve Implementation" })).not.toBeInTheDocument();
        expect(screen.getByRole("status")).toHaveTextContent("Loading workflow");
        await act(async () => resolveNext(workflow({ workflow_id: "next-workflow", workflow_state: "completed" })));
        expect(screen.queryByRole("button", { name: "Approve Implementation" })).not.toBeInTheDocument();
        expect(mockedSubmitWorkflowImplementationApproval).not.toHaveBeenCalled();
    });

    it("refuses workflow details for a different route identity", async () => {
        mockedGetWorkflowDetail.mockResolvedValue(workflow({ workflow_id: "wrong-workflow" }));
        renderPage();
        const alert = await screen.findByRole("alert");
        expect(alert).toHaveTextContent("The returned workflow does not match this page.");
        expect(alert).not.toHaveTextContent("Try loading it again.");
        expect(screen.queryByRole("button", { name: "Approve Implementation" })).not.toBeInTheDocument();
        expect(screen.getByRole("link", { name: "← All workflows" })).toHaveAttribute("href", "/workflows");
    });

    it("does not attach a late read from a previous workflow to the current page", async () => {
        let resolveOld!: (value: WorkflowDetailResponse) => void;
        mockedGetWorkflowDetail.mockImplementationOnce(() => new Promise((resolve) => { resolveOld = resolve; }))
            .mockResolvedValue(workflow({ workflow_id: "next-workflow", workflow_state: "completed" }));
        const router = createMemoryRouter([{ path: "/workflows/:workflowId", element: <WorkflowPage /> }], { initialEntries: ["/workflows/workflow-123"] });
        render(<RouterProvider router={router} />);
        await waitFor(() => expect(mockedGetWorkflowDetail).toHaveBeenCalledWith("workflow-123"));
        await act(() => router.navigate("/workflows/next-workflow"));
        expect(await screen.findByRole("link", { name: "Open Audit" })).toHaveAttribute("href", "/workflows/next-workflow/audit");
        await act(async () => resolveOld(workflow()));
        expect(screen.getByRole("link", { name: "Open Audit" })).toHaveAttribute("href", "/workflows/next-workflow/audit");
        expect(screen.queryByRole("button", { name: "Approve Implementation" })).not.toBeInTheDocument();
    });

    it("retries a failed read without submitting a workflow action", async () => {
        mockedGetWorkflowDetail.mockRejectedValueOnce(new Error("Unavailable")).mockResolvedValue(workflow());
        renderPage();
        fireEvent.click(await screen.findByRole("button", { name: "Try again" }));
        await screen.findByRole("button", { name: "Approve Implementation" });
        expect(mockedGetWorkflowDetail).toHaveBeenCalledTimes(2);
        expect(mockedSubmitWorkflowImplementationApproval).not.toHaveBeenCalled();
        expect(mockedResumeWorkflow).not.toHaveBeenCalled();
    });

    beforeEach(() => {
        vi.clearAllMocks();
        mockedGetWorkflowDetail.mockReset().mockResolvedValue(workflow());
        mockedGetWorkflowOperationalLifecycle.mockResolvedValue(operationalLifecycle({ workflow_id: "workflow-123" }));
        mockedGetWorkflowRecoveryDiagnostic.mockResolvedValue(null);
        mockedGetWorkflowSupportBundle.mockResolvedValue(null);
        mockedResumeWorkflow.mockResolvedValue(undefined);
    });

    it("shows output truncation without granting execution or approvals", async () => {
        const detail = workflow();
        detail.execution.output_capture = [{ stream: "stdout", retained_bytes: 1024, observed_bytes: 4096, truncated: true }];
        mockedGetWorkflowDetail.mockResolvedValue(detail);
        renderPage();
        expect(await screen.findByRole("heading", { name: "Worker output was shortened" })).toBeInTheDocument();
        expect(screen.getByText(/1024 bytes retained; 4096 bytes observed/)).toBeInTheDocument();
        expect(mockedResumeWorkflow).not.toHaveBeenCalled();
        expect(mockedSubmitWorkflowImplementationApproval).not.toHaveBeenCalled();
        expect(mockedSubmitWorkflowVerificationApproval).not.toHaveBeenCalled();
        expect(mockedSubmitWorkflowCommitApproval).not.toHaveBeenCalled();
    });

    it("checks an unknown worker result once and keeps verification approval separate", async () => {
        const uncertain = workflow({
            workflow_state: "blocked",
            implementation_approval_status: "approved",
            worker_reconciliation: {
                request_id: "original-worker-request", outcome: "unknown",
                request_digest: "execution-request-digest-v1:fixture",
                can_check_result: true, message: "Check the original request.",
            },
        });
        mockedGetWorkflowDetail.mockResolvedValueOnce(uncertain).mockResolvedValue(workflow({
            workflow_state: "awaiting_verification_approval",
            verification_approval_status: "pending",
        }));
        renderPage();

        const check = await screen.findByRole("button", { name: "Check worker result" });
        expect(screen.getByRole("heading", { name: "Worker outcome unknown" })).toBeInTheDocument();
        expect(within(screen.getByRole("region", { name: "Workflow summary" })).getByText("The worker result is unknown. Check the original result before taking another action.")).toBeVisible();
        expect(screen.getByText(/Original request: original-worker-request/)).toBeInTheDocument();
        const record = screen.getByText("Worker request record").closest("details");
        expect(record).not.toHaveAttribute("open");
        expect(record).toHaveTextContent("execution-request-digest-v1:fixture");
        expect(screen.queryByRole("button", { name: "Resume Approved Implementation" })).not.toBeInTheDocument();
        fireEvent.click(check);

        await waitFor(() => expect(mockedResumeWorkflow).toHaveBeenCalledExactlyOnceWith("workflow-123"));
        await waitFor(() => expect(screen.queryByRole("button", { name: "Check worker result" })).not.toBeInTheDocument());
        expect(mockedSubmitWorkflowImplementationApproval).not.toHaveBeenCalled();
        expect(mockedSubmitWorkflowVerificationApproval).not.toHaveBeenCalled();
        expect(mockedSubmitWorkflowCommitApproval).not.toHaveBeenCalled();
    });

    it("does not offer worker reconciliation without server eligibility", async () => {
        mockedGetWorkflowDetail.mockResolvedValue(workflow({
            workflow_state: "blocked",
            worker_reconciliation: {
                request_id: "original-worker-request", outcome: "unknown",
                can_check_result: false, message: "Operator review required.",
            },
        }));
        renderPage();

        await screen.findByRole("heading", { name: "Worker outcome unknown" });
        expect(screen.queryByRole("button", { name: "Check worker result" })).not.toBeInTheDocument();
        expect(mockedResumeWorkflow).not.toHaveBeenCalled();
    });

    it("never checks a worker result automatically on load or refresh", async () => {
        mockedGetWorkflowDetail.mockResolvedValue(workflow({
            workflow_state: "blocked",
            worker_reconciliation: {
                request_id: "original-worker-request", outcome: "unknown",
                can_check_result: true, message: "Check the original request.",
            },
        }));
        renderPage();
        await screen.findByRole("button", { name: "Check worker result" });
        const refresh = screen.getByRole("button", { name: "Refresh" });
        fireEvent.click(refresh);

        await waitFor(() => expect(mockedGetWorkflowDetail).toHaveBeenCalledTimes(2));
        expect(mockedResumeWorkflow).not.toHaveBeenCalled();
    });

    it("shows Resume Approved Implementation only when implementation is approved", async () => {
        mockedGetWorkflowDetail.mockResolvedValue(workflow({
            workflow_state: "awaiting_implementation_approval",
            implementation_approval_status: "approved",
        }));
        renderPage();

        expect(await screen.findByRole("button", { name: "Resume Approved Implementation" })).toBeInTheDocument();
    });

    it("does not show resume action when implementation is pending", async () => {
        renderPage();

        expect(await screen.findByText("Implementation needs approval.", { exact: true })).toBeVisible();
        expect(screen.queryByRole("button", { name: "Resume Approved Implementation" })).not.toBeInTheDocument();
    });

    it("does not show resume action when implementation is rejected", async () => {
        mockedGetWorkflowDetail.mockResolvedValue(workflow({
            workflow_state: "awaiting_implementation_approval",
            implementation_approval_status: "rejected",
        }));
        renderPage();

        expect(await screen.findByText("Implementation approval was rejected.", { exact: true })).toBeVisible();
        expect(screen.queryByRole("button", { name: "Resume Approved Implementation" })).not.toBeInTheDocument();
    });

    it("does not call resume automatically after approving implementation", async () => {
        mockedGetWorkflowDetail.mockResolvedValueOnce(workflow())
            .mockResolvedValue(workflow({ implementation_approval_status: "approved" }));
        mockedSubmitWorkflowImplementationApproval.mockResolvedValue({
            workflow_id: "workflow-123",
            workflow_state: "awaiting_implementation_approval",
            implementation_approval_status: "approved",
            message: null,
        });

        renderPage();

        fireEvent.click(await screen.findByRole("button", { name: "Approve Implementation" }));
        await screen.findByText("Implementation approved. Resume to run this change.");

        expect(mockedResumeWorkflow).not.toHaveBeenCalled();
    });

    it("calls resume exactly once and blocks duplicate resume clicks while in flight", async () => {
        mockedGetWorkflowDetail.mockResolvedValue(workflow({
            workflow_state: "awaiting_implementation_approval",
            implementation_approval_status: "approved",
        }));
        let resolveResume: () => void = () => undefined;
        mockedResumeWorkflow.mockReturnValue(new Promise((resolve) => {
            resolveResume = resolve as () => void;
        }));

        renderPage();

        const resume = await screen.findByRole("button", { name: "Resume Approved Implementation" });
        fireEvent.click(resume);
        fireEvent.click(resume);

        await waitFor(() => expect(mockedResumeWorkflow).toHaveBeenCalledTimes(1));
        expect(screen.queryByRole("button", { name: "Resume Approved Implementation" })).not.toBeInTheDocument();
        expect(screen.getByRole("button", { name: "Resuming..." })).toBeDisabled();
        expect(screen.getByText("Resuming workflow...")).toBeVisible();

        resolveResume();
        await screen.findByText("Implementation");
    });

    it("reloads workflow detail on resume success and uses server-authoritative state", async () => {
        mockedGetWorkflowDetail
            .mockResolvedValueOnce(
                workflow({
                    workflow_state: "awaiting_implementation_approval",
                    implementation_approval_status: "approved",
                }),
            )
            .mockResolvedValueOnce(
                workflow({
                    workflow_state: "awaiting_verification_approval",
                    verification_approval_status: "pending",
                }),
            );

        renderPage();

        fireEvent.click(await screen.findByRole("button", { name: "Resume Approved Implementation" }));

        expect(await screen.findByText("Verification needs approval.")).toBeInTheDocument();
        expect(mockedGetWorkflowDetail).toHaveBeenCalledTimes(2);
    });

    it("shows error and stays on page when resume fails, then refetches authoritative state", async () => {
        mockedGetWorkflowDetail
            .mockResolvedValueOnce(
                workflow({
                    workflow_state: "awaiting_verification_approval",
                    verification_approval_status: "approved",
                }),
            )
            .mockResolvedValueOnce(
                workflow({
                    workflow_state: "awaiting_verification_approval",
                    verification_approval_status: "approved",
                }),
            );
        mockedResumeWorkflow.mockRejectedValue(new Error("Workflow blocked"));

        renderPage();

        fireEvent.click(await screen.findByRole("button", { name: "Resume Approved Verification" }));

        const alert = await screen.findByRole("alert");
        expect(alert).toHaveTextContent("Mission Control could not confirm the workflow result.");
        const technicalDetails = screen.getByText("Technical details").closest("details");
        expect(technicalDetails).not.toHaveAttribute("open");
        expect(technicalDetails).toHaveTextContent("Workflow blocked");
        expect(screen.getByRole("button", { name: "Resume Approved Verification" })).toBeInTheDocument();
        expect(mockedGetWorkflowDetail).toHaveBeenCalledTimes(2);
    });

    it("shows Resume Approved Verification for approved verification state", async () => {
        mockedGetWorkflowDetail.mockResolvedValue(workflowAwaitingVerification({
            verification_approval_status: "approved",
        }));
        renderPage();

        expect(await screen.findByRole("button", { name: "Resume Approved Verification" })).toBeInTheDocument();
    });

    it("shows Resume Approved Commit for approved commit state", async () => {
        mockedGetWorkflowDetail.mockResolvedValue(
            workflowAwaitingCommit({
                workflow_state: "awaiting_commit_approval",
                commit_approval_status: "approved",
            }),
        );
        renderPage();

        expect(await screen.findByRole("button", { name: "Resume Approved Commit" })).toBeInTheDocument();
    });

    it("never shows resume action for blocked workflow", async () => {
        mockedGetWorkflowDetail.mockResolvedValue(
            workflow({
                workflow_state: "blocked",
            }),
        );
        renderPage();

        expect(screen.queryByRole("button", { name: /Resume Approved/i })).not.toBeInTheDocument();
    });

    it("never shows resume action for completed workflow", async () => {
        mockedGetWorkflowDetail.mockResolvedValue(
            workflow({
                workflow_state: "completed",
            }),
        );
        renderPage();

        expect(await screen.findByText("Workflow completed.", { exact: true })).toBeVisible();
        expect(screen.queryByRole("button", { name: /Resume Approved/i })).not.toBeInTheDocument();
    });

    it("renders workflow and immutable implementation request details", async () => {
        renderPage();

        expect(await screen.findByRole("heading", { name: "Review workflow" })).toBeInTheDocument();
        const summary = within(screen.getByRole("region", { name: "Workflow summary" }));
        expect(summary.getByText("Implementation needs approval.", { exact: true })).toBeVisible();
        const details = summary.getByText("Workflow details", { exact: true });
        expect(details.closest("details")).not.toHaveAttribute("open");
        expect(summary.getByText("workflow-123")).not.toBeVisible();
        expect(summary.getByText("Awaiting Implementation Approval")).not.toBeVisible();
        expect(summary.getByText("Candidate ID", { exact: true })).not.toBeVisible();
        fireEvent.click(details);
        expect(summary.getByText("workflow-123")).toBeVisible();
        expect(summary.getByText("Awaiting Implementation Approval")).toBeVisible();
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

    it("provides Open Audit link to workflow audit explorer", async () => {
        renderPage();

        expect(await screen.findByRole("link", { name: "Open Audit" })).toHaveAttribute(
            "href",
            "/workflows/workflow-123/audit",
        );
    });

    it.each([
        ["candidate", "Back to execution candidates", "/execution-candidates"],
        ["manual", "← All workflows", "/workflows"],
        ["unrecognized", "← All workflows", "/workflows"],
    ])("returns a %s workflow to its matching list", async (source, label, destination) => {
        mockedGetWorkflowDetail.mockResolvedValue(workflow({ workflow_source: source }));
        renderPage();

        expect(await screen.findByRole("link", { name: label })).toHaveAttribute("href", destination);
    });

    it("submits approve with only workflow id and decision", async () => {
        mockedGetWorkflowDetail.mockResolvedValueOnce(workflow())
            .mockResolvedValue(workflow({ implementation_approval_status: "approved" }));
        mockedSubmitWorkflowImplementationApproval.mockResolvedValue({
            workflow_id: "workflow-123",
            workflow_state: "awaiting_execution",
            implementation_approval_status: "approved",
            message: null,
        });
        renderPage();

        fireEvent.click(await screen.findByRole("button", { name: "Approve Implementation" }));

        await screen.findByText("Implementation approved. Resume to run this change.");
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

        fireEvent.click(await screen.findByRole("button", { name: "Reject implementation" }));

        await screen.findByText("Implementation request rejected.");
        expect(mockedSubmitWorkflowImplementationApproval).toHaveBeenCalledWith("workflow-123", "reject");
    });

    it("shows pending state and blocks duplicate submissions", async () => {
        mockedGetWorkflowDetail.mockResolvedValueOnce(workflow())
            .mockResolvedValue(workflow({ implementation_approval_status: "approved" }));
        let resolveApproval: (value: Awaited<ReturnType<typeof submitWorkflowImplementationApproval>>) => void = () => undefined;
        mockedSubmitWorkflowImplementationApproval.mockReturnValue(new Promise((resolve) => {
            resolveApproval = resolve;
        }));
        renderPage();

        const approve = await screen.findByRole("button", { name: "Approve Implementation" });
        fireEvent.click(approve);
        fireEvent.click(approve);

        expect(await screen.findByText("Submitting implementation approval...")).toBeInTheDocument();
        expect(mockedSubmitWorkflowImplementationApproval).toHaveBeenCalledTimes(1);
        resolveApproval({
            workflow_id: "workflow-123",
            workflow_state: "awaiting_execution",
            implementation_approval_status: "approved",
            message: null,
        });
        await screen.findByText("Implementation approved. Resume to run this change.");
    });

    it("hides approval controls outside awaiting implementation approval", async () => {
        mockedGetWorkflowDetail.mockResolvedValue(workflow({
            workflow_state: "awaiting_execution",
            implementation_approval_status: "approved",
        }));
        renderPage();

        expect(await screen.findByText("Implementation approval is not available at this step.")).toBeVisible();
        expect(screen.queryByRole("button", { name: "Approve Implementation" })).not.toBeInTheDocument();
        expect(screen.queryByRole("button", { name: "Reject implementation" })).not.toBeInTheDocument();
    });

    it("hides implementation approval controls after an approve response without state transition", async () => {
        mockedGetWorkflowDetail
            .mockResolvedValueOnce(workflow())
            .mockResolvedValueOnce(workflow({ implementation_approval_status: "approved" }));
        mockedSubmitWorkflowImplementationApproval.mockResolvedValue({
            workflow_id: "workflow-123",
            workflow_state: "awaiting_implementation_approval",
            implementation_approval_status: "approved",
            message: null,
        });
        renderPage();

        fireEvent.click(await screen.findByRole("button", { name: "Approve Implementation" }));

        await screen.findByText("Implementation approved. Resume to run this change.");
        expect(screen.queryByRole("button", { name: "Approve Implementation" })).not.toBeInTheDocument();
        expect(screen.queryByRole("button", { name: "Reject implementation" })).not.toBeInTheDocument();
    });

    it("renders workflow rail and no execution, verification, or commit controls", async () => {
        renderPage();

        expect(await screen.findByText("Implementation")).toBeInTheDocument();
        expect(screen.getAllByText("Execution").length).toBeGreaterThan(0);
        expect(screen.getAllByText("Verification").length).toBeGreaterThan(0);
        expect(screen.getAllByText("Commit").length).toBeGreaterThan(0);
        expect(screen.getByText("current")).toBeInTheDocument();
        expect(screen.getAllByText("waiting").length).toBeGreaterThan(0);
        expect(screen.queryByRole("button", { name: /execute/i })).not.toBeInTheDocument();
        expect(screen.queryByRole("button", { name: /verify/i })).not.toBeInTheDocument();
        expect(screen.queryByRole("button", { name: /commit/i })).not.toBeInTheDocument();
        expect(screen.queryByRole("textbox")).not.toBeInTheDocument();
    });

    it("presents operational action approval without repository-only controls", async () => {
        mockedGetWorkflowDetail.mockResolvedValue(workflow({
            effect_kind: "operational_action",
            operational_action_request: operationalActionRequest(),
        }));
        renderPage();

        expect(await screen.findByRole("heading", { name: "Maintenance request approval" })).toBeInTheDocument();
        expect(screen.getByRole("button", { name: "Approve maintenance request" })).toBeInTheDocument();
        expect(screen.getByRole("button", { name: "Reject maintenance request" })).toBeInTheDocument();
        expect(screen.queryByRole("heading", { name: "Implementation Request" })).not.toBeInTheDocument();
        expect(screen.queryByRole("heading", { name: "Verification Plan" })).not.toBeInTheDocument();
        expect(screen.queryByRole("heading", { name: "Commit Request" })).not.toBeInTheDocument();
        expect(screen.queryByRole("button", { name: /commit/i })).not.toBeInTheDocument();
        expect(await screen.findByRole("heading", { name: "Operational lifecycle" })).toBeInTheDocument();
        expect(screen.getAllByText("resolved (approved)")).toHaveLength(2);
    });

    it("rejects a maintenance request without running it", async () => {
        mockedGetWorkflowDetail.mockResolvedValue(workflow({ effect_kind: "operational_action" }));
        mockedSubmitWorkflowImplementationApproval.mockResolvedValue({
            workflow_id: "workflow-123",
            workflow_state: "implementation_rejected",
            implementation_approval_status: "rejected",
            message: null,
        });
        renderPage();

        fireEvent.click(await screen.findByRole("button", { name: "Reject maintenance request" }));

        expect(await screen.findByText("Maintenance request rejected.")).toBeVisible();
        expect(mockedSubmitWorkflowImplementationApproval).toHaveBeenCalledWith("workflow-123", "reject");
        expect(mockedResumeWorkflow).not.toHaveBeenCalled();
    });

    it("downloads only the sanitized in-memory support bundle", async () => {
        mockedGetWorkflowDetail.mockResolvedValue(workflow({ effect_kind: "operational_action" }));
        mockedGetWorkflowSupportBundle.mockResolvedValue({
            applicable: true,
            metadata: { schema_version: "atlas-operational-support-bundle-v1", generated_at: "2026-08-15T00:00:00Z", agent_version: "0.9", workflow_id: "workflow-123" },
            workflow: { candidate_id: "candidate-123", planning_session_id: "plan-123", effect_kind: "operational_action", execution_intent: "restart-service", target_label: "proxmox/qemu/110" },
            approvals: { preparation: null, operational_action: null },
            lifecycle: { availability: "complete", request_id: "request-1", request_digest: "digest-1", agent_execution_stage: "verified", core_ledger_state: "verified", transitions: [], transition_sequence_valid: true, barrier_crossed: true, barrier_crossing_count: 1, provider_operation_captured: true, provider_operation_capture_count: 1, dispatch_status: "succeeded", dispatch_result_known: true, provider_operation_reference: "UPID:sanitized", verification_status: "succeeded", observed_state: "running", observed_health: "running", terminal: true },
            diagnostic: { applicable: true, diagnostic_status: "healthy", consistency: "consistent", correlation: { workflow_id: "workflow-123", request_id: "request-1", request_digest_match: true, agent_record_present: true, core_record_present: true }, dispatch_evidence: { barrier_crossed: true, provider_operation_captured: true, dispatch_result_known: true, transition_sequence_valid: true }, verification_evidence: { status: "succeeded", target_fingerprint_state: "unchanged", observed_state: "running", observed_health: "running", terminal_evidence: true }, controlled_reason: null, safe_next_action: "none" },
            service_health: [],
            capability_boundary: { production_tuples: ["restart-service/proxmox/qemu"], agent_execution_intents: ["restart-service"], parity_status: "not_evaluated" },
            audit_refs: [],
            truncation: { transitions_truncated: true, audit_references_truncated: false, text_fields_truncated: [] },
            integrity: { digest: "operational-support-bundle-digest-v1:abc", purpose: "integrity_and_correlation_only" },
        });
        const createObjectURL = vi.fn(() => "blob:support-evidence");
        const revokeObjectURL = vi.fn();
        Object.defineProperty(URL, "createObjectURL", { value: createObjectURL, configurable: true });
        Object.defineProperty(URL, "revokeObjectURL", { value: revokeObjectURL, configurable: true });
        const click = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => undefined);
        renderPage();

        fireEvent.click(await screen.findByRole("button", { name: "Prepare support evidence" }));

        await screen.findByText("atlas-operational-support-bundle-v1");
        expect(mockedGetWorkflowSupportBundle).toHaveBeenCalledWith("workflow-123");
        expect(screen.getByText(/integrity and correlation only/i)).toBeInTheDocument();
        expect(screen.getByText("Partial or truncated").nextElementSibling).toHaveTextContent("Yes");
        expect(createObjectURL).not.toHaveBeenCalled();

        fireEvent.click(screen.getByRole("button", { name: "Download support evidence" }));

        expect(createObjectURL).toHaveBeenCalledOnce();
        expect(click).toHaveBeenCalledOnce();
        expect(revokeObjectURL).toHaveBeenCalledWith("blob:support-evidence");
        expect(screen.queryByRole("button", { name: /retry|run again|reconcile|upload/i })).not.toBeInTheDocument();
    });

    it("never loads operational lifecycle for a repository workflow", async () => {
        renderPage();

        await screen.findByRole("heading", { name: "Implementation approval" });
        expect(mockedGetWorkflowOperationalLifecycle).not.toHaveBeenCalled();
        expect(mockedGetWorkflowRecoveryDiagnostic).not.toHaveBeenCalled();
        expect(mockedGetWorkflowSupportBundle).not.toHaveBeenCalled();
        expect(screen.queryByRole("heading", { name: "Operational lifecycle" })).not.toBeInTheDocument();
        expect(screen.queryByRole("heading", { name: "Support evidence" })).not.toBeInTheDocument();
        expect(screen.queryByLabelText("Recovery summary")).not.toBeInTheDocument();
    });

    it("deterministically refreshes workflow and operational lifecycle together", async () => {
        mockedGetWorkflowDetail.mockResolvedValue(workflow({ effect_kind: "operational_action" }));
        renderPage();

        fireEvent.click(await screen.findByRole("button", { name: "Refresh lifecycle" }));

        await waitFor(() => expect(mockedGetWorkflowDetail).toHaveBeenCalledTimes(2));
        expect(mockedGetWorkflowOperationalLifecycle).toHaveBeenCalledTimes(2);
    });

    it("retries unavailable lifecycle reads without repeating the action", async () => {
        mockedGetWorkflowDetail.mockResolvedValue(workflow({ effect_kind: "operational_action" }));
        mockedGetWorkflowOperationalLifecycle.mockRejectedValueOnce(new Error("Temporary lifecycle read failure"))
            .mockResolvedValueOnce(operationalLifecycle({ workflow_id: "workflow-123" }));
        renderPage();

        const alert = await screen.findByRole("alert");
        expect(alert).toHaveTextContent("Operational lifecycle unavailable");
        expect(alert).toHaveTextContent("Checking status again does not repeat the maintenance action.");
        fireEvent.click(screen.getByRole("button", { name: "Check status again" }));

        expect(await screen.findByText("proxmox/qemu/110")).toBeInTheDocument();
        expect(mockedGetWorkflowDetail).toHaveBeenCalledTimes(2);
        expect(mockedGetWorkflowOperationalLifecycle).toHaveBeenCalledTimes(2);
        expect(mockedResumeWorkflow).not.toHaveBeenCalled();
        expect(mockedSubmitWorkflowImplementationApproval).not.toHaveBeenCalled();
    });

    it("shows workflow not found", async () => {
        mockedGetWorkflowDetail.mockResolvedValue(null);
        renderPage();

        expect(await screen.findByRole("alert")).toHaveTextContent("Workflow not found");
    });

    it("renders verification plan, evidence, and deterministic review", async () => {
        renderPage();

        expect(await screen.findByRole("heading", { name: "Verification Plan" })).toBeInTheDocument();
        expect(screen.getByText("verification-plan-123")).toBeInTheDocument();
        expect(screen.getByText("verifier-v1")).toBeInTheDocument();
        expect(screen.getAllByText("changed-digest-123").length).toBeGreaterThan(0);
        expect(screen.getAllByText("compose-config, compose-ps").length).toBeGreaterThan(0);
        expect(screen.getByRole("heading", { name: "Verification Evidence" })).toBeInTheDocument();
        expect(screen.getAllByText("abc123").length).toBeGreaterThan(0);
        expect(screen.getByText("compose-config: passed")).toBeInTheDocument();
        expect(screen.getByRole("heading", { name: "Review" })).toBeInTheDocument();
        expect(screen.getByText("Deterministic review")).toBeInTheDocument();
        expect(screen.getByText("review-fingerprint-123")).toBeInTheDocument();
        expect(screen.getAllByText("Disabled").length).toBeGreaterThan(0);
    });

    it("submits verification approval with only workflow id and decision", async () => {
        mockedGetWorkflowDetail.mockResolvedValueOnce(workflow({ workflow_state: "awaiting_verification_approval" }))
            .mockResolvedValue(workflow({ workflow_state: "awaiting_verification_approval", verification_approval_status: "approved" }));
        mockedSubmitWorkflowVerificationApproval.mockResolvedValue({
            workflow_id: "workflow-123",
            workflow_state: "awaiting_verification_approval",
            verification_approval_status: "approved",
            message: null,
        });
        renderPage();

        fireEvent.click(await screen.findByRole("button", { name: "Approve Verification" }));

        await screen.findByText("Verification approved. Resume to run the checks.");
        expect(mockedSubmitWorkflowVerificationApproval).toHaveBeenCalledTimes(1);
        expect(mockedSubmitWorkflowVerificationApproval).toHaveBeenCalledWith("workflow-123", "approve");
        expect(JSON.stringify(mockedSubmitWorkflowVerificationApproval.mock.calls[0])).not.toMatch(/command|check|evidence|changed|review|commit/);
    });

    it("hides verification controls after a verification approve response without state transition", async () => {
        mockedGetWorkflowDetail
            .mockResolvedValueOnce(workflow({ workflow_state: "awaiting_verification_approval" }))
            .mockResolvedValueOnce(workflow({
                workflow_state: "awaiting_verification_approval",
                verification_approval_status: "approved",
            }));
        mockedSubmitWorkflowVerificationApproval.mockResolvedValue({
            workflow_id: "workflow-123",
            workflow_state: "awaiting_verification_approval",
            verification_approval_status: "approved",
            message: null,
        });
        renderPage();

        fireEvent.click(await screen.findByRole("button", { name: "Approve Verification" }));

        await screen.findByText("Verification approved. Resume to run the checks.");
        expect(screen.queryByRole("button", { name: "Approve Verification" })).not.toBeInTheDocument();
        expect(screen.queryByRole("button", { name: "Reject Verification" })).not.toBeInTheDocument();
    });

    it("submits verification rejection and blocks duplicate clicks", async () => {
        mockedGetWorkflowDetail.mockResolvedValue(workflow({ workflow_state: "awaiting_verification_approval" }));
        let resolveApproval: (value: Awaited<ReturnType<typeof submitWorkflowVerificationApproval>>) => void = () => undefined;
        mockedSubmitWorkflowVerificationApproval.mockReturnValue(new Promise((resolve) => {
            resolveApproval = resolve;
        }));
        renderPage();

        const reject = await screen.findByRole("button", { name: "Reject Verification" });
        fireEvent.click(reject);
        fireEvent.click(reject);

        expect(await screen.findByText("Submitting verification approval...")).toBeInTheDocument();
        expect(mockedSubmitWorkflowVerificationApproval).toHaveBeenCalledTimes(1);
        expect(mockedSubmitWorkflowVerificationApproval).toHaveBeenCalledWith("workflow-123", "reject");
        resolveApproval({
            workflow_id: "workflow-123",
            workflow_state: "awaiting_verification_approval",
            verification_approval_status: "rejected",
            message: null,
        });
        await screen.findByText("Verification approval rejected.");
    });

    it("renders commit request and reviewed files read-only", async () => {
        mockedGetWorkflowDetail.mockResolvedValue(workflowAwaitingCommit());
        renderPage();

        expect(await screen.findByRole("heading", { name: "Commit Request" })).toBeInTheDocument();
        expect(screen.getByText("approval-commit-workflow-123")).toBeInTheDocument();
        expect(screen.getAllByText("/opt/atlas").length).toBeGreaterThan(0);
        expect(screen.getByText("feature/atlas-agent")).toBeInTheDocument();
        expect(screen.getAllByText("abc123").length).toBeGreaterThan(0);
        expect(screen.getByText("feat(compose): update stack")).toBeInTheDocument();
        expect(screen.getAllByText("compose.yaml, services/demo/Dockerfile").length).toBeGreaterThan(0);
        expect(screen.getByText("reviewed-fingerprint-123")).toBeInTheDocument();
        expect(screen.queryByRole("textbox")).not.toBeInTheDocument();
    });

    it("submits commit approval with only workflow id and decision", async () => {
        mockedGetWorkflowDetail.mockResolvedValueOnce(workflowAwaitingCommit())
            .mockResolvedValue(workflowAwaitingCommit({ commit_approval_status: "approved" }));
        mockedSubmitWorkflowCommitApproval.mockResolvedValue({
            workflow_id: "workflow-123",
            workflow_state: "awaiting_commit_approval",
            commit_approval_status: "approved",
            message: null,
        });
        renderPage();

        fireEvent.click(await screen.findByRole("button", { name: "Approve Commit" }));

        await screen.findByText("Commit approved. Resume to finish the local commit.");
        expect(mockedSubmitWorkflowCommitApproval).toHaveBeenCalledTimes(1);
        expect(mockedSubmitWorkflowCommitApproval).toHaveBeenCalledWith("workflow-123", "approve");
        expect(JSON.stringify(mockedSubmitWorkflowCommitApproval.mock.calls[0])).not.toMatch(/message|path|sha|fingerprint|evidence|repository|push|tag/);
    });

    it("hides commit controls after a commit approve response without state transition", async () => {
        mockedGetWorkflowDetail
            .mockResolvedValueOnce(workflowAwaitingCommit())
            .mockResolvedValueOnce(workflowAwaitingCommit({ commit_approval_status: "approved" }));
        mockedSubmitWorkflowCommitApproval.mockResolvedValue({
            workflow_id: "workflow-123",
            workflow_state: "awaiting_commit_approval",
            commit_approval_status: "approved",
            message: null,
        });
        renderPage();

        fireEvent.click(await screen.findByRole("button", { name: "Approve Commit" }));

        await screen.findByText("Commit approved. Resume to finish the local commit.");
        expect(screen.queryByRole("button", { name: "Approve Commit" })).not.toBeInTheDocument();
        expect(screen.queryByRole("button", { name: "Reject Commit" })).not.toBeInTheDocument();
    });

    it("submits commit rejection and blocks duplicate clicks", async () => {
        mockedGetWorkflowDetail.mockResolvedValue(workflowAwaitingCommit());
        let resolveApproval: (value: Awaited<ReturnType<typeof submitWorkflowCommitApproval>>) => void = () => undefined;
        mockedSubmitWorkflowCommitApproval.mockReturnValue(new Promise((resolve) => {
            resolveApproval = resolve;
        }));
        renderPage();

        const reject = await screen.findByRole("button", { name: "Reject Commit" });
        fireEvent.click(reject);
        fireEvent.click(reject);

        expect(await screen.findByText("Submitting commit approval...")).toBeInTheDocument();
        expect(mockedSubmitWorkflowCommitApproval).toHaveBeenCalledTimes(1);
        expect(mockedSubmitWorkflowCommitApproval).toHaveBeenCalledWith("workflow-123", "reject");
        resolveApproval({
            workflow_id: "workflow-123",
            workflow_state: "awaiting_commit_approval",
            commit_approval_status: "rejected",
            message: null,
        });
        await screen.findByText("Commit approval rejected.");
    });

    it("renders completed workflow commit result read-only", async () => {
        mockedGetWorkflowDetail.mockResolvedValue(workflowAwaitingCommit({
            workflow_state: "completed",
            commit_approval_status: "approved",
            commit_result: {
                commit_sha: "def456",
                commit_message: "feat(compose): update stack",
                committed_files: ["compose.yaml", "services/demo/Dockerfile"],
                completion_time: "2026-08-02T18:00:00Z",
            },
        }));
        renderPage();

        expect(await screen.findByRole("heading", { name: "Completed workflow" })).toBeInTheDocument();
        expect(screen.getByText("def456")).toBeInTheDocument();
        expect(screen.getAllByText("feat(compose): update stack").length).toBeGreaterThan(0);
        expect(screen.getAllByText("compose.yaml, services/demo/Dockerfile").length).toBeGreaterThan(0);
        expect(screen.getByText("2026-08-02T18:00:00Z")).toBeInTheDocument();
        expect(screen.queryByRole("button", { name: "Approve Commit" })).not.toBeInTheDocument();
    });

    it("does not expose push, tag, amend, release, or rollback controls", async () => {
        mockedGetWorkflowDetail.mockResolvedValue(workflowAwaitingCommit());
        renderPage();

        await screen.findByRole("heading", { name: "Commit Request" });
        expect(screen.queryByRole("button", { name: /push/i })).not.toBeInTheDocument();
        expect(screen.queryByRole("button", { name: /tag/i })).not.toBeInTheDocument();
        expect(screen.queryByRole("button", { name: /amend/i })).not.toBeInTheDocument();
        expect(screen.queryByRole("button", { name: /release/i })).not.toBeInTheDocument();
        expect(screen.queryByRole("button", { name: /roll back|rollback/i })).not.toBeInTheDocument();
    });

    it("shows approval failures in plain language with the backend message collapsed", async () => {
        mockedSubmitWorkflowImplementationApproval.mockRejectedValue(new Error("approval already approved"));
        renderPage();

        fireEvent.click(await screen.findByRole("button", { name: "Approve Implementation" }));

        const alert = await screen.findByRole("alert");
        expect(alert).toHaveTextContent("Mission Control could not confirm the implementation approval decision.");
        const technicalDetails = screen.getByText("Technical details").closest("details");
        expect(technicalDetails).not.toHaveAttribute("open");
        expect(technicalDetails).toHaveTextContent("approval already approved");
    });
});
