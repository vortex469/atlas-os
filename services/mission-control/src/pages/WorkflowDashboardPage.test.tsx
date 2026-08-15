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

        expect(await screen.findByText("workflow-123")).toBeInTheDocument();
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
        expect(screen.getAllByText("Mini workflow rail")[0]).toBeInTheDocument();
    });

    it("filters by state, source, candidate ID, workflow ID, and action required", async () => {
        vi.mocked(listWorkflows).mockResolvedValue(response([
            workflow(),
            workflow({ workflow_id: "workflow-999", workflow_state: "completed", candidate_id: "candidate-999" }),
        ]));

        renderDashboard();

        await screen.findByText("workflow-123");
        fireEvent.change(screen.getByLabelText("State"), { target: { value: "awaiting_implementation_approval" } });
        fireEvent.change(screen.getByLabelText("Source"), { target: { value: "candidate" } });
        fireEvent.change(screen.getByLabelText("Candidate ID"), { target: { value: "candidate-123" } });
        fireEvent.change(screen.getByLabelText("Workflow ID search"), { target: { value: "workflow-123" } });
        fireEvent.change(screen.getByLabelText("Action required"), { target: { value: "yes" } });
        fireEvent.click(screen.getByRole("button", { name: /Apply filters/i }));

        expect(screen.getByText("workflow-123")).toBeInTheDocument();
        expect(screen.queryByText("workflow-999")).not.toBeInTheDocument();
    });

    it("supports pagination when more returned workflows exist", async () => {
        const items = Array.from({ length: 11 }, (_, index) => workflow({ workflow_id: `workflow-${index}` }));
        vi.mocked(listWorkflows).mockResolvedValue(response(items));

        renderDashboard();

        expect(await screen.findByText("workflow-0")).toBeInTheDocument();
        expect(screen.queryByText("workflow-10")).not.toBeInTheDocument();
        fireEvent.click(screen.getByRole("button", { name: /Next/i }));

        expect(screen.getByText("workflow-10")).toBeInTheDocument();
    });

    it("refreshes manually and blocks overlapping refresh requests", async () => {
        vi.mocked(listWorkflows).mockResolvedValueOnce(response([workflow()]));
        let resolveRefresh: (value: WorkflowListResponse) => void = () => undefined;
        vi.mocked(listWorkflows).mockImplementationOnce(() => new Promise((resolve) => {
            resolveRefresh = resolve;
        }));

        renderDashboard();

        await screen.findByText("workflow-123");
        fireEvent.click(screen.getByRole("button", { name: /Refresh/i }));
        fireEvent.click(screen.getByRole("button", { name: /Refresh/i }));

        expect(listWorkflows).toHaveBeenCalledTimes(2);
        expect(screen.getByText("Refreshing workflows...")).toBeInTheDocument();
        resolveRefresh(response([workflow({ workflow_id: "workflow-refreshed" })]));
        expect(await screen.findByText("workflow-refreshed")).toBeInTheDocument();
    });

    it("renders empty, filtered empty, and Agent unavailable states", async () => {
        vi.mocked(listWorkflows).mockResolvedValueOnce(response([]));
        renderDashboard();
        expect(await screen.findByText("No workflows have been persisted yet.")).toBeInTheDocument();

        vi.mocked(listWorkflows).mockReset();
        vi.mocked(listWorkflows).mockResolvedValueOnce(response([workflow()]));
        renderDashboard();
        await screen.findByText("workflow-123");
        fireEvent.change(screen.getAllByLabelText("Workflow ID search")[1], { target: { value: "missing" } });
        fireEvent.click(screen.getAllByRole("button", { name: /Apply filters/i })[1]);
        expect(screen.getByText("No workflows match the current filters.")).toBeInTheDocument();

        vi.mocked(listWorkflows).mockReset();
        vi.mocked(listWorkflows).mockRejectedValueOnce(new Error("Atlas Agent unavailable"));
        renderDashboard();
        expect(await screen.findByRole("alert")).toHaveTextContent("Atlas Agent unavailable");
    });

    it("does not expose approval, execution, resume, or commit controls", async () => {
        vi.mocked(listWorkflows).mockResolvedValue(response([workflow()]));

        renderDashboard();

        await screen.findByText("workflow-123");
        const main = screen.getByRole("main");
        expect(within(main).queryByRole("button", { name: /Approve/i })).not.toBeInTheDocument();
        expect(within(main).queryByRole("button", { name: /Reject/i })).not.toBeInTheDocument();
        expect(within(main).queryByRole("button", { name: /Execute/i })).not.toBeInTheDocument();
        expect(within(main).queryByRole("button", { name: /Resume/i })).not.toBeInTheDocument();
        expect(within(main).queryByRole("button", { name: /Commit/i })).not.toBeInTheDocument();
    });
});
