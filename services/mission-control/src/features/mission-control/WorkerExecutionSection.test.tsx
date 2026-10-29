import { fireEvent, render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";
import type { WorkflowListResponse, WorkflowSummary } from "../../types/atlasAgent";
import { WorkerExecutionSection } from "./WorkerExecutionSection";
import { isWorkflowEvidencePage } from "./workerExecutionEvidence";

function workflow(id: string, state = "executing", stage = "current", intent: string | null = null): WorkflowSummary {
    return { workflow_id: id, workflow_state: state, workflow_source: "candidate",
        effect_kind: "repository_change", execution_intent: intent, candidate_id: null,
        planning_session_id: null, repository: null, target_id: null,
        last_result_summary: "Commit completed", timeline: [{ name: "Execution", status: stage }] };
}
function page(items: WorkflowSummary[]): WorkflowListResponse {
    return { items, total: items.length, offset: 0, limit: 200 };
}
function view(evidence: unknown, unavailable = false, loading = false) {
    return render(<MemoryRouter><WorkerExecutionSection evidence={{ data: evidence, unavailable }} loading={loading} /></MemoryRouter>);
}

describe("Work activity summary", () => {
    it("shows one checking message without unavailable count placeholders during first load", () => {
        view(undefined, false, true);
        const section = screen.getByRole("region", { name: "Work activity" });
        expect(within(section).getByText("Checking workflow status…")).toBeVisible();
        expect(within(section).queryByText("Could not confirm the full workflow list, so running and blocked counts are hidden.")).not.toBeInTheDocument();
        expect(within(section).queryByText("Running workflows", { exact: true })).not.toBeInTheDocument();
        expect(within(section).queryByText("Blocked workflows", { exact: true })).not.toBeInTheDocument();
    });
    it("shows one unavailable message instead of repeating it as two unavailable counts", () => {
        view(undefined, true);
        const section = screen.getByRole("region", { name: "Work activity" });
        expect(within(section).getByText("Workflow status could not be loaded.")).toBeVisible();
        expect(within(section).queryByText("Running workflows", { exact: true })).not.toBeInTheDocument();
        expect(within(section).queryByText("Blocked workflows", { exact: true })).not.toBeInTheDocument();
    });
    it("shows an idle observation without inventing worker health or queue depth", () => {
        view(page([]));
        const section = screen.getByRole("region", { name: "Work activity" });
        expect(within(section).getByText("Running workflows").nextElementSibling).toHaveTextContent("0");
        expect(within(section).getByText("Blocked workflows").nextElementSibling).toHaveTextContent("0");
        expect(within(section).getByText("No running workflows are listed.")).toBeInTheDocument();
        expect(within(section).getByText("This read-only summary shows workflow progress and results. It doesn't show whether a worker can take new work.")).toBeInTheDocument();
        expect(within(section).queryByText("Worker availability is unknown.")).not.toBeInTheDocument();
        expect(within(section).getByText("Queue size").closest("details")?.open).toBe(false);
        fireEvent.click(within(section).getByText("More workflow details"));
        expect(within(section).getByText("Queue size")).toBeInTheDocument();
        expect(within(section).getByText("Not reported")).toBeInTheDocument();
    });
    it("distinguishes executing from verification and links to encoded detail routes", () => {
        view(page([workflow("a/b?#", "executing", "current", "restart-service"), workflow("verify", "verifying", "completed")]));
        const section = screen.getByRole("region", { name: "Work activity" });
        expect(within(section).getAllByText("Running workflows")[0].nextElementSibling).toHaveTextContent("1");
        const workflowLink = within(section).getByRole("link", { name: "Restart Service · Running" });
        expect(workflowLink).toHaveAttribute("href", "/workflows/a%2Fb%3F%23");
        const workflowRow = workflowLink.closest("li");
        const workflowId = within(workflowRow!).getByText(/Workflow ID: a\/b\?#/);
        expect(workflowId).not.toBeVisible();
        fireEvent.click(within(workflowRow!).getByText("Technical details"));
        expect(workflowId).toBeVisible();
        expect(screen.getByRole("link", { name: "Review workflows →" })).toHaveAttribute("href", "/workflows");
    });
    it("shows blocked workflows without claiming that execution started", () => {
        view(page([workflow("blocked", "blocked", "waiting")]));
        const section = screen.getByRole("region", { name: "Work activity" });
        expect(within(section).getAllByText("Blocked workflows")[0].nextElementSibling).toHaveTextContent("1");
        expect(within(section).getByRole("link", { name: "Workflow · Blocked" })).toHaveAttribute("href", "/workflows/blocked");
        fireEvent.click(within(section).getByText("More workflow details"));
        expect(within(section).getByText(/A workflow can be blocked before it starts/)).toBeInTheDocument();
        expect(screen.getByText("No execution outcomes recorded")).toBeInTheDocument();
    });
    it("uses execution evidence, not the latest commit result, and explains why results are not newest first", () => {
        view(page([workflow("success", "completed", "completed", "restart-service"), workflow("failure", "blocked", "failed", "update-container-image")]));
        fireEvent.click(screen.getByText("More workflow details"));
        const successLink = screen.getByRole("link", { name: "Restart Service · Execution completed" });
        const failedLink = screen.getByRole("link", { name: "Update Container Image · Execution failed" });
        expect(successLink).toHaveAttribute("href", "/workflows/success");
        expect(failedLink).toHaveAttribute("href", "/workflows/failure");
        const successRow = successLink.closest("li");
        const successId = within(successRow!).getByText("Workflow ID: success");
        expect(successId).not.toBeVisible();
        fireEvent.click(within(successRow!).getByText("Technical details"));
        expect(successId).toBeVisible();
        expect(screen.queryByText("Commit completed")).not.toBeInTheDocument();
        expect(screen.getByText(/Finish times aren't available, so results aren't shown newest first/)).toBeInTheDocument();
    });
    it("puts failed execution outcomes before completed outcomes in the short preview", () => {
        view(page([
            workflow("a-completed", "completed", "completed", "restart-service"),
            workflow("b-completed", "completed", "completed", "restart-service"),
            workflow("c-completed", "completed", "completed", "restart-service"),
            workflow("z-failed", "blocked", "failed", "update-compose-stack"),
        ]));
        const section = within(screen.getByRole("region", { name: "Work activity" }));
        fireEvent.click(section.getByText("More workflow details"));
        const outcomes = within(section.getByRole("list", { name: "Recorded execution outcomes" }));
        const first = within(outcomes.getAllByRole("listitem")[0]);

        expect(first.getByRole("link", { name: "Update Compose Stack · Execution failed" })).toBeVisible();
        expect(section.getByRole("button", { name: "Show all 4 recorded execution outcomes" })).toBeVisible();
    });
    it("lets operators expand each workflow and outcome list beyond three records", () => {
        const records = [
            ...Array.from({ length: 5 }, (_, index) => workflow(`running-${index}`, "executing")),
            ...Array.from({ length: 5 }, (_, index) => workflow(`blocked-${index}`, "blocked", "waiting")),
            ...Array.from({ length: 5 }, (_, index) => workflow(`outcome-${index}`, "completed", "completed")),
        ];
        view(page(records));

        const section = within(screen.getByRole("region", { name: "Work activity" }));
        const running = section.getByRole("list", { name: "Running workflows" });
        expect(within(running).getAllByRole("listitem")).toHaveLength(3);
        fireEvent.click(section.getByRole("button", { name: "Show all 5 running workflows" }));
        expect(within(running).getAllByRole("listitem")).toHaveLength(5);
        fireEvent.click(section.getByRole("button", { name: "Show fewer running workflows" }));
        expect(within(running).getAllByRole("listitem")).toHaveLength(3);

        const blocked = section.getByRole("list", { name: "Blocked workflows" });
        expect(within(blocked).getAllByRole("listitem")).toHaveLength(3);
        fireEvent.click(section.getByRole("button", { name: "Show all 5 blocked workflows" }));
        expect(within(blocked).getAllByRole("listitem")).toHaveLength(5);
        fireEvent.click(section.getByRole("button", { name: "Show fewer blocked workflows" }));
        expect(within(blocked).getAllByRole("listitem")).toHaveLength(3);

        fireEvent.click(section.getByText("More workflow details"));
        const outcomes = section.getByRole("list", { name: "Recorded execution outcomes" });
        expect(within(outcomes).getAllByRole("listitem")).toHaveLength(3);
        fireEvent.click(section.getByRole("button", { name: "Show all 5 recorded execution outcomes" }));
        expect(within(outcomes).getAllByRole("listitem")).toHaveLength(5);
        fireEvent.click(section.getByRole("button", { name: "Show fewer recorded execution outcomes" }));
        expect(within(outcomes).getAllByRole("listitem")).toHaveLength(3);
    });
    it("hides old observations on refresh failure and recovers on a new response", () => {
        const { rerender } = view(page([workflow("old")]), true);
        expect(screen.queryByRole("link", { name: "Workflow · Running" })).not.toBeInTheDocument();
        expect(screen.getByText("Workflow status could not be loaded.")).toBeInTheDocument();
        expect(screen.queryByText("Running workflows", { exact: true })).not.toBeInTheDocument();
        expect(screen.queryByText("Blocked workflows", { exact: true })).not.toBeInTheDocument();
        rerender(<MemoryRouter><WorkerExecutionSection evidence={{ data: page([]) }} loading={false} /></MemoryRouter>);
        expect(screen.getByRole("region", { name: "Work activity" }).querySelector("dd")).toHaveTextContent("0");
    });
    it("marks retained observations during refresh as potentially stale", () => {
        view(page([workflow("active")]), false, true);
        expect(screen.getByRole("status")).toHaveTextContent(/displayed results may be stale/);
    });
    it.each([null, {}, { items: null }, page([null as unknown as WorkflowSummary]),
        { ...page([]), total: -1 }, { ...page([]), total: 1 },
        page([{ ...workflow("bad"), timeline: null } as unknown as WorkflowSummary]),
        page([workflow("duplicate"), workflow("duplicate")]),
    ])("fails closed on missing, malformed, or incomplete evidence: %j", (evidence) => {
        view(evidence);
        expect(screen.getByText("Could not confirm the full workflow list, so running and blocked counts are hidden.")).toBeInTheDocument();
        expect(screen.getByRole("region", { name: "Work activity" }).querySelector(":scope > dl")).toBeNull();
    });
    it.each([{ timeline: [] }, { timeline: [{ name: "Execution", status: "surprise" }] }, { timeline: [{ name: "Execution", status: "completed" }, { name: "Execution", status: "failed" }] }])("does not fabricate outcomes from invalid execution stages", ({ timeline }) => {
        view(page([{ ...workflow("unknown", "completed"), timeline }]));
        fireEvent.click(screen.getByText("More workflow details"));
        expect(screen.getByText("Mission Control could not read an execution result for one or more workflows.")).toBeInTheDocument();
    });
    it("treats future workflow states as unknown rather than idle", () => {
        view(page([workflow("future", "future_state")]));
        expect(screen.getByText("Some workflow statuses are not recognized. Running and blocked counts are hidden.")).toBeInTheDocument();
        expect(screen.getByRole("region", { name: "Work activity" }).querySelector(":scope > dl")).toBeNull();
    });
    it("starts with a short summary and exposes no mutation controls or raw payloads", () => {
        view(page(Array.from({ length: 8 }, (_, index) => workflow(`item-${index}`))));
        const section = screen.getByRole("region", { name: "Work activity" });
        expect(within(section).getAllByRole("link")).toHaveLength(4);
        expect(within(section).getByRole("button", { name: "Show all 8 running workflows" })).toBeVisible();
        expect(section.querySelectorAll("button")).toHaveLength(1);
        expect(section.querySelectorAll("form,input,select,textarea")).toHaveLength(0);
        expect(section).toHaveTextContent("This read-only summary shows workflow progress and results.");
    });
    it("rejects malformed JSON fields before the shared dashboard consumes them", () => {
        expect(isWorkflowEvidencePage({ ...page([]), total: Infinity })).toBe(false);
        expect(isWorkflowEvidencePage(page([{ ...workflow("bad"), last_result_summary: {} } as unknown as WorkflowSummary]))).toBe(false);
    });
});

it("retains failed-refresh observations explicitly as stale, without asserting health", () => {
    render(<MemoryRouter><WorkerExecutionSection evidence={{ data: page([workflow("old")]), unavailable: true, stale: true }} /></MemoryRouter>);
    expect(screen.getByRole("link", { name: "Workflow · Running" })).toBeInTheDocument();
    expect(screen.getByText("Showing last-known workflow information. Current status is unknown.")).toBeInTheDocument();
    expect(screen.queryByText("Healthy")).not.toBeInTheDocument();
});

it.each(["..", "\ud800", " "])("rejects unsafe workflow navigation: %j", id => {
    view(page([workflow(id)]));
    expect(screen.getByText("Could not confirm the full workflow list, so running and blocked counts are hidden.")).toBeInTheDocument();
});

it("redacts sensitive display text and discloses partially missing outcomes", () => {
    view(page([workflow("token=private-value", "completed", "completed"), { ...workflow("missing"), timeline: [] }]));
    expect(screen.queryByText(/private-value/)).not.toBeInTheDocument();
    fireEvent.click(screen.getByText("More workflow details"));
    const redactedId = screen.getByText("Workflow ID: [Sensitive text withheld]");
    expect(redactedId).not.toBeVisible();
    fireEvent.click(within(redactedId.closest("li")!).getByText("Technical details"));
    expect(redactedId).toBeVisible();
    expect(screen.getByText(/Some execution results are missing or incomplete/)).toBeInTheDocument();
});
