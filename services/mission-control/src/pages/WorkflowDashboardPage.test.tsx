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

function response(items: WorkflowSummary[]): WorkflowListResponse {
    return {
        items,
        total: items.length,
        limit: 200,
        offset: 0,
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
            workflow({ workflow_id: "workflow-running", workflow_state: "executing", last_result_summary: "Execution running" }),
            workflow({ workflow_id: "workflow-verification", workflow_state: "awaiting_verification_approval" }),
            workflow({ workflow_id: "workflow-commit", workflow_state: "awaiting_commit_approval" }),
            workflow({ workflow_id: "workflow-blocked", workflow_state: "blocked", last_result_summary: "Blocked: stale candidate" }),
            workflow({ workflow_id: "workflow-completed", workflow_state: "completed", last_result_summary: "Commit completed" }),
        ]));

        renderDashboard();

        expect((await screen.findAllByRole("heading", { name: "Update Compose Stack" })).length).toBe(6);
        expect(screen.getByText("Execution running")).toBeInTheDocument();
        expect(screen.getByText("Blocked: stale candidate")).toBeInTheDocument();
        expect(screen.getByText("Commit completed")).toBeInTheDocument();
        expect(screen.getAllByRole("link", { name: /Open Workflow/i })[0]).toHaveAttribute("href", "/workflows/workflow-123");
        expect(screen.getAllByText("Running")[0]).toBeInTheDocument();
        expect(screen.getByText("Waiting for implementation approval")).toBeInTheDocument();
        expect(screen.getByText("Waiting for verification approval")).toBeInTheDocument();
        expect(screen.getByText("Waiting for commit approval")).toBeInTheDocument();
        expect(screen.getAllByText("Blocked").length).toBeGreaterThan(0);
        expect(screen.getAllByText("Completed").length).toBeGreaterThan(0);
        expect(screen.getAllByText("Progress")[0]).toBeInTheDocument();

        const card = screen.getAllByRole("heading", { name: "Update Compose Stack" })[0].closest("article");
        expect(card).not.toBeNull();
        const details = within(card as HTMLElement);
        expect(details.getByText("Stage: Change approval")).toBeVisible();
        expect(details.getByText("Latest result")).toBeVisible();
        expect(details.getByText("Your approval is needed")).toBeVisible();
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
    });

    it("keeps the common filters visible and tucks source and ID searches under More filters", async () => {
        vi.mocked(listWorkflows).mockResolvedValue(response([
            workflow(),
            workflow({ workflow_id: "workflow-999", workflow_state: "completed", candidate_id: "candidate-999", execution_intent: "restart-service" }),
        ]));

        renderDashboard();

        expect((await screen.findAllByRole("heading", { name: "Update Compose Stack" })).length).toBe(1);
        expect(screen.getByLabelText("Workflow status")).toBeVisible();
        expect(screen.getByLabelText("Approval status")).toBeVisible();
        const moreFilters = screen.getByText("More filters", { exact: true });
        expect(moreFilters.closest("details")).not.toHaveAttribute("open");
        expect(screen.getByLabelText("Started from")).not.toBeVisible();
        fireEvent.click(moreFilters);

        fireEvent.change(screen.getByLabelText("Workflow status"), { target: { value: "awaiting_implementation_approval" } });
        fireEvent.change(screen.getByLabelText("Started from"), { target: { value: "candidate" } });
        fireEvent.change(screen.getByLabelText("Candidate ID"), { target: { value: "candidate-123" } });
        fireEvent.change(screen.getByLabelText("Workflow ID contains"), { target: { value: "workflow-123" } });
        fireEvent.change(screen.getByLabelText("Approval status"), { target: { value: "waiting" } });
        expect(screen.getByText("These filter changes haven't been applied yet. Select Apply filters to update the workflow list.")).toBeVisible();
        expect(screen.getByRole("heading", { name: "Restart Service" })).toBeInTheDocument();
        fireEvent.click(screen.getByRole("button", { name: /Apply filters/i }));

        expect(screen.queryByText("These filter changes haven't been applied yet. Select Apply filters to update the workflow list.")).not.toBeInTheDocument();
        expect(screen.getByRole("heading", { name: "Update Compose Stack" })).toBeInTheDocument();
        expect(screen.queryByRole("heading", { name: "Restart Service" })).not.toBeInTheDocument();
        expect(screen.getByText("Additional filters are applied")).toBeVisible();
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
        resolveRefresh(response([workflow({ workflow_id: "workflow-refreshed", execution_intent: "restart-service" })]));
        expect(await screen.findByRole("heading", { name: "Restart Service" })).toBeInTheDocument();
    });

    it("renders empty, filtered empty, and Agent unavailable states", async () => {
        vi.mocked(listWorkflows).mockResolvedValueOnce(response([]));
        renderDashboard();
        expect(await screen.findByText("No workflows yet.")).toBeInTheDocument();
        expect(screen.queryByText("0 workflows", { exact: true })).not.toBeInTheDocument();

        vi.mocked(listWorkflows).mockReset();
        vi.mocked(listWorkflows).mockResolvedValueOnce(response([workflow()]));
        renderDashboard();
        await screen.findByRole("heading", { name: "Update Compose Stack" });
        fireEvent.click(screen.getAllByText("More filters", { exact: true })[1]);
        fireEvent.change(screen.getAllByLabelText("Workflow ID contains")[1], { target: { value: "missing" } });
        fireEvent.click(screen.getAllByRole("button", { name: /Apply filters/i })[1]);
        expect(screen.getByText("No workflows match the current filters.")).toBeInTheDocument();
        expect(screen.queryByText("0 workflows", { exact: true })).not.toBeInTheDocument();

        vi.mocked(listWorkflows).mockReset();
        vi.mocked(listWorkflows).mockRejectedValueOnce(new Error("Atlas Agent unavailable"));
        renderDashboard();
        const unavailableAlert = await screen.findByRole("alert");
        expect(unavailableAlert).toHaveTextContent("Workflows unavailable");
        expect(unavailableAlert).toHaveTextContent("Mission Control could not load the workflow list.");
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
        expect(initialAlert).toHaveTextContent("Mission Control could not load the workflow list.");
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
        expect(alert).toHaveTextContent("Mission Control could not load the workflow list.");
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
