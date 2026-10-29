import { fireEvent, render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { listWorkflows } from "../api/atlas-agent";
import type { WorkflowListResponse, WorkflowSummary } from "../types/atlasAgent";
import { WorkflowDashboardPage } from "./WorkflowDashboardPage";

vi.mock("../api/atlas-agent", async () => {
    const actual = await vi.importActual<typeof import("../api/atlas-agent")>("../api/atlas-agent");
    return {
        ...actual,
        listWorkflows: vi.fn(),
    };
});

const timeline = [
    { name: "Execution Candidate", status: "completed" },
    { name: "Planning Session", status: "completed" },
    { name: "Candidate Plan", status: "completed" },
    { name: "Workflow", status: "completed" },
    { name: "Implementation Approval", status: "current" },
    { name: "Execution", status: "waiting" },
    { name: "Verification", status: "waiting" },
    { name: "Review", status: "waiting" },
    { name: "Commit", status: "waiting" },
];

function workflow(overrides: Partial<WorkflowSummary> = {}): WorkflowSummary {
    return {
        workflow_id: "workflow-123",
        workflow_source: "candidate",
        workflow_state: "awaiting_implementation_approval",
        effect_kind: "repository_change",
        execution_intent: "update-compose-stack",
        candidate_id: "candidate-123",
        planning_session_id: "planning-123",
        repository: "/repo",
        target_id: "compose-stack-1",
        last_result_summary: "No result yet",
        timeline,
        ...overrides,
    };
}

function response(items: WorkflowSummary[], total = items.length, offset = 0): WorkflowListResponse {
    return {
        items,
        total,
        limit: 200,
        offset,
    };
}

function renderDashboard() {
    return render(
        <MemoryRouter>
            <WorkflowDashboardPage />
        </MemoryRouter>,
    );
}

describe("WorkflowDashboardPage", () => {
    beforeEach(() => {
        vi.useRealTimers();
        vi.mocked(listWorkflows).mockReset();
    });

    it("loads workflow summaries, summary counts, rails, and detail links", async () => {
        vi.mocked(listWorkflows).mockResolvedValue(response([
            workflow(),
            workflow({ workflow_id: "workflow-approval", workflow_state: "awaiting_approval" }),
            workflow({ workflow_id: "workflow-running", workflow_state: "executing", last_result_summary: "Execution running" }),
            workflow({ workflow_id: "workflow-verification", workflow_state: "awaiting_verification_approval" }),
            workflow({ workflow_id: "workflow-commit", workflow_state: "awaiting_commit_approval" }),
            workflow({ workflow_id: "workflow-blocked", workflow_state: "blocked", last_result_summary: "Blocked: stale candidate" }),
            workflow({ workflow_id: "workflow-completed", workflow_state: "completed", last_result_summary: "Commit completed" }),
        ]));

        renderDashboard();

        expect((await screen.findAllByRole("heading", { name: "Update Compose Stack" })).length).toBe(7);
        expect(Array.from((screen.getByLabelText("Workflow status") as HTMLSelectElement).options).map((option) => option.textContent)).toEqual([
            "Any status",
            "Ready for review",
            "Prepare change for review",
            "Review change, then run if approved",
            "Approved and ready to run",
            "Applying change",
            "Preparing verification",
            "Review checks, then run if approved",
            "Running checks",
            "Review commit, then record if approved",
            "Recording commit",
            "Blocked",
            "Approval rejected",
            "Completed",
        ]);
        expect(screen.getByText("Execution running")).toBeInTheDocument();
        expect(screen.getByText("Blocked: stale candidate")).toBeInTheDocument();
        expect(screen.getByText("Commit completed")).toBeInTheDocument();
        expect(screen.getAllByRole("link", { name: /Open Workflow/i })[0]).toHaveAttribute("href", "/workflows/workflow-123");
        expect(screen.getAllByText("Running")[0]).toBeInTheDocument();
        const counts = within(screen.getByRole("region", { name: "Workflow summary counts" }));
        expect(counts.getAllByRole("article")).toHaveLength(4);
        expect(counts.queryByText("Status unavailable", { exact: true })).not.toBeInTheDocument();
        expect(counts.getByText("Needs your input")).toBeInTheDocument();
        const needsInputCard = counts.getByText("Needs your input").closest("article");
        expect(within(needsInputCard as HTMLElement).getByText("4")).toBeInTheDocument();
        expect(screen.getByText("Review the checks. If approved, choose Run approved checks.")).toBeVisible();
        expect(screen.getByText("Review the commit. If approved, choose Record approved commit.")).toBeVisible();
        expect(screen.getAllByText("Blocked").length).toBeGreaterThan(0);
        expect(screen.getAllByText("Completed").length).toBeGreaterThan(0);
        expect(screen.getAllByText("Progress")[0]).toBeInTheDocument();

        const card = screen.getAllByRole("heading", { name: "Update Compose Stack" })[0].closest("article");
        expect(card).not.toBeNull();
        const details = within(card as HTMLElement);
        expect(details.getByText("Stage: Change approval")).toBeVisible();
        expect(details.getByText("Latest result")).toBeVisible();
        expect(details.getByText("Next step")).toBeVisible();
        expect(details.getByText("Review the change. If approved, choose Run approved change.")).toBeVisible();
        expect(details.queryByText("Your approval is needed")).not.toBeInTheDocument();
        expect(details.queryByText("Current State")).not.toBeInTheDocument();
        const disclosure = details.getByText("Workflow details", { exact: true });
        expect(disclosure.closest("details")).not.toHaveAttribute("open");
        expect(details.getByText("Workflow ID", { exact: true })).not.toBeVisible();
        expect(details.getByText("workflow-123", { exact: true })).not.toBeVisible();
        expect(details.getByText("Candidate ID", { exact: true })).not.toBeVisible();
        fireEvent.click(disclosure);
        expect(details.getByText("Workflow ID", { exact: true })).toBeVisible();
        expect(details.getByText("workflow-123", { exact: true })).toBeVisible();
        expect(details.getByText("Candidate ID", { exact: true })).toBeVisible();
        expect(details.getByText("candidate-123", { exact: true })).toBeVisible();

        const prepareCard = screen.getAllByRole("heading", { name: "Update Compose Stack" })[1].closest("article");
        expect(prepareCard).not.toBeNull();
        const prepareDetails = within(prepareCard as HTMLElement);
        expect(prepareDetails.getByText("Stage: Prepare change")).toBeVisible();
        expect(prepareDetails.getByText("Prepare the change for review.")).toBeVisible();
        expect(prepareDetails.queryByText("Your approval is needed")).not.toBeInTheDocument();
    });

    it("explains the safe next step for operational maintenance", async () => {
        vi.mocked(listWorkflows).mockResolvedValue(response([workflow({
            workflow_id: "maintenance-review",
            effect_kind: "operational_action",
            execution_intent: "restart-service",
            target_id: "VM 110",
        })]));

        renderDashboard();

        const title = await screen.findByRole("heading", { name: "Restart Service" });
        const card = title.closest("article");
        expect(card).not.toBeNull();
        const details = within(card as HTMLElement);
        expect(details.getByText("Stage: Maintenance request approval")).toBeVisible();
        expect(details.getByText("Review the maintenance request. If approved, choose Run approved maintenance.")).toBeVisible();
        expect(details.queryByText("Your approval is needed")).not.toBeInTheDocument();
        expect(details.queryByText("Stage: Change approval")).not.toBeInTheDocument();
    });

    it.each<[string | undefined, string]>([
        ["Review changes_required", "Review changes required"],
        ["Execution launch_failed", "Execution launch failed"],
        [undefined, "No result reported yet"],
    ])("shows a readable latest result for %s", async (last_result_summary, label) => {
        vi.mocked(listWorkflows).mockResolvedValue(response([workflow({ last_result_summary })]));

        renderDashboard();

        expect(await screen.findByText(label)).toBeInTheDocument();
    });

    it("keeps the common filters visible and tucks source and ID searches under More filters", async () => {
        vi.mocked(listWorkflows).mockResolvedValue(response([
            workflow(),
            workflow({ workflow_id: "workflow-999", workflow_state: "completed", candidate_id: "candidate-999", execution_intent: "restart-service" }),
        ]));

        renderDashboard();

        expect((await screen.findAllByRole("heading", { name: "Update Compose Stack" })).length).toBe(1);
        expect(screen.getByLabelText("Workflow status")).toBeVisible();
        expect(screen.getByRole("option", { name: "Prepare change for review" })).toBeInTheDocument();
        expect(screen.getByRole("option", { name: "Review checks, then run if approved" })).toBeInTheDocument();
        expect(screen.getByRole("option", { name: "Review commit, then record if approved" })).toBeInTheDocument();
        expect(screen.getByLabelText("Next step")).toBeVisible();
        const moreFilters = screen.getByText("More filters", { exact: true });
        expect(moreFilters.closest("details")).not.toHaveAttribute("open");
        expect(screen.getByLabelText("Started from")).not.toBeVisible();
        fireEvent.click(moreFilters);

        fireEvent.change(screen.getByLabelText("Workflow status"), { target: { value: "awaiting_implementation_approval" } });
        fireEvent.change(screen.getByLabelText("Started from"), { target: { value: "candidate" } });
        fireEvent.change(screen.getByLabelText("Candidate ID"), { target: { value: "candidate-123" } });
        fireEvent.change(screen.getByLabelText("Workflow ID contains"), { target: { value: "workflow-123" } });
        fireEvent.change(screen.getByLabelText("Next step"), { target: { value: "needed" } });
        expect(screen.getByText("These filter changes haven't been applied yet. Select Apply filters to update the workflow list.")).toBeVisible();
        expect(screen.getByRole("heading", { name: "Restart Service" })).toBeInTheDocument();
        fireEvent.click(screen.getByRole("button", { name: /Apply filters/i }));

        expect(screen.queryByText("These filter changes haven't been applied yet. Select Apply filters to update the workflow list.")).not.toBeInTheDocument();
        expect(screen.getByRole("heading", { name: "Update Compose Stack" })).toBeInTheDocument();
        expect(screen.queryByRole("heading", { name: "Restart Service" })).not.toBeInTheDocument();
        expect(screen.getByText("Additional filters are applied")).toBeVisible();
    });

    it("separates unknown workflow status from workflows with no current operator action", async () => {
        vi.mocked(listWorkflows).mockResolvedValue(response([
            workflow(),
            workflow({ workflow_id: "workflow-blocked", workflow_state: "blocked", execution_intent: "update-container-image" }),
            workflow({ workflow_id: "workflow-completed", workflow_state: "completed", execution_intent: "restart-service" }),
            workflow({ workflow_id: "workflow-running", workflow_state: "executing", execution_intent: null }),
            workflow({ workflow_id: "workflow-unknown", workflow_state: "future_state", execution_intent: "future-task" }),
        ]));

        renderDashboard();

        await screen.findAllByRole("heading", { name: "Update Compose Stack" });
        expect(screen.getByRole("option", { name: "No action needed right now" })).toBeInTheDocument();
        expect(screen.getByRole("option", { name: "Status unavailable" })).toBeInTheDocument();
        fireEvent.change(screen.getByLabelText("Next step"), { target: { value: "needed" } });
        fireEvent.click(screen.getByRole("button", { name: /Apply filters/i }));
        expect(screen.getByRole("heading", { name: "Update Compose Stack" })).toBeInTheDocument();
        expect(screen.getByRole("heading", { name: "Update Container Image" })).toBeInTheDocument();
        expect(screen.queryByRole("heading", { name: "Restart Service" })).not.toBeInTheDocument();
        expect(screen.queryByRole("heading", { name: "Future Task" })).not.toBeInTheDocument();
        let counts = within(screen.getByRole("region", { name: "Workflow summary counts" }));
        const countFor = (label: string) => {
            const card = counts.getByText(label, { exact: true }).closest("article");
            return within(card as HTMLElement).getByText(/^\d+$/).textContent;
        };
        expect(countFor("Needs your input")).toBe("1");
        expect(countFor("Blocked")).toBe("1");
        expect(counts.queryByText("Completed", { exact: true })).not.toBeInTheDocument();

        fireEvent.change(screen.getByLabelText("Next step"), { target: { value: "not_needed" } });
        fireEvent.click(screen.getByRole("button", { name: /Apply filters/i }));
        expect(screen.getByRole("heading", { name: "Restart Service" })).toBeInTheDocument();
        expect(screen.getByRole("heading", { name: "Repository change" })).toBeInTheDocument();
        expect(screen.queryByRole("heading", { name: "Update Container Image" })).not.toBeInTheDocument();
        expect(screen.queryByRole("heading", { name: "Future Task" })).not.toBeInTheDocument();
        counts = within(screen.getByRole("region", { name: "Workflow summary counts" }));
        expect(countFor("Completed")).toBe("1");
        expect(countFor("Running")).toBe("1");
        expect(counts.queryByText("Needs your input", { exact: true })).not.toBeInTheDocument();
        expect(counts.queryByText("Blocked", { exact: true })).not.toBeInTheDocument();

        fireEvent.change(screen.getByLabelText("Next step"), { target: { value: "unknown" } });
        fireEvent.click(screen.getByRole("button", { name: /Apply filters/i }));
        const unknownWorkflow = screen.getByRole("heading", { name: "Future Task" }).closest("article");
        expect(unknownWorkflow).not.toBeNull();
        expect(within(unknownWorkflow as HTMLElement).getByText("Stage: Status unavailable")).toBeVisible();
        const details = within(unknownWorkflow as HTMLElement).getByText("Workflow details", { exact: true });
        const disclosure = details.closest("details");
        expect(within(disclosure as HTMLElement).getByText("Reported workflow status")).not.toBeVisible();
        fireEvent.click(details);
        expect(within(disclosure as HTMLElement).getByText("future_state")).toBeVisible();
        expect(screen.queryByRole("heading", { name: "Restart Service" })).not.toBeInTheDocument();
        counts = within(screen.getByRole("region", { name: "Workflow summary counts" }));
        expect(countFor("Status unavailable")).toBe("1");
    });

    it("shows recognized intermediate and legacy states with clear stages and counts", async () => {
        vi.mocked(listWorkflows).mockResolvedValue(response([
            workflow({ workflow_id: "planned", workflow_state: "planned" }),
            workflow({ workflow_id: "patch-applied", workflow_state: "patch_applied_pending_verification", execution_intent: "restart-service" }),
            workflow({ workflow_id: "ready-to-run", workflow_state: "awaiting_execution", execution_intent: "update-container-image" }),
            workflow({ workflow_id: "rejected", workflow_state: "implementation_rejected", execution_intent: "start-service" }),
        ]));

        renderDashboard();

        const plannedCard = (await screen.findByRole("heading", { name: "Update Compose Stack" })).closest("article");
        expect(within(plannedCard as HTMLElement).getByText("Stage: Ready for review")).toBeVisible();
        expect(within(plannedCard as HTMLElement).getByText("Review the workflow before continuing.")).toBeVisible();

        const patchCard = screen.getByRole("heading", { name: "Restart Service" }).closest("article");
        expect(within(patchCard as HTMLElement).getByText("Stage: Preparing verification")).toBeVisible();
        expect(within(patchCard as HTMLElement).queryByText("Stage: Status unavailable")).not.toBeInTheDocument();

        const readyCard = screen.getByRole("heading", { name: "Update Container Image" }).closest("article");
        expect(within(readyCard as HTMLElement).getByText("Stage: Approved and ready to run")).toBeVisible();
        expect(within(readyCard as HTMLElement).getByText("The change is approved. Choose Run approved change when ready.")).toBeVisible();

        const rejectedCard = screen.getByRole("heading", { name: "Start Service" }).closest("article");
        expect(within(rejectedCard as HTMLElement).getByText("Stage: Approval rejected")).toBeVisible();
        const counts = within(screen.getByRole("region", { name: "Workflow summary counts" }));
        const countFor = (label: string) => {
            const card = counts.getByText(label, { exact: true }).closest("article");
            return within(card as HTMLElement).getByText(/^\d+$/).textContent;
        };
        expect(countFor("Needs your input")).toBe("2");
        expect(countFor("Running")).toBe("1");
        expect(countFor("Rejected")).toBe("1");
        expect(counts.queryByText("Status unavailable", { exact: true })).not.toBeInTheDocument();
    });

    it("supports pagination when more returned workflows exist", async () => {
        const items = Array.from({ length: 11 }, (_, index) => workflow({
            workflow_id: `workflow-${index}`,
            execution_intent: index === 10 ? "update-container-image" : "update-compose-stack",
        }));
        vi.mocked(listWorkflows).mockResolvedValue(response(items));

        renderDashboard();

        expect((await screen.findAllByRole("heading", { name: "Update Compose Stack" })).length).toBe(10);
        expect(screen.queryByRole("heading", { name: "Update Container Image" })).not.toBeInTheDocument();
        fireEvent.click(screen.getByRole("button", { name: /Next/i }));

        expect(screen.getByRole("heading", { name: "Update Container Image" })).toBeInTheDocument();
        expect(screen.getByText("Showing 11–11 of 11 loaded workflows")).toBeVisible();
        fireEvent.change(screen.getByLabelText("Workflow status"), { target: { value: "awaiting_implementation_approval" } });
        expect(screen.getByText("These filter changes haven't been applied yet. Select Apply filters to update the workflow list.")).toBeVisible();
        expect(screen.getByRole("button", { name: "Previous" })).toBeDisabled();
        expect(screen.getByRole("button", { name: "Next" })).toBeDisabled();

        fireEvent.click(screen.getByRole("button", { name: /Apply filters/i }));
        expect(screen.queryByText("These filter changes haven't been applied yet. Select Apply filters to update the workflow list.")).not.toBeInTheDocument();
        expect(screen.getByText("Showing 1–10 of 11 loaded workflows")).toBeVisible();
        expect(screen.getByRole("button", { name: "Next" })).toBeEnabled();
        expect(screen.queryByRole("heading", { name: "Update Container Image" })).not.toBeInTheDocument();
    });

    it("loads additional workflow batches and makes the loaded filter scope clear", async () => {
        const firstBatch = Array.from({ length: 200 }, (_, index) => workflow({
            workflow_id: `workflow-${String(index).padStart(3, "0")}`,
            workflow_state: index === 0 ? "executing" : "completed",
        }));
        const additional = workflow({ workflow_id: "workflow-older", execution_intent: "update-container-image" });
        vi.mocked(listWorkflows)
            .mockResolvedValueOnce(response(firstBatch, 201))
            .mockResolvedValueOnce(response([additional], 201, 200));

        renderDashboard();

        expect(await screen.findByText("Loaded 200 of 201 workflows. Summary counts and filters cover the loaded workflows only.")).toBeVisible();
        fireEvent.click(screen.getByRole("button", { name: "Load more workflows" }));
        expect(await screen.findByText("You loaded more than 200 workflows. Automatic refresh is paused; select Refresh to return to the first 200 and turn it back on.")).toBeVisible();
        expect(screen.getByText("Showing 1–10 of 201 loaded workflows")).toBeVisible();
        expect(screen.queryByRole("button", { name: "Load more workflows" })).not.toBeInTheDocument();

        fireEvent.click(screen.getByText("More filters", { exact: true }));
        fireEvent.change(screen.getByLabelText("Workflow ID contains"), { target: { value: "workflow-older" } });
        fireEvent.click(screen.getByRole("button", { name: "Apply filters" }));
        expect(screen.getByRole("heading", { name: "Update Container Image" })).toBeInTheDocument();
        expect(vi.mocked(listWorkflows)).toHaveBeenLastCalledWith({ limit: 200, offset: 200 });
    });

    it("keeps the loaded workflows visible when loading another batch fails", async () => {
        const firstBatch = Array.from({ length: 200 }, (_, index) => workflow({ workflow_id: `workflow-${index}` }));
        vi.mocked(listWorkflows)
            .mockResolvedValueOnce(response(firstBatch, 201))
            .mockRejectedValueOnce(new Error("private list error"))
            .mockResolvedValueOnce(response([workflow({ workflow_id: "workflow-200" })], 201, 200));

        renderDashboard();

        await screen.findByText("Loaded 200 of 201 workflows. Summary counts and filters cover the loaded workflows only.");
        fireEvent.click(screen.getByRole("button", { name: "Load more workflows" }));
        expect(await screen.findByRole("alert")).toHaveTextContent("Could not load more workflows. The workflows already shown are unchanged. Try again.");
        expect(screen.getAllByRole("heading", { name: "Update Compose Stack" }).length).toBe(10);

        fireEvent.click(screen.getByRole("button", { name: "Load more workflows" }));
        expect(await screen.findByText("Showing 1–10 of 201 loaded workflows")).toBeVisible();
        expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    });

    it("uses a plain fallback for missing references inside workflow details", async () => {
        vi.mocked(listWorkflows).mockResolvedValue(response([workflow({
            candidate_id: null,
            planning_session_id: null,
            repository: null,
            target_id: null,
            execution_intent: null,
        })]));

        renderDashboard();

        await screen.findByRole("heading", { name: "Repository change" });
        const card = screen.getByRole("heading", { name: "Repository change" }).closest("article");
        expect(card).not.toBeNull();
        const details = within(card as HTMLElement);
        fireEvent.click(details.getByText("Workflow details", { exact: true }));
        expect(details.getAllByText("Not available", { exact: true })).toHaveLength(3);
        expect(details.queryByText("Not exposed", { exact: true })).not.toBeInTheDocument();
    });

    it("refreshes manually and blocks overlapping refresh requests", async () => {
        vi.mocked(listWorkflows).mockResolvedValueOnce(response([workflow()]));
        let resolveRefresh: (value: WorkflowListResponse) => void = () => undefined;
        vi.mocked(listWorkflows).mockImplementationOnce(() => new Promise((resolve) => {
            resolveRefresh = resolve;
        }));

        renderDashboard();

        await screen.findByRole("heading", { name: "Update Compose Stack" });
        fireEvent.click(screen.getByRole("button", { name: /Refresh/i }));
        fireEvent.click(screen.getByRole("button", { name: /Refresh/i }));

        expect(listWorkflows).toHaveBeenCalledTimes(2);
        expect(screen.getByText("Refreshing workflows...")).toBeInTheDocument();
        expect(screen.getByRole("button", { name: "Refreshing…" })).toBeDisabled();
        resolveRefresh(response([workflow({ workflow_id: "workflow-refreshed", execution_intent: "restart-service" })]));
        expect(await screen.findByRole("heading", { name: "Restart Service" })).toBeInTheDocument();
        expect(screen.getByRole("button", { name: "Refresh" })).toBeEnabled();
    });

    it("renders empty, filtered empty, and Agent unavailable states", async () => {
        vi.mocked(listWorkflows).mockResolvedValueOnce(response([]));
        renderDashboard();
        expect(await screen.findByText("No workflows yet.")).toBeInTheDocument();
        expect(screen.queryByRole("region", { name: "Workflow summary counts" })).not.toBeInTheDocument();
        expect(screen.queryByText("0 workflows", { exact: true })).not.toBeInTheDocument();

        vi.mocked(listWorkflows).mockReset();
        vi.mocked(listWorkflows).mockResolvedValueOnce(response([workflow()]));
        renderDashboard();
        await screen.findByRole("heading", { name: "Update Compose Stack" });
        fireEvent.click(screen.getAllByText("More filters", { exact: true })[1]);
        fireEvent.change(screen.getAllByLabelText("Workflow ID contains")[1], { target: { value: "missing" } });
        fireEvent.click(screen.getAllByRole("button", { name: /Apply filters/i })[1]);
        expect(screen.getByText("No workflows match the current filters.")).toBeInTheDocument();
        expect(screen.queryByRole("region", { name: "Workflow summary counts" })).not.toBeInTheDocument();
        expect(screen.queryByText("0 workflows", { exact: true })).not.toBeInTheDocument();

        vi.mocked(listWorkflows).mockReset();
        vi.mocked(listWorkflows).mockRejectedValueOnce(new Error("Atlas Agent unavailable"));
        renderDashboard();
        const unavailableAlert = await screen.findByRole("alert");
        expect(unavailableAlert).toHaveTextContent("Workflows unavailable");
        expect(unavailableAlert).toHaveTextContent("Atlas couldn't load your workflows. Try again to get the latest list.");
        expect(screen.queryByText("Try loading your workflows again.")).not.toBeInTheDocument();
        const initialErrorDetails = within(unavailableAlert).getByText("Technical details").closest("details");
        expect(initialErrorDetails).not.toHaveAttribute("open");
        expect(within(initialErrorDetails as HTMLDetailsElement).getByText("Atlas Agent unavailable")).not.toBeVisible();
    });

    it("lets an operator retry an initial failure without reloading the page", async () => {
        vi.mocked(listWorkflows).mockRejectedValueOnce(new Error("Atlas Agent unavailable"));
        let resolveRetry!: (value: WorkflowListResponse) => void;
        vi.mocked(listWorkflows).mockImplementationOnce(() => new Promise((resolve) => { resolveRetry = resolve; }));
        renderDashboard();
        const initialAlert = await screen.findByRole("alert");
        expect(initialAlert).toHaveTextContent("Atlas couldn't load your workflows. Try again to get the latest list.");
        expect(screen.queryByText("Try loading your workflows again.")).not.toBeInTheDocument();
        fireEvent.click(screen.getByRole("button", { name: "Try again" }));
        expect(screen.getByRole("status")).toHaveTextContent("Loading workflows");
        expect(listWorkflows).toHaveBeenCalledTimes(2);
        resolveRetry(response([workflow({ workflow_state: "completed" })]));
        expect(await screen.findByRole("heading", { name: "Update Compose Stack" })).toBeInTheDocument();
        expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    });

    it("offers a retry when workflow response validation fails", async () => {
        vi.mocked(listWorkflows)
            .mockRejectedValueOnce(new Error("Malformed workflow list payload."))
            .mockResolvedValueOnce(response([workflow()]));
        renderDashboard();

        const alert = await screen.findByRole("alert");
        expect(alert).toHaveTextContent("Workflows unavailable");
        expect(alert).toHaveTextContent("Atlas couldn't load your workflows. Try again to get the latest list.");
        const technicalDetails = within(alert).getByText("Technical details").closest("details");
        expect(technicalDetails).not.toHaveAttribute("open");
        expect(screen.queryByRole("heading", { name: "This page could not load" })).not.toBeInTheDocument();

        fireEvent.click(within(alert).getByRole("button", { name: "Try again" }));

        expect(await screen.findByRole("heading", { name: "Update Compose Stack" })).toBeInTheDocument();
        expect(screen.queryByRole("alert")).not.toBeInTheDocument();
        expect(listWorkflows).toHaveBeenCalledTimes(2);
    });

    it("labels stale workflow data after a failed refresh and keeps the error optional", async () => {
        vi.mocked(listWorkflows).mockResolvedValueOnce(response([workflow()]))
            .mockRejectedValueOnce(new Error("Atlas Agent unavailable"))
            .mockResolvedValueOnce(response([workflow({ workflow_id: "workflow-refreshed", workflow_state: "completed", execution_intent: "restart-service" })]));
        renderDashboard();
        await screen.findByRole("heading", { name: "Update Compose Stack" });
        fireEvent.click(screen.getByRole("button", { name: "Refresh" }));

        const refreshAlert = await screen.findByRole("alert");
        expect(refreshAlert).toHaveTextContent("Could not refresh workflows");
        expect(refreshAlert).toHaveTextContent("The list and counts below show the last successfully loaded state.");
        expect(screen.getByRole("heading", { name: "Update Compose Stack" })).toBeInTheDocument();
        const details = within(refreshAlert).getByText("Technical details").closest("details");
        expect(details).not.toHaveAttribute("open");
        expect(within(details as HTMLDetailsElement).getByText("Atlas Agent unavailable")).not.toBeVisible();

        fireEvent.click(screen.getByRole("button", { name: "Refresh" }));
        expect(await screen.findByRole("heading", { name: "Restart Service" })).toBeInTheDocument();
        expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    });

    it("does not expose approval, execution, resume, or commit controls", async () => {
        vi.mocked(listWorkflows).mockResolvedValue(response([workflow()]));

        renderDashboard();

        await screen.findByRole("heading", { name: "Update Compose Stack" });
        const main = screen.getByRole("main");
        expect(within(main).queryByRole("button", { name: /Approve/i })).not.toBeInTheDocument();
        expect(within(main).queryByRole("button", { name: /Reject/i })).not.toBeInTheDocument();
        expect(within(main).queryByRole("button", { name: /Execute/i })).not.toBeInTheDocument();
        expect(within(main).queryByRole("button", { name: /Resume/i })).not.toBeInTheDocument();
        expect(within(main).queryByRole("button", { name: /Commit/i })).not.toBeInTheDocument();
    });
});
