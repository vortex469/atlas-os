import { fireEvent, render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";
import type { WorkflowListResponse, WorkflowSummary } from "../../types/atlasAgent";
import { WorkerExecutionSection } from "./WorkerExecutionSection";
import { isWorkflowEvidencePage } from "./workerExecutionEvidence";

function workflow(id: string, state = "executing", stage = "current"): WorkflowSummary {
    return { workflow_id: id, workflow_state: state, workflow_source: "candidate",
        effect_kind: "repository_change", execution_intent: null, candidate_id: null,
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
    it("shows an idle observation without inventing worker health or queue depth", () => {
        view(page([]));
        const section = screen.getByRole("region", { name: "Work activity" });
        expect(within(section).getByText("Running workflows").nextElementSibling).toHaveTextContent("0");
        expect(within(section).getByText("Blocked workflows").nextElementSibling).toHaveTextContent("0");
        expect(within(section).getByText("No running workflows are listed. Worker availability is unknown.")).toBeInTheDocument();
        expect(within(section).getByText("Worker availability is not reported.")).toBeInTheDocument();
        expect(within(section).getByText("Queue size").closest("details")?.open).toBe(false);
        fireEvent.click(within(section).getByText("More about execution data"));
        expect(within(section).getByText("Queue size")).toBeInTheDocument();
        expect(within(section).getByText("Not reported")).toBeInTheDocument();
    });
    it("distinguishes executing from verification and links to encoded detail routes", () => {
        view(page([workflow("a/b?#"), workflow("verify", "verifying", "completed")]));
        const section = screen.getByRole("region", { name: "Work activity" });
        expect(within(section).getAllByText("Running workflows")[0].nextElementSibling).toHaveTextContent("1");
        expect(screen.getByRole("link", { name: "a/b?#" })).toHaveAttribute("href", "/workflows/a%2Fb%3F%23");
        expect(screen.getByRole("link", { name: "Review workflows →" })).toHaveAttribute("href", "/workflows");
    });
    it("shows blocked workflows without claiming that execution started", () => {
        view(page([workflow("blocked", "blocked", "waiting")]));
        const section = screen.getByRole("region", { name: "Work activity" });
        expect(within(section).getAllByText("Blocked workflows")[0].nextElementSibling).toHaveTextContent("1");
        fireEvent.click(within(section).getByText("More about execution data"));
        expect(within(section).getByText(/A workflow may be blocked before it starts running/)).toBeInTheDocument();
        expect(screen.getByText("No execution outcomes recorded")).toBeInTheDocument();
    });
    it("uses execution evidence, not the latest commit result, and discloses absent recency", () => {
        view(page([workflow("success", "completed", "completed"), workflow("failure", "blocked", "failed")]));
        fireEvent.click(screen.getByText("More about execution data"));
        expect(screen.getByText("Execution completed")).toBeInTheDocument();
        expect(screen.getByText("Execution failed")).toBeInTheDocument();
        expect(screen.queryByText("Commit completed")).not.toBeInTheDocument();
        expect(screen.getByText(/Execution times are not available/)).toBeInTheDocument();
    });
    it("hides old observations on refresh failure and recovers on a new response", () => {
        const { rerender } = view(page([workflow("old")]), true);
        expect(screen.queryByRole("link", { name: "old" })).not.toBeInTheDocument();
        expect(screen.getByText("Workflow status could not be loaded.")).toBeInTheDocument();
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
        expect(screen.getByText("Workflow status is unknown or incomplete.")).toBeInTheDocument();
        expect(screen.getByRole("region", { name: "Work activity" }).querySelector("dd")).not.toHaveTextContent("0");
    });
    it.each([{ timeline: [] }, { timeline: [{ name: "Execution", status: "surprise" }] }, { timeline: [{ name: "Execution", status: "completed" }, { name: "Execution", status: "failed" }] }])("does not fabricate outcomes from invalid execution stages", ({ timeline }) => {
        view(page([{ ...workflow("unknown", "completed"), timeline }]));
        fireEvent.click(screen.getByText("More about execution data"));
        expect(screen.getByText(/Unknown — execution evidence missing or malformed/)).toBeInTheDocument();
    });
    it("treats future workflow states as unknown rather than idle", () => {
        view(page([workflow("future", "future_state")]));
        expect(screen.getByText(/Some workflow states are not recognized/)).toBeInTheDocument();
        expect(screen.getByRole("region", { name: "Work activity" }).querySelector("dd")).toHaveTextContent("Unknown");
    });
    it("caps records and exposes no mutation controls or raw payloads", () => {
        view(page(Array.from({ length: 8 }, (_, index) => workflow(`item-${index}`))));
        const section = screen.getByRole("region", { name: "Work activity" });
        expect(within(section).getAllByRole("link")).toHaveLength(4);
        expect(section.querySelectorAll("button,form,input,select,textarea")).toHaveLength(0);
        expect(section).toHaveTextContent("This page does not start work.");
    });
    it("rejects malformed JSON fields before the shared dashboard consumes them", () => {
        expect(isWorkflowEvidencePage({ ...page([]), total: Infinity })).toBe(false);
        expect(isWorkflowEvidencePage(page([{ ...workflow("bad"), last_result_summary: {} } as unknown as WorkflowSummary]))).toBe(false);
    });
});

it("retains failed-refresh observations explicitly as stale, without asserting health", () => {
    render(<MemoryRouter><WorkerExecutionSection evidence={{ data: page([workflow("old")]), unavailable: true, stale: true }} /></MemoryRouter>);
    expect(screen.getByRole("link", { name: "old" })).toBeInTheDocument();
    expect(screen.getByText("Showing last-known workflow information. Current status is unknown.")).toBeInTheDocument();
    expect(screen.queryByText("Healthy")).not.toBeInTheDocument();
});

it.each(["..", "\ud800", " "])("rejects unsafe workflow navigation: %j", id => {
    view(page([workflow(id)]));
    expect(screen.getByText("Workflow status is unknown or incomplete.")).toBeInTheDocument();
});

it("redacts sensitive display text and discloses partially missing outcomes", () => {
    view(page([workflow("token=private-value", "completed", "completed"), { ...workflow("missing"), timeline: [] }]));
    expect(screen.queryByText(/private-value/)).not.toBeInTheDocument();
    expect(screen.getByText("[Sensitive text withheld]")).toBeInTheDocument();
    expect(screen.getByText(/Some execution results are missing or incomplete/)).toBeInTheDocument();
});
