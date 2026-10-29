import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { createMemoryRouter, MemoryRouter, Route, RouterProvider, Routes } from "react-router-dom";
import { StrictMode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { getWorkflowAudit, getWorkflowOperationalLifecycle } from "../api/atlas-agent";
import { operationalLifecycle } from "../test/operationalLifecycle";
import { workflowAudit as audit } from "../test/workflowAudit";
import type { WorkflowAuditResponse } from "../types/atlasAgent";
import { WorkflowAuditPage } from "./WorkflowAuditPage";

vi.mock("../api/atlas-agent", () => ({
    getAtlasAgentErrorMessage: (error: unknown, fallback: string) => error instanceof Error ? error.message : fallback,
    getWorkflowAudit: vi.fn(),
    getWorkflowOperationalLifecycle: vi.fn(),
}));

const mockedGetWorkflowAudit = vi.mocked(getWorkflowAudit);

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
    it("clears the previous audit while a new workflow loads", async () => {
        let resolveNext!: (value: WorkflowAuditResponse) => void;
        mockedGetWorkflowAudit.mockResolvedValueOnce(audit()).mockImplementationOnce(() => new Promise((resolve) => { resolveNext = resolve; }));
        const router = createMemoryRouter([{ path: "/workflows/:workflowId/audit", element: <WorkflowAuditPage /> }], { initialEntries: ["/workflows/workflow-123/audit"] });
        render(<RouterProvider router={router} />);
        await screen.findByRole("heading", { name: "Workflow audit" });
        await act(() => router.navigate("/workflows/next-workflow/audit"));
        expect(screen.queryByText("candidate-123")).not.toBeInTheDocument();
        expect(screen.getByRole("status")).toHaveTextContent("Loading workflow audit");
        await act(async () => resolveNext(audit({ workflow_id: "next-workflow", workflow: { ...audit().workflow, workflow_id: "next-workflow" } })));
        expect(await screen.findByRole("heading", { name: "Workflow audit" })).toBeInTheDocument();
    });

    it.each(["outer", "nested"])("refuses an audit with a mismatched %s workflow identity", async (field) => {
        const response = audit();
        if (field === "outer") response.workflow_id = "other";
        else response.workflow.workflow_id = "other";
        mockedGetWorkflowAudit.mockResolvedValue(response);
        renderAuditPage();
        const alert = await screen.findByRole("alert");
        expect(alert).toHaveTextContent("The returned record does not match this workflow link.");
        expect(alert).not.toHaveTextContent("Try loading it again.");
        expect(screen.queryByText("candidate-123")).not.toBeInTheDocument();
    });

    it("retries an unavailable audit with one read under Strict Mode", async () => {
        mockedGetWorkflowAudit.mockRejectedValueOnce(new Error("Unavailable")).mockResolvedValue(audit());
        render(<StrictMode><MemoryRouter initialEntries={["/workflows/workflow-123/audit"]}><Routes>
            <Route path="/workflows/:workflowId/audit" element={<WorkflowAuditPage />} />
        </Routes></MemoryRouter></StrictMode>);
        fireEvent.click(await screen.findByRole("button", { name: "Try again" }));
        await screen.findByRole("heading", { name: "Workflow audit" });
        expect(mockedGetWorkflowAudit).toHaveBeenCalledTimes(2);
    });

    it("keeps a late audit from an earlier workflow out of the current page", async () => {
        let resolveOld!: (value: WorkflowAuditResponse) => void;
        const next = audit({ workflow_id: "next-workflow", workflow: { ...audit().workflow, workflow_id: "next-workflow" } });
        mockedGetWorkflowAudit.mockImplementationOnce(() => new Promise((resolve) => { resolveOld = resolve; })).mockResolvedValue(next);
        const router = createMemoryRouter([{ path: "/workflows/:workflowId/audit", element: <WorkflowAuditPage /> }], { initialEntries: ["/workflows/workflow-123/audit"] });
        render(<RouterProvider router={router} />);
        await waitFor(() => expect(mockedGetWorkflowAudit).toHaveBeenCalledWith("workflow-123"));
        await act(() => router.navigate("/workflows/next-workflow/audit"));
        await screen.findByRole("heading", { name: "Workflow audit" });
        await act(async () => resolveOld(audit()));
        expect(screen.getByRole("heading", { name: "Workflow audit" })).toBeInTheDocument();
    });

    beforeEach(() => {
        vi.clearAllMocks();
        mockedGetWorkflowAudit.mockResolvedValue(audit());
        vi.mocked(getWorkflowOperationalLifecycle).mockReset();
    });

    it("shows maintenance lifecycle instead of repository artifacts", async () => {
        mockedGetWorkflowAudit.mockResolvedValue(audit({ effect_kind: "operational_action" }));
        vi.mocked(getWorkflowOperationalLifecycle).mockResolvedValue(operationalLifecycle({ workflow_id: "workflow-123" }));
        renderAuditPage();
        expect(await screen.findByRole("heading", { name: "Verified" })).toBeInTheDocument();
        expect(screen.getByRole("heading", { name: "Maintenance audit" })).toBeInTheDocument();
        expect(screen.getByText(/Maintenance status:/)).toBeInTheDocument();
        expect(screen.queryByRole("heading", { name: "Commit details" })).not.toBeInTheDocument();
        expect(screen.queryByRole("heading", { name: "Change request" })).not.toBeInTheDocument();
        expect(screen.queryByRole("button", { name: /approve|run|resume/i })).not.toBeInTheDocument();
    });

    it.each([
        ["awaiting_implementation_approval", "pending", "Maintenance request needs approval."],
        ["awaiting_implementation_approval", "approved", "Maintenance request is approved. Run approved maintenance when you are ready."],
        ["awaiting_implementation_approval", "rejected", "Maintenance request approval was rejected."],
        ["awaiting_execution", "approved", "Maintenance request is approved and ready to run."],
        ["executing", "approved", "Maintenance is running."],
        ["completed", "approved", "Maintenance workflow completed."],
    ])("uses maintenance terms in the audit for %s / %s", async (workflow_state, approval, message) => {
        mockedGetWorkflowAudit.mockResolvedValue(audit({
            effect_kind: "operational_action",
            workflow_state,
            approvals: { ...audit().approvals, implementation: { status: approval, approval_id: "approval-maintenance" } },
        }));
        vi.mocked(getWorkflowOperationalLifecycle).mockResolvedValue(operationalLifecycle({ workflow_id: "workflow-123" }));
        renderAuditPage();

        const status = await screen.findByText(/Maintenance status:/);
        expect(status).toHaveTextContent(message);
        expect(screen.queryByText(/Maintenance action/)).not.toBeInTheDocument();
        expect(status).toBeVisible();
    });

    it("keeps invalid maintenance audit codes under technical details", async () => {
        mockedGetWorkflowAudit.mockResolvedValue(audit({
            effect_kind: "operational_action",
            validation: {
                valid: false,
                failure_code: "maintenance_chain_mismatch",
                failure_stage: "verification",
            },
        }));
        vi.mocked(getWorkflowOperationalLifecycle).mockResolvedValue(operationalLifecycle({ workflow_id: "workflow-123" }));
        renderAuditPage();

        expect(await screen.findByText("This audit record is inconsistent. Review its technical details.")).toBeInTheDocument();
        const technicalDetails = screen.getByText("Technical details").closest("details");
        expect((technicalDetails as HTMLDetailsElement).open).toBe(false);
        fireEvent.click(within(technicalDetails as HTMLElement).getByText("Technical details"));
        expect(within(technicalDetails as HTMLElement).getByText("maintenance_chain_mismatch")).toBeInTheDocument();
        expect(within(technicalDetails as HTMLElement).getByText("verification")).toBeInTheDocument();
    });

    it("rejects foreign maintenance evidence and permits a read-only refresh", async () => {
        mockedGetWorkflowAudit.mockResolvedValue(audit({ effect_kind: "operational_action" }));
        vi.mocked(getWorkflowOperationalLifecycle).mockResolvedValueOnce(operationalLifecycle({ target_label: "Foreign target" }))
            .mockResolvedValueOnce(operationalLifecycle({ workflow_id: "workflow-123" }));
        renderAuditPage();
        expect(await screen.findByText("Matching maintenance evidence is unavailable. Refresh to check again.")).toBeInTheDocument();
        expect(screen.queryByText("Foreign target")).not.toBeInTheDocument();
        expect(screen.queryByRole("button", { name: "Refresh maintenance evidence" })).not.toBeInTheDocument();
        fireEvent.click(screen.getByRole("button", { name: "Check status again" }));
        expect(await screen.findByRole("heading", { name: "Verified" })).toBeInTheDocument();
    });

    it("shows a concise completed audit and keeps identifiers with their recorded details", async () => {
        renderAuditPage();

        expect(await screen.findByRole("heading", { name: "Workflow audit" })).toBeInTheDocument();
        expect(screen.getByText("Read-only record")).toBeInTheDocument();
        expect(screen.getAllByText("Workflow status").length).toBe(1);
        expect(screen.getAllByText("Completed").length).toBeGreaterThan(0);
        expect(screen.queryByText("Overall audit status")).not.toBeInTheDocument();
        expect(screen.getAllByText("Audit validation").length).toBe(1);
        expect(screen.queryByText(/Overall chain state:/)).not.toBeInTheDocument();
        expect(screen.getAllByText("Valid").length).toBeGreaterThan(0);

        const technicalDetails = screen.getByText("Technical details").closest("details");
        expect(technicalDetails).not.toBeNull();
        expect((technicalDetails as HTMLDetailsElement).open).toBe(false);
        fireEvent.click(within(technicalDetails as HTMLElement).getByText("Technical details"));
        expect((technicalDetails as HTMLDetailsElement).open).toBe(true);
        expect(within(technicalDetails as HTMLElement).getByText("workflow-123")).toBeInTheDocument();

        const candidateStage = screen.getByRole("region", { name: "Change proposal, Completed" });
        expect(candidateStage).not.toHaveAttribute("open");
        fireEvent.click(within(candidateStage).getByText("Change proposal", { exact: true }));
        expect(candidateStage).toHaveAttribute("open");
        expect(within(candidateStage).getByText("candidate-123")).toBeVisible();

        const commitStage = screen.getByRole("region", { name: "Commit result, Completed" });
        expect(commitStage).not.toHaveAttribute("open");
        fireEvent.click(within(commitStage).getByText("Commit result", { exact: true }));
        expect(within(commitStage).getByText("def456")).toBeVisible();
        expect(within(commitStage).getByText("Commit SHA")).toBeInTheDocument();
    });

    it("shows audit timestamps as local times with their exact source instants", async () => {
        renderAuditPage();
        await screen.findByRole("heading", { name: "Workflow audit" });

        const planningStage = screen.getByRole("region", { name: "Planning, Completed" });
        fireEvent.click(within(planningStage).getByText("Planning", { exact: true }));
        for (const [label, timestamp] of [
            ["Created (local time)", "2026-08-01T10:00:00Z"],
            ["Planning completed (local time)", "2026-08-01T10:00:30Z"],
        ]) {
            const time = within(planningStage).getByText(label).parentElement?.querySelector("time");
            expect(time).toHaveAttribute("datetime", timestamp);
            expect(time).toHaveTextContent(new Date(timestamp).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" }));
        }

        const verificationStage = screen.getByRole("region", { name: "Checks to run, Completed" });
        fireEvent.click(within(verificationStage).getByText("Checks to run", { exact: true }));
        const started = within(verificationStage).getByText("Verification started (local time)").parentElement?.querySelector("time");
        const completed = within(verificationStage).getByText("Verification completed (local time)").parentElement?.querySelector("time");
        expect(started).toHaveAttribute("datetime", "2026-08-01T10:01:00Z");
        expect(completed).toHaveAttribute("datetime", "2026-08-01T10:02:00Z");
    });

    it("marks malformed audit timestamps unavailable instead of exposing raw values", async () => {
        const response = audit();
        response.planning.created_at = "2026-02-30T10:00:00Z";
        mockedGetWorkflowAudit.mockResolvedValue(response);
        renderAuditPage();
        await screen.findByRole("heading", { name: "Workflow audit" });

        const planningStage = screen.getByRole("region", { name: "Planning, Completed" });
        fireEvent.click(within(planningStage).getByText("Planning", { exact: true }));
        expect(within(planningStage).getByText("Created (local time)").parentElement).toHaveTextContent("Time unavailable");
        expect(within(planningStage).queryByText("2026-02-30T10:00:00Z")).not.toBeInTheDocument();
    });

    it("shows in-progress stages as Not started", async () => {
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

        expect(await screen.findByRole("region", { name: "Review results, Not started" })).toBeInTheDocument();
        expect(screen.queryByRole("region", { name: "Review results, Not reached" })).not.toBeInTheDocument();
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

    it("shows blocked reason in overview when workflow is blocked", async () => {
        mockedGetWorkflowAudit.mockResolvedValue(
            audit({
                blocked_reason: "Blocked: safety gate open failed due to policy",
                workflow_state: "blocked",
            }),
        );
        renderAuditPage();

        expect(await screen.findByText("Blocked reason")).toBeInTheDocument();
        expect(screen.getByText("Blocked: safety gate open failed due to policy")).toBeInTheDocument();
    });

    it("shows a pending stage approval separately from audit validation", async () => {
        mockedGetWorkflowAudit.mockResolvedValue(
            audit({
                workflow_state: "awaiting_verification_approval",
                approvals: {
                    ...audit().approvals,
                    verification: { status: "pending", approval_id: null },
                },
                validation: {
                    valid: true,
                    failure_code: null,
                    failure_stage: null,
                },
            }),
        );
        renderAuditPage();

        expect(await screen.findByText("Workflow status")).toBeInTheDocument();
        expect(screen.getByText("Verification needs approval.")).toBeInTheDocument();
        expect(screen.getByText("Valid")).toBeInTheDocument();
        expect(screen.getByText("Review the recorded stages and results. Open a stage to inspect its details; this page does not change the workflow.")).toBeInTheDocument();
    });

    it("shows the next action after verification approval", async () => {
        mockedGetWorkflowAudit.mockResolvedValue(
            audit({ workflow_state: "awaiting_verification_approval" }),
        );
        renderAuditPage();

        expect(await screen.findByText("Verification is approved. Run the approved checks when you are ready.")).toBeInTheDocument();
    });

    it("keeps workflow status separate from audit validation when validation is invalid", async () => {
        mockedGetWorkflowAudit.mockResolvedValue(
            audit({
                workflow_state: "blocked",
                validation: {
                    valid: false,
                    failure_code: "candidate_plan_mismatch",
                    failure_stage: "candidate",
                },
            }),
        );
        renderAuditPage();

        expect(await screen.findByText("Workflow is blocked. Review the recorded stages and results below.")).toBeInTheDocument();
        expect(screen.getByText("Workflow status")).toBeInTheDocument();
        expect(screen.queryByText("Overall audit status")).not.toBeInTheDocument();
        expect(screen.getByText("Invalid")).toBeInTheDocument();
        expect(screen.getByRole("alert")).toHaveTextContent("This audit record is inconsistent.");
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

        expect(await screen.findByText("This audit record is inconsistent. Review the flagged stage below and its recorded details.")).toBeInTheDocument();
        expect(screen.getByText("This stage is inconsistent with audit-chain validation.")).toBeInTheDocument();
        expect((await screen.findAllByText(/Inconsistent/i)).length).toBeGreaterThan(1);
        const technicalDetails = screen.getByText("Technical details").closest("details");
        expect((technicalDetails as HTMLDetailsElement).open).toBe(false);
        fireEvent.click(within(technicalDetails as HTMLElement).getByText("Technical details"));
        expect(within(technicalDetails as HTMLElement).getByText("candidate_plan_mismatch")).toBeInTheDocument();
    });

    it("shows workflow not found", async () => {
        mockedGetWorkflowAudit.mockResolvedValue(null);
        renderAuditPage("/workflows/workflow-missing/audit");

        expect(await screen.findByRole("alert")).toHaveTextContent("Workflow not found");
    });

    it("shows agent unavailable alert", async () => {
        mockedGetWorkflowAudit.mockRejectedValue(new Error("Atlas Agent unavailable."));
        renderAuditPage();

        const alert = await screen.findByRole("alert");
        expect(alert).toHaveTextContent("Atlas couldn’t load this workflow’s history. Try again to see its activity.");
        expect(alert).toHaveTextContent("Workflow history unavailable");
        const technicalDetails = within(alert).getByText("Technical details").closest("details");
        expect(technicalDetails).not.toHaveAttribute("open");
        expect(within(technicalDetails as HTMLElement).getByText("Atlas Agent unavailable.")).not.toBeVisible();
        fireEvent.click(within(technicalDetails as HTMLElement).getByText("Technical details"));
        expect(within(technicalDetails as HTMLElement).getByText("Atlas Agent unavailable.")).toBeInTheDocument();
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

        expect(await screen.findByRole("region", { name: "Change proposal, Completed" })).toBeInTheDocument();
        expect(screen.queryByRole("button", { name: /approve/i })).not.toBeInTheDocument();
        expect(screen.queryByRole("button", { name: /reject/i })).not.toBeInTheDocument();
        expect(screen.queryByRole("button", { name: /execute/i })).not.toBeInTheDocument();
        expect(screen.queryByRole("button", { name: /resume/i })).not.toBeInTheDocument();
        expect(screen.queryByRole("button", { name: /commit/i })).not.toBeInTheDocument();
    });
});
