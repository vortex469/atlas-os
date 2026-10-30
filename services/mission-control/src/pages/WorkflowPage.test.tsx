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

function renderPage(path = "/workflows/workflow-123", state?: unknown) {
    return render(
        <MemoryRouter initialEntries={[state === undefined ? path : { pathname: path, state }]}>
            <Routes>
                <Route path="/workflows/:workflowId" element={<WorkflowPage />} />
            </Routes>
        </MemoryRouter>,
    );
}

describe("WorkflowPage", () => {
    it.each([
        ["preparation", workflow({ workflow_state: "awaiting_approval" }), "Prepare the change for review."],
        ["executing", workflow({ workflow_state: "executing" }), "Implementation is running."],
        ["approved and ready", workflow({ workflow_state: "awaiting_execution", implementation_approval_status: "approved" }), "Implementation is approved and ready to run."],
        ["unconfirmed approval", workflow({ workflow_state: "awaiting_execution", implementation_approval_status: "pending" }), "Implementation approval is not confirmed. Refresh before running it."],
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
        expect(alert).toHaveTextContent("Atlas couldn’t read this workflow’s details. Try again to reload them.");
        const technicalDetails = within(alert).getByText("Technical details").closest("details");
        expect(technicalDetails).not.toHaveAttribute("open");
        expect(within(technicalDetails as HTMLElement).getByText("Malformed workflow detail payload.")).not.toBeVisible();
        expect(screen.queryByRole("button", { name: "Approve Implementation" })).not.toBeInTheDocument();
        expect(screen.queryByRole("button", { name: "Run approved change" })).not.toBeInTheDocument();
        expect(mockedSubmitWorkflowImplementationApproval).not.toHaveBeenCalled();
        expect(mockedResumeWorkflow).not.toHaveBeenCalled();
    });

    it("keeps workflow request errors in collapsed technical details", async () => {
        mockedGetWorkflowDetail.mockRejectedValue(new Error("Network Error"));
        renderPage();

        const alert = await screen.findByRole("alert");
        expect(alert).toHaveTextContent("Atlas couldn’t load this workflow, so its status is unknown.");
        const technicalDetails = within(alert).getByText("Technical details").closest("details");
        expect(technicalDetails).not.toHaveAttribute("open");
        expect(within(technicalDetails as HTMLElement).getByText("Network Error")).not.toBeVisible();
        expect(within(alert).getByRole("button", { name: "Try again" })).toBeVisible();
        expect(screen.getByRole("link", { name: "← All workflows" })).toHaveAttribute("href", "/workflows");
        expect(screen.queryByRole("region", { name: "Read-only workflow rail" })).not.toBeInTheDocument();
        expect(screen.queryByRole("button", { name: "Approve Implementation" })).not.toBeInTheDocument();
    });

    it("shows the exact maintenance request before offering action approval", async () => {
        mockedGetWorkflowDetail.mockResolvedValue(workflow({ effect_kind: "operational_action" }));
        renderPage();
        await screen.findByRole("heading", { name: "Maintenance request" });
        expect(screen.getByText("Maintenance request needs approval.", { exact: true })).toBeVisible();
        expect(screen.getByText("Proxmox virtual machine 110", { exact: true })).toBeVisible();
        const expiryTime = screen.getByText("Request expires (local time)").parentElement?.querySelector("time");
        expect(expiryTime).toHaveAttribute("datetime", "2999-01-01T12:00:00Z");
        const references = screen.getByText("Request references", { exact: true });
        expect(references.closest("details")).not.toHaveAttribute("open");
        fireEvent.click(references);
        expect(within(references.closest("details") as HTMLElement).getByText("proxmox/qemu/110", { exact: true })).toBeVisible();
        const generatedTime = within(references.closest("details") as HTMLElement).getByText("Generated (local time)").parentElement?.querySelector("time");
        expect(generatedTime).toHaveAttribute("datetime", "2026-01-01T12:00:00Z");
        expect(screen.getByText("Temporary service interruption.")).toBeVisible();
        expect(screen.getByText(/Stop and require operator review/)).toBeVisible();
        expect(screen.getByRole("button", { name: "Approve maintenance request" })).toBeEnabled();
        expect(screen.getByRole("button", { name: "Reject maintenance request" })).toBeEnabled();
        expect(screen.getByText(/Approval does not run it; choose Run approved maintenance separately/)).toBeVisible();
        expect(mockedSubmitWorkflowImplementationApproval).not.toHaveBeenCalled();
    });

    it("labels an invalid request expiry as unverified without changing the recorded approval controls", async () => {
        mockedGetWorkflowDetail.mockResolvedValue(workflow({
            effect_kind: "operational_action",
            operational_action_request: operationalActionRequest({ expires_at: "2026-02-30T12:00:00Z" }),
        }));
        renderPage();

        await screen.findByRole("heading", { name: "Maintenance request" });
        expect(screen.getByText("Unverified expiry")).toBeVisible();
        expect(screen.getByRole("button", { name: "Approve maintenance request" })).toBeEnabled();
        expect(screen.getByRole("button", { name: "Reject maintenance request" })).toBeEnabled();
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
        mockedGetWorkflowDetail.mockResolvedValue(workflow({ effect_kind: "operational_action", workflow_state: "awaiting_execution", operational_action_request: null, implementation_approval_status: "approved" }));
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
        expect(screen.queryByText("Checking maintenance status…")).not.toBeInTheDocument();
        expect(mockedSubmitWorkflowImplementationApproval).not.toHaveBeenCalled();
    });

    it.each(["lifecycle", "diagnostic"])("does not display %s evidence from another workflow", async (kind) => {
        mockedGetWorkflowDetail.mockResolvedValue(workflow({ effect_kind: "operational_action" }));
        if (kind === "lifecycle") mockedGetWorkflowOperationalLifecycle.mockResolvedValue(operationalLifecycle({ workflow_id: "different-workflow" }));
        else mockedGetWorkflowRecoveryDiagnostic.mockResolvedValue(operationalDiagnostic());
        renderPage();
        const message = kind === "lifecycle" ? "The operational lifecycle response does not match this workflow." : "The returned status does not match this workflow.";
        const messageElement = await screen.findByText(message);
        if (kind === "lifecycle") {
            expect(messageElement.closest("details")).not.toHaveAttribute("open");
            expect(messageElement).not.toBeVisible();
        } else {
            expect(messageElement).toBeVisible();
        }
        expect(screen.queryByText("different-workflow")).not.toBeInTheDocument();
        expect(screen.queryByText("Checking maintenance status…")).not.toBeInTheDocument();
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

        const alert = await screen.findByRole("alert");
        expect(alert).toHaveTextContent(expectedFailureMessage);
        const technicalDetails = within(alert).getByText("Technical details").closest("details");
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
        const name = stage === "implementation" ? "Run approved change"
            : stage === "verification" ? "Run approved checks" : "Record approved commit";
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
        expect(screen.queryByText("Change approved. Run it when you are ready.")).not.toBeInTheDocument();
        expect(screen.queryByRole("button", { name: "Run approved change" })).not.toBeInTheDocument();
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
        expect(screen.getByText("Only part of the worker's output is shown. Verification and commit each need separate approval.")).toBeVisible();
        const outputDetails = screen.getByText("Output details").closest("details") as HTMLElement;
        const byteCounts = within(outputDetails).getByText(/1024 bytes retained; 4096 bytes observed/);
        expect(outputDetails).not.toHaveAttribute("open");
        expect(byteCounts).not.toBeVisible();
        fireEvent.click(screen.getByText("Output details"));
        expect(byteCounts).toBeVisible();
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
        expect(screen.getByRole("heading", { name: "Worker result not confirmed" })).toBeInTheDocument();
        expect(within(screen.getByRole("region", { name: "Workflow summary" })).getByText("Atlas couldn't confirm whether the change finished. Check its result before starting the change again.")).toBeVisible();
        expect(within(screen.getByRole("region", { name: "Change progress" })).getByRole("status")).toHaveTextContent("The change may have finished. Check its result before starting it again.");
        const record = screen.getByText("Request details").closest("details");
        expect(record).not.toHaveAttribute("open");
        const requestId = within(record as HTMLElement).getByText("Request ID: original-worker-request");
        const requestDigest = within(record as HTMLElement).getByText("Request digest: execution-request-digest-v1:fixture");
        expect(requestId).not.toBeVisible();
        expect(requestDigest).not.toBeVisible();
        fireEvent.click(screen.getByText("Request details"));
        expect(requestId).toBeVisible();
        expect(requestDigest).toBeVisible();
        expect(screen.queryByRole("button", { name: "Run approved change" })).not.toBeInTheDocument();
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

        await screen.findByRole("heading", { name: "Worker result not confirmed" });
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

    it("shows Run approved change only when implementation is approved", async () => {
        mockedGetWorkflowDetail.mockResolvedValue(workflow({
            workflow_state: "awaiting_implementation_approval",
            implementation_approval_status: "approved",
        }));
        renderPage();

        expect(await screen.findByRole("button", { name: "Run approved change" })).toBeInTheDocument();
        expect(screen.getByText("Implementation approval is recorded.", { exact: true })).toBeVisible();
    });

    it("does not show resume action when implementation is pending", async () => {
        renderPage();

        expect(await screen.findByText("Implementation needs approval.", { exact: true })).toBeVisible();
        expect(screen.queryByRole("button", { name: "Run approved change" })).not.toBeInTheDocument();
    });

    it("does not show resume action when implementation is rejected", async () => {
        mockedGetWorkflowDetail.mockResolvedValue(workflow({
            workflow_state: "awaiting_implementation_approval",
            implementation_approval_status: "rejected",
        }));
        renderPage();

        expect(await screen.findByText("Implementation approval was rejected.", { exact: true })).toBeVisible();
        expect(screen.queryByRole("button", { name: "Run approved change" })).not.toBeInTheDocument();
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
        await screen.findByText("Change approved. Run it when you are ready.");

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

        const resume = await screen.findByRole("button", { name: "Run approved change" });
        fireEvent.click(resume);
        fireEvent.click(resume);

        await waitFor(() => expect(mockedResumeWorkflow).toHaveBeenCalledTimes(1));
        expect(screen.queryByRole("button", { name: "Run approved change" })).not.toBeInTheDocument();
        expect(screen.getByRole("button", { name: "Running approved change..." })).toBeDisabled();
        expect(screen.getByText("Running the approved change...")).toBeVisible();

        resolveResume();
        await waitFor(() => expect(mockedGetWorkflowDetail).toHaveBeenCalledTimes(2));
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

        fireEvent.click(await screen.findByRole("button", { name: "Run approved change" }));

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

        fireEvent.click(await screen.findByRole("button", { name: "Run approved checks" }));

        const alert = await screen.findByRole("alert");
        expect(alert).toHaveTextContent("Mission Control could not confirm the workflow result.");
        const technicalDetails = within(alert).getByText("Technical details").closest("details");
        expect(technicalDetails).not.toHaveAttribute("open");
        expect(technicalDetails).toHaveTextContent("Workflow blocked");
        expect(screen.getByRole("button", { name: "Run approved checks" })).toBeInTheDocument();
        expect(mockedGetWorkflowDetail).toHaveBeenCalledTimes(2);
    });

    it("shows Run approved checks for approved verification state", async () => {
        mockedGetWorkflowDetail.mockResolvedValue(workflowAwaitingVerification({
            verification_approval_status: "approved",
        }));
        renderPage();

        expect(await screen.findByRole("button", { name: "Run approved checks" })).toBeInTheDocument();
        expect(screen.getByText("Verification approval is recorded.", { exact: true })).toBeVisible();
    });

    it("shows Record approved commit for approved commit state", async () => {
        mockedGetWorkflowDetail.mockResolvedValue(
            workflowAwaitingCommit({
                workflow_state: "awaiting_commit_approval",
                commit_approval_status: "approved",
            }),
        );
        renderPage();

        expect(await screen.findByRole("button", { name: "Record approved commit" })).toBeInTheDocument();
        expect(screen.getByText("Commit approval is recorded.", { exact: true })).toBeVisible();
    });

    it("never shows resume action for blocked workflow", async () => {
        mockedGetWorkflowDetail.mockResolvedValue(
            workflow({
                workflow_state: "blocked",
            }),
        );
        renderPage();

        expect(screen.queryByRole("button", { name: /Run approved|Record approved/i })).not.toBeInTheDocument();
    });

    it("never shows resume action for completed workflow", async () => {
        mockedGetWorkflowDetail.mockResolvedValue(
            workflow({
                workflow_state: "completed",
            }),
        );
        renderPage();

        expect(await screen.findByText("Workflow completed.", { exact: true })).toBeVisible();
        expect(screen.queryByRole("button", { name: /Run approved|Record approved/i })).not.toBeInTheDocument();
    });

    it("renders concise change details and keeps request references collapsed", async () => {
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
        const changeDetails = within(screen.getByRole("region", { name: "Change details" }));
        expect(changeDetails.getByText("docker-compose")).toBeVisible();
        expect(changeDetails.getByText("compose.yaml, services/demo/Dockerfile")).toBeVisible();
        const technicalDetails = changeDetails.getByText("Technical details").closest("details");
        expect(technicalDetails).not.toHaveAttribute("open");
        expect(changeDetails.getByText("/opt/atlas")).not.toBeVisible();
        expect(changeDetails.getByText("/opt/atlas/services/demo")).not.toBeVisible();
        expect(changeDetails.getByText("candidate-translator-v1")).not.toBeVisible();
        expect(changeDetails.getByText("impl-request-123")).not.toBeVisible();

        fireEvent.click(changeDetails.getByText("Technical details"));

        expect(technicalDetails).toHaveAttribute("open");
        expect(changeDetails.getByText("/opt/atlas")).toBeVisible();
        expect(changeDetails.getByText("/opt/atlas/services/demo")).toBeVisible();
        expect(changeDetails.getByText("candidate-translator-v1")).toBeVisible();
        expect(changeDetails.getByText("impl-request-123")).toBeVisible();
    });

    it("explains when change details are unavailable", async () => {
        mockedGetWorkflowDetail.mockResolvedValue(workflow({ implementation_request: null }));
        renderPage();

        const changeDetails = within(await screen.findByRole("region", { name: "Change details" }));
        expect(changeDetails.getByRole("alert")).toHaveTextContent("Change details are unavailable. Refresh this workflow before continuing.");
    });

    it("provides Open Audit link to workflow audit explorer", async () => {
        renderPage("/workflows/workflow-123?source=maintenance-history");

        expect(await screen.findByRole("link", { name: "Open Audit" })).toHaveAttribute(
            "href",
            "/workflows/workflow-123/audit?source=maintenance-history",
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

    it("returns a maintenance request to maintenance history when opened directly", async () => {
        mockedGetWorkflowDetail.mockResolvedValue(workflow({ effect_kind: "operational_action" }));
        renderPage();

        expect(await screen.findByRole("link", { name: "← Maintenance history" })).toHaveAttribute("href", "/operations/history");
    });

    it("preserves maintenance history filters and page position when returning from review", async () => {
        mockedGetWorkflowDetail.mockResolvedValue(workflow({ effect_kind: "operational_action" }));
        const search = "?status=unavailable&completion=terminal&offset=10";
        render(
            <MemoryRouter initialEntries={[{
                pathname: "/workflows/workflow-123",
                search,
                state: { returnTo: "/operations/history" },
            }]}>
                <Routes><Route path="/workflows/:workflowId" element={<WorkflowPage />} /></Routes>
            </MemoryRouter>,
        );

        expect(await screen.findByRole("link", { name: "← Maintenance history" })).toHaveAttribute(
            "href",
            `/operations/history${search}`,
        );
    });

    it("keeps the maintenance return context when workflow details are unavailable", async () => {
        mockedGetWorkflowDetail.mockRejectedValue(new Error("Workflow read failed."));
        const search = "?status=unavailable&completion=terminal&offset=10";
        render(
            <MemoryRouter initialEntries={[{
                pathname: "/workflows/workflow-123",
                search,
                state: { returnTo: "/operations/history" },
            }]}>
                <Routes><Route path="/workflows/:workflowId" element={<WorkflowPage />} /></Routes>
            </MemoryRouter>,
        );

        expect(await screen.findByRole("alert")).toHaveTextContent("Workflow unavailable");
        expect(screen.getByRole("link", { name: "← Maintenance history" })).toHaveAttribute(
            "href",
            `/operations/history${search}`,
        );
    });

    it("offers the maintenance return context while workflow details are loading", () => {
        mockedGetWorkflowDetail.mockImplementation(() => new Promise(() => {}));
        const search = "?status=unavailable&completion=terminal&offset=10";
        render(
            <MemoryRouter initialEntries={[{
                pathname: "/workflows/workflow-123",
                search,
                state: { returnTo: "/operations/history" },
            }]}>
                <Routes><Route path="/workflows/:workflowId" element={<WorkflowPage />} /></Routes>
            </MemoryRouter>,
        );

        expect(screen.getByRole("status")).toHaveTextContent("Loading workflow");
        expect(screen.getByRole("link", { name: "← Maintenance history" })).toHaveAttribute(
            "href",
            `/operations/history${search}`,
        );
    });

    it("returns a maintenance request to the list it was opened from", async () => {
        mockedGetWorkflowDetail.mockResolvedValue(workflow({ effect_kind: "operational_action" }));
        renderPage("/workflows/workflow-123", { returnTo: "/workflows" });

        expect(await screen.findByRole("link", { name: "← All workflows" })).toHaveAttribute("href", "/workflows");
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

        await screen.findByText("Change approved. Run it when you are ready.");
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
        await screen.findByText("Change approved. Run it when you are ready.");
    });

    it("hides approval controls outside awaiting implementation approval", async () => {
        mockedGetWorkflowDetail.mockResolvedValue(workflow({
            workflow_state: "awaiting_execution",
            implementation_approval_status: "approved",
        }));
        renderPage();

        expect(await screen.findByText("Implementation approval is recorded.", { exact: true })).toBeVisible();
        expect(screen.queryByRole("button", { name: "Approve Implementation" })).not.toBeInTheDocument();
        expect(screen.queryByRole("button", { name: "Reject implementation" })).not.toBeInTheDocument();
        expect(screen.getByRole("button", { name: "Run approved change" })).toBeVisible();
    });

    it("offers approved maintenance run in the ready-to-run state only with the exact request", async () => {
        mockedGetWorkflowDetail.mockResolvedValue(workflow({
            effect_kind: "operational_action",
            workflow_state: "awaiting_execution",
            implementation_approval_status: "approved",
            operational_action_request: operationalActionRequest(),
        }));
        renderPage();

        expect(await screen.findByRole("button", { name: "Run approved maintenance" })).toBeVisible();
        expect(screen.queryByRole("button", { name: "Approve maintenance request" })).not.toBeInTheDocument();
        expect(screen.queryByRole("button", { name: "Reject maintenance request" })).not.toBeInTheDocument();
        expect(mockedResumeWorkflow).not.toHaveBeenCalled();
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

        await screen.findByText("Change approved. Run it when you are ready.");
        expect(screen.queryByRole("button", { name: "Approve Implementation" })).not.toBeInTheDocument();
        expect(screen.queryByRole("button", { name: "Reject implementation" })).not.toBeInTheDocument();
    });

    it("renders workflow rail and no execution, verification, or commit controls", async () => {
        renderPage();

        const rail = await screen.findByRole("region", { name: "Read-only workflow rail" });
        expect(within(rail).getByText("Change approval")).toBeInTheDocument();
        expect(within(rail).getByText("Apply change")).toBeInTheDocument();
        expect(within(rail).getByText("Verify change")).toBeInTheDocument();
        expect(within(rail).getByText("Commit")).toBeInTheDocument();
        expect(within(rail).getByText("Current step")).toBeInTheDocument();
        expect(within(rail).getAllByText("Not started").length).toBeGreaterThan(0);
        const stages = within(screen.getByRole("region", { name: "Change progress" })).getByRole("list", { name: "Change stages" });
        expect(within(stages).getByText("Change proposal")).toBeInTheDocument();
        expect(within(stages).getByText("Apply change")).toBeInTheDocument();
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

        expect(await screen.findByRole("heading", { name: "Review maintenance request" })).toBeInTheDocument();
        expect(await screen.findByRole("heading", { name: "Maintenance request approval" })).toBeInTheDocument();
        expect(screen.getByRole("button", { name: "Approve maintenance request" })).toBeInTheDocument();
        expect(screen.getByRole("button", { name: "Reject maintenance request" })).toBeInTheDocument();
        expect(screen.queryByRole("region", { name: "Read-only workflow rail" })).not.toBeInTheDocument();
        const stages = screen.getByRole("list", { name: "Maintenance workflow stages" });
        expect(within(stages).getByText("Maintenance request approval", { exact: true })).toBeInTheDocument();
        expect(within(stages).queryByText("Review", { exact: true })).not.toBeInTheDocument();
        expect(within(stages).queryByText("Commit", { exact: true })).not.toBeInTheDocument();
        expect(screen.queryByRole("heading", { name: "Implementation Request" })).not.toBeInTheDocument();
        expect(screen.queryByRole("heading", { name: "Checks to run" })).not.toBeInTheDocument();
        expect(screen.queryByRole("heading", { name: "Commit Request" })).not.toBeInTheDocument();
        expect(screen.queryByRole("button", { name: /commit/i })).not.toBeInTheDocument();
        expect(await screen.findByRole("heading", { name: "Maintenance status" })).toBeInTheDocument();
        expect(screen.getAllByText("resolved (approved)")).toHaveLength(2);
    });

    it("uses maintenance labels and keeps repository-only details out of the summary", async () => {
        mockedGetWorkflowDetail.mockResolvedValue(workflow({ effect_kind: "operational_action" }));
        renderPage();

        const summary = within(await screen.findByRole("region", { name: "Maintenance summary" }));
        const disclosure = summary.getByText("Technical details", { exact: true });
        const details = disclosure.closest("details") as HTMLDetailsElement;
        expect(details).not.toHaveAttribute("open");
        fireEvent.click(disclosure);

        const detailsContent = within(details);
        expect(detailsContent.getByText("Maintenance request approval", { exact: true })).toBeVisible();
        expect(detailsContent.queryByText("Implementation approval", { exact: true })).not.toBeInTheDocument();
        expect(detailsContent.queryByText("Verification approval", { exact: true })).not.toBeInTheDocument();
        expect(detailsContent.queryByText("Commit approval", { exact: true })).not.toBeInTheDocument();
        expect(detailsContent.queryByText("Repository", { exact: true })).not.toBeInTheDocument();
        expect(detailsContent.queryByText("Working directory", { exact: true })).not.toBeInTheDocument();
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
        const createObjectURL = vi.fn()
            .mockImplementationOnce(() => { throw new Error("private download diagnostic"); })
            .mockReturnValueOnce("blob:support-evidence");
        const revokeObjectURL = vi.fn();
        Object.defineProperty(URL, "createObjectURL", { value: createObjectURL, configurable: true });
        Object.defineProperty(URL, "revokeObjectURL", { value: revokeObjectURL, configurable: true });
        const click = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => undefined);
        renderPage();

        const supportSummary = await screen.findByText("Optional support file");
        const supportPanel = supportSummary.closest("details");
        expect(supportPanel).not.toHaveAttribute("open");
        expect(mockedGetWorkflowSupportBundle).not.toHaveBeenCalled();
        fireEvent.click(supportSummary);
        fireEvent.click(await screen.findByRole("button", { name: "Prepare support file" }));

        expect(await screen.findByText("Support file ready. Some information is missing or shortened.")).toBeVisible();
        expect(mockedGetWorkflowSupportBundle).toHaveBeenCalledWith("workflow-123");
        const technicalDetails = within(supportPanel!).getByText("Technical details").closest("details");
        expect(technicalDetails).not.toHaveAttribute("open");
        expect(screen.getByText("atlas-operational-support-bundle-v1")).not.toBeVisible();
        fireEvent.click(within(technicalDetails!).getByText("Technical details"));
        expect(screen.getByText("atlas-operational-support-bundle-v1")).toBeVisible();
        const generatedTime = within(technicalDetails!).getByText("Generated (local time)").parentElement?.querySelector("time");
        expect(generatedTime).toHaveAttribute("datetime", "2026-08-15T00:00:00Z");
        expect(screen.getByText("The digest helps identify the file; it is not a digital signature.")).toBeVisible();
        expect(screen.getByText("Information shortened").nextElementSibling).toHaveTextContent("Yes");
        expect(createObjectURL).not.toHaveBeenCalled();

        fireEvent.click(screen.getByRole("button", { name: "Download support file" }));
        expect(await screen.findByText("Mission Control could not download the support file. Try again.")).toBeInTheDocument();
        expect(createObjectURL).toHaveBeenCalledOnce();
        expect(click).not.toHaveBeenCalled();
        expect(document.body).not.toHaveTextContent("private download diagnostic");

        fireEvent.click(screen.getByRole("button", { name: "Download support file" }));

        expect(createObjectURL).toHaveBeenCalledTimes(2);
        expect(click).toHaveBeenCalledOnce();
        expect(revokeObjectURL).toHaveBeenCalledWith("blob:support-evidence");
        expect(screen.queryByText("Mission Control could not download the support file. Try again.")).not.toBeInTheDocument();
        expect(mockedGetWorkflowSupportBundle).toHaveBeenCalledTimes(1);
    });

    it("retries failed support evidence preparation with the same read only", async () => {
        mockedGetWorkflowDetail.mockResolvedValue(workflow({ effect_kind: "operational_action" }));
        mockedGetWorkflowSupportBundle
            .mockRejectedValueOnce(new Error("private diagnostic"))
            .mockRejectedValueOnce(new Error("private diagnostic"));
        renderPage();

        fireEvent.click(await screen.findByText("Optional support file"));
        fireEvent.click(await screen.findByRole("button", { name: "Prepare support file" }));
        const message = await screen.findByText("Mission Control could not prepare a support file.");
        expect(message.closest("[role=alert]")).toBeInTheDocument();
        expect(screen.getByRole("button", { name: "Retry support file" })).toBeEnabled();
        expect(document.body).not.toHaveTextContent("private diagnostic");

        fireEvent.click(screen.getByRole("button", { name: "Retry support file" }));
        await waitFor(() => expect(mockedGetWorkflowSupportBundle).toHaveBeenCalledTimes(2));
        expect(screen.getByRole("button", { name: "Retry support file" })).toBeEnabled();
        expect(mockedSubmitWorkflowImplementationApproval).not.toHaveBeenCalled();
        expect(mockedSubmitWorkflowVerificationApproval).not.toHaveBeenCalled();
        expect(mockedSubmitWorkflowCommitApproval).not.toHaveBeenCalled();
        expect(mockedResumeWorkflow).not.toHaveBeenCalled();
    });

    it("never loads operational lifecycle for a repository workflow", async () => {
        renderPage();

        await screen.findByRole("heading", { name: "Implementation approval" });
        expect(mockedGetWorkflowOperationalLifecycle).not.toHaveBeenCalled();
        expect(mockedGetWorkflowRecoveryDiagnostic).not.toHaveBeenCalled();
        expect(mockedGetWorkflowSupportBundle).not.toHaveBeenCalled();
        expect(screen.queryByRole("heading", { name: "Maintenance status" })).not.toBeInTheDocument();
        expect(screen.queryByText("Optional support file")).not.toBeInTheDocument();
        expect(screen.queryByLabelText("Maintenance status summary")).not.toBeInTheDocument();
    });

    it("deterministically refreshes workflow and operational lifecycle together", async () => {
        mockedGetWorkflowDetail.mockResolvedValue(workflow({ effect_kind: "operational_action" }));
        renderPage();

        fireEvent.click(await screen.findByRole("button", { name: "Refresh maintenance status" }));

        await waitFor(() => expect(mockedGetWorkflowDetail).toHaveBeenCalledTimes(2));
        expect(mockedGetWorkflowOperationalLifecycle).toHaveBeenCalledTimes(2);
    });

    it("retries unavailable lifecycle reads without repeating the action", async () => {
        mockedGetWorkflowDetail.mockResolvedValue(workflow({ effect_kind: "operational_action" }));
        mockedGetWorkflowOperationalLifecycle.mockRejectedValueOnce(new Error("Temporary lifecycle read failure"))
            .mockResolvedValueOnce(operationalLifecycle({ workflow_id: "workflow-123" }));
        renderPage();

        const alert = await screen.findByRole("alert");
        expect(alert).toHaveTextContent("Maintenance status unavailable");
        expect(alert).toHaveTextContent("Checking status again does not repeat the maintenance action.");
        fireEvent.click(screen.getByRole("button", { name: "Check status again" }));

        expect(await screen.findByText("Proxmox virtual machine 110", { exact: true })).toBeVisible();
        expect(mockedGetWorkflowDetail).toHaveBeenCalledTimes(2);
        expect(mockedGetWorkflowOperationalLifecycle).toHaveBeenCalledTimes(2);
        expect(mockedResumeWorkflow).not.toHaveBeenCalled();
        expect(mockedSubmitWorkflowImplementationApproval).not.toHaveBeenCalled();
    });

    it("shows workflow not found", async () => {
        mockedGetWorkflowDetail.mockResolvedValue(null);
        renderPage();

        expect(await screen.findByRole("alert")).toHaveTextContent("Workflow not found");
        expect(screen.queryByRole("region", { name: "Read-only workflow rail" })).not.toBeInTheDocument();
    });

    it("shows checks, results, and one clear review decision", async () => {
        renderPage();

        expect(await screen.findByRole("heading", { name: "Checks to run" })).toBeInTheDocument();
        const verificationReview = within(screen.getByRole("region", { name: "Verification and review" }));
        const technicalDetails = verificationReview.getByText("Technical details").closest("details");
        expect(technicalDetails).not.toHaveAttribute("open");
        expect(verificationReview.getByText("verification-plan-123")).not.toBeVisible();
        expect(verificationReview.getByText("verifier-v1")).not.toBeVisible();
        for (const digest of verificationReview.getAllByText("changed-digest-123")) expect(digest).not.toBeVisible();
        expect(verificationReview.getByText("/opt/atlas/services/demo")).not.toBeVisible();
        expect(verificationReview.getByText("Planned checks")).toBeVisible();
        expect(verificationReview.getAllByText("compose-config, compose-ps").length).toBeGreaterThan(0);
        expect(screen.getByRole("heading", { name: "Check results" })).toBeInTheDocument();
        expect(verificationReview.getByText("abc123")).not.toBeVisible();
        expect(verificationReview.getByText("compose-config: passed")).toBeVisible();
        const review = within(screen.getByRole("region", { name: "Review" }));
        expect(review.getByText("Decision")).toBeVisible();
        expect(review.getByText("Approved", { exact: true })).toBeVisible();
        expect(review.getByText("Summary")).toBeVisible();
        expect(review.getByText("No findings or recommendations.", { exact: true })).toBeVisible();
        expect(review.getByText("compose.yaml")).toBeVisible();
        expect(review.queryByText("Review result", { exact: true })).not.toBeInTheDocument();
        expect(review.queryByText("Review status", { exact: true })).not.toBeInTheDocument();
        expect(review.queryByText("Model-assisted review", { exact: true })).not.toBeInTheDocument();
        expect(verificationReview.getByText("review-fingerprint-123")).not.toBeVisible();

        fireEvent.click(verificationReview.getByText("Technical details"));

        expect(technicalDetails).toHaveAttribute("open");
        expect(verificationReview.getByText("verification-plan-123")).toBeVisible();
        expect(verificationReview.getByText("verifier-v1")).toBeVisible();
        for (const digest of verificationReview.getAllByText("changed-digest-123")) expect(digest).toBeVisible();
        expect(verificationReview.getByText("/opt/atlas/services/demo")).toBeVisible();
        expect(verificationReview.getByText("abc123")).toBeVisible();
        expect(verificationReview.getByText("Review result", { exact: true })).toBeVisible();
        expect(verificationReview.getByText("Review status", { exact: true })).toBeVisible();
        expect(verificationReview.getByText("review-fingerprint-123")).toBeVisible();
        expect(verificationReview.getByText("Model-assisted review", { exact: true })).toBeVisible();
    });

    it.each([
        ["1 finding, 0 recommendations", "1 finding and no recommendations."],
        ["0 findings, 2 recommendations", "No findings and 2 recommendations."],
        ["2 findings, 1 recommendation", "2 findings and 1 recommendation."],
    ])("formats review counts as plain language: %s", async (evidenceSummary, expected) => {
        const current = workflow();
        mockedGetWorkflowDetail.mockResolvedValue(workflow({
            review: { ...current.review, evidence_summary: evidenceSummary },
        }));
        renderPage();

        const review = within(await screen.findByRole("region", { name: "Review" }));
        expect(review.getByText(expected, { exact: true })).toBeVisible();
    });

    it("keeps planned checks visible without empty future review panels", async () => {
        const empty = workflow();
        mockedGetWorkflowDetail.mockResolvedValue(workflow({
            verification_evidence: {
                ...empty.verification_evidence,
                verification_status: null,
                completed_time: null,
                executed_checks: [],
                check_results: [],
                repository_head: null,
                changed_files_digest: null,
            },
            review: {
                ...empty.review,
                review_result: null,
                review_status: null,
                approved: null,
                evidence_summary: null,
                changed_files: [],
                review_fingerprint: null,
            },
        }));
        renderPage();

        const verification = within(await screen.findByRole("region", { name: "Verification and review" }));
        expect(verification.getByRole("heading", { name: "Checks to run" })).toBeVisible();
        expect(verification.getAllByText("compose-config, compose-ps").length).toBeGreaterThan(0);
        expect(verification.queryByRole("heading", { name: "Check results" })).not.toBeInTheDocument();
        expect(verification.queryByRole("heading", { name: "Review" })).not.toBeInTheDocument();
        expect(verification.queryByRole("heading", { name: "Verification approval" })).not.toBeInTheDocument();
    });

    it("shows the next verification step without empty result fields", async () => {
        const empty = workflow();
        mockedGetWorkflowDetail.mockResolvedValue(workflowAwaitingVerification({
            verification_approval_status: "pending",
            verification_evidence: {
                ...empty.verification_evidence,
                verification_status: null,
                completed_time: null,
                executed_checks: [],
                check_results: [],
                repository_head: null,
                changed_files_digest: null,
            },
            review: {
                ...empty.review,
                review_result: null,
                review_status: null,
                approved: null,
                evidence_summary: null,
                changed_files: [],
                review_fingerprint: null,
                model_assisted_review: "Not applicable",
            },
        }));
        renderPage();

        const checkResults = within(await screen.findByRole("region", { name: "Check results" }));
        expect(checkResults.getByText("Review these checks. Approve them before Atlas runs them.")).toBeVisible();
        expect(checkResults.queryByText("Completed", { exact: true })).not.toBeInTheDocument();
        const review = within(screen.getByRole("region", { name: "Review" }));
        expect(review.getByText("Review results will appear after verification runs.")).toBeVisible();
        expect(screen.getByRole("button", { name: "Approve Verification" })).toBeVisible();
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

        await screen.findByText("Checks approved. Run them when you are ready.");
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

        await screen.findByText("Checks approved. Run them when you are ready.");
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

    it("does not show an empty commit stage before a commit request exists", async () => {
        mockedGetWorkflowDetail.mockResolvedValue(workflow());
        renderPage();

        await screen.findByRole("heading", { name: "Implementation approval" });

        expect(screen.queryByRole("heading", { name: "Commit details" })).not.toBeInTheDocument();
        expect(screen.queryByText("Commit details are unavailable for this workflow.")).not.toBeInTheDocument();
    });

    it("keeps the commit stage visible when its current request details are missing", async () => {
        mockedGetWorkflowDetail.mockResolvedValue(workflow({ workflow_state: "awaiting_commit_approval" }));
        renderPage();

        expect(await screen.findByRole("heading", { name: "Commit details" })).toBeInTheDocument();
        expect(screen.getByText("Commit details are unavailable for this workflow.")).toBeVisible();
        expect(screen.getByRole("heading", { name: "Commit approval" })).toBeVisible();
    });

    it("keeps commit message and files visible with technical references collapsed", async () => {
        mockedGetWorkflowDetail.mockResolvedValue(workflowAwaitingCommit());
        renderPage();

        expect(await screen.findByRole("heading", { name: "Commit details" })).toBeInTheDocument();
        const commitDetails = within(screen.getByRole("region", { name: "Commit details" }));
        expect(commitDetails.getByText("feature/atlas-agent")).toBeVisible();
        expect(commitDetails.getByText("feat(compose): update stack")).toBeVisible();
        expect(commitDetails.getByText("compose.yaml, services/demo/Dockerfile")).toBeVisible();
        const technicalDetails = commitDetails.getByText("Technical details").closest("details");
        expect(technicalDetails).not.toHaveAttribute("open");
        expect(commitDetails.getByText("approval-commit-workflow-123")).not.toBeVisible();
        expect(commitDetails.getByText("/opt/atlas")).not.toBeVisible();
        expect(commitDetails.getByText("abc123")).not.toBeVisible();
        expect(commitDetails.getByText("reviewed-fingerprint-123")).not.toBeVisible();
        expect(screen.queryByRole("textbox")).not.toBeInTheDocument();

        fireEvent.click(commitDetails.getByText("Technical details"));

        expect(technicalDetails).toHaveAttribute("open");
        expect(commitDetails.getByText("approval-commit-workflow-123")).toBeVisible();
        expect(commitDetails.getByText("/opt/atlas")).toBeVisible();
        expect(commitDetails.getByText("abc123")).toBeVisible();
        expect(commitDetails.getByText("reviewed-fingerprint-123")).toBeVisible();
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

        await screen.findByText("Commit approved. Record it when you are ready.");
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

        await screen.findByText("Commit approved. Record it when you are ready.");
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

        await screen.findByRole("heading", { name: "Commit details" });
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
        const technicalDetails = within(alert).getByText("Technical details").closest("details");
        expect(technicalDetails).not.toHaveAttribute("open");
        expect(technicalDetails).toHaveTextContent("approval already approved");
    });
});
