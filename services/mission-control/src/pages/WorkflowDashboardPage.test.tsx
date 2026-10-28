import { StrictMode } from "react";
import { act, fireEvent, render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { listWorkflows } from "../api/atlas-agent";
import type { WorkflowListResponse, WorkflowSummary } from "../types/atlasAgent";
import { WorkflowDashboardPage } from "./WorkflowDashboardPage";

vi.mock("../api/atlas-agent", async () => ({
    ...await vi.importActual<typeof import("../api/atlas-agent")>("../api/atlas-agent"),
    listWorkflows: vi.fn(),
}));
const list = vi.mocked(listWorkflows);

function workflow(overrides: Partial<WorkflowSummary> = {}): WorkflowSummary {
    return {
        workflow_id: "workflow-123", workflow_source: "candidate", workflow_state: "awaiting_implementation_approval",
        effect_kind: "repository_change", execution_intent: "update-compose-stack", candidate_id: "candidate-123",
        planning_session_id: "planning-123", repository: "/repo", target_id: "compose-stack-1",
        last_result_summary: "No result yet", timeline: [{ name: "Implementation Approval", status: "current" }],
        ...overrides,
    };
}
function response(items: WorkflowSummary[], overrides: Partial<WorkflowListResponse> = {}): WorkflowListResponse {
    const state_counts: Record<string, number> = {};
    for (const item of items) state_counts[item.workflow_state] = (state_counts[item.workflow_state] ?? 0) + 1;
    return { items, state_counts, total: items.length, limit: 10, offset: 0, ...overrides };
}
function renderDashboard() {
    return render(<MemoryRouter><WorkflowDashboardPage /></MemoryRouter>);
}
function search(id: string) {
    fireEvent.change(screen.getByLabelText("Workflow ID search"), { target: { value: id } });
    fireEvent.click(screen.getByRole("button", { name: "Apply filters" }));
}

describe("WorkflowDashboardPage", () => {
    beforeEach(() => { vi.useRealTimers(); list.mockReset(); });

    it("loads summaries, full matching counts, rails and detail links without mutation controls", async () => {
        list.mockResolvedValue(response([workflow()], { total: 215, state_counts: { awaiting_implementation_approval: 1, completed: 214 }, items: [workflow(), ...Array.from({ length: 9 }, (_, i) => workflow({ workflow_id: `completed-${i}`, workflow_state: "completed" }))] }));
        renderDashboard();
        await screen.findByText("workflow-123");
        expect(screen.getAllByRole("heading", { name: "Update Compose Stack" })).toHaveLength(10);
        expect(screen.getByText("workflow-123", { exact: true })).toBeVisible();
        const workflowCard = screen.getByText("workflow-123", { exact: true }).closest("article")!;
        expect(within(workflowCard).getByText(/Workflow ID:/)).toBeVisible();
        expect(list).toHaveBeenCalledWith(expect.objectContaining({ limit: 10, offset: 0 }));
        expect(screen.getByText("Showing 10 of 215 matching workflows")).toBeVisible();
        expect(screen.getByRole("heading", { name: "Totals for this search" })).toBeVisible();
        const completed = screen.getByText("Completed", { selector: "p" }).closest("article")!;
        expect(within(completed).getByText("214")).toBeVisible();
        expect(screen.getAllByRole("link", { name: "Open Workflow" })[0]).toHaveAttribute("href", "/workflows/workflow-123");
        const main = screen.getByRole("main");
        expect(within(main).queryByRole("button", { name: /Approve|Reject|Execute|Resume|Commit/i })).not.toBeInTheDocument();
        expect(screen.getAllByText("Workflow progress").length).toBe(10);
    });

    it("sends all submitted filters to the server and resets the offset", async () => {
        list.mockResolvedValue(response([workflow()]));
        renderDashboard(); await screen.findByText("workflow-123");
        const applied = screen.getByRole("region", {name: "Applied workflow filters"});
        expect(applied).toHaveTextContent("All workflows");
        expect(screen.getByLabelText("Source")).not.toBeVisible();
        expect(screen.getByLabelText("Candidate ID")).not.toBeVisible();
        fireEvent.click(screen.getByText("More filters"));
        expect(screen.getByLabelText("Source")).toBeVisible();
        expect(screen.getByLabelText("Candidate ID")).toBeVisible();
        fireEvent.change(screen.getByLabelText("State"), { target: { value: "awaiting_implementation_approval" } });
        fireEvent.change(screen.getByLabelText("Source"), { target: { value: "candidate" } });
        fireEvent.change(screen.getByLabelText("Candidate ID"), { target: { value: " candidate-123 " } });
        fireEvent.change(screen.getByLabelText("Waiting for approval"), { target: { value: "yes" } });
        expect(applied).toHaveTextContent("All workflows");
        expect(screen.getByText("Changes are not applied yet. Choose Apply filters to update results.")).toBeVisible();
        expect(list).toHaveBeenCalledTimes(1);
        search(" workflow-123 ");
        await screen.findByText("workflow-123");
        expect(applied).toHaveTextContent("Source: Candidate");
        expect(applied).toHaveTextContent("Candidate ID: candidate-123");
        expect(applied).toHaveTextContent("Workflow ID: workflow-123");
        expect(screen.queryByText("Changes are not applied yet. Choose Apply filters to update results.")).not.toBeInTheDocument();
        fireEvent.change(screen.getByLabelText("Workflow ID search"), {target: {value: "different"}});
        expect(screen.getByText("Changes are not applied yet. Choose Apply filters to update results.")).toBeVisible();
        fireEvent.change(screen.getByLabelText("Workflow ID search"), {target: {value: " workflow-123 "}});
        expect(screen.queryByText("Changes are not applied yet. Choose Apply filters to update results.")).not.toBeInTheDocument();
        expect(list).toHaveBeenCalledTimes(2);
        expect(list).toHaveBeenLastCalledWith({ state: "awaiting_implementation_approval", source: "candidate", candidate_id: "candidate-123", workflow_id: "workflow-123", waiting_for_approval: true, limit: 10, offset: 0 });
    });

    it("can page and search beyond the first 200 records", async () => {
        const all = Array.from({ length: 215 }, (_, i) => workflow({ workflow_id: `workflow-${String(i).padStart(3, "0")}`, workflow_state: "completed" }));
        list.mockImplementation(async (query = {}) => {
            const matching = all.filter((item) => !query.workflow_id || item.workflow_id.includes(query.workflow_id));
            const offset = query.offset ?? 0;
            return response(matching.slice(offset, offset + 10), { total: matching.length, offset, state_counts: { completed: matching.length } });
        });
        renderDashboard(); await screen.findByText("workflow-000");
        fireEvent.click(screen.getByRole("button", { name: "Next" }));
        await screen.findByText("workflow-010");
        expect(list).toHaveBeenLastCalledWith(expect.objectContaining({ limit: 10, offset: 10 }));
        search("workflow-214");
        expect(await screen.findByText("workflow-214")).toBeVisible();
        expect(screen.getByText("Showing 1 of 1 matching workflows")).toBeVisible();
        expect(screen.queryByText("workflow-000")).not.toBeInTheDocument();
    });

    it("blocks overlapping refreshes of the same query", async () => {
        list.mockResolvedValueOnce(response([workflow()]));
        let resolve!: (value: WorkflowListResponse) => void;
        list.mockImplementationOnce(() => new Promise((done) => { resolve = done; }));
        renderDashboard(); await screen.findByText("workflow-123");
        fireEvent.click(screen.getByRole("button", { name: "Refresh" }));
        fireEvent.click(screen.getByRole("button", { name: "Refresh" }));
        expect(list).toHaveBeenCalledTimes(2);
        await act(async () => resolve(response([workflow({ workflow_id: "refreshed" })])));
        expect(screen.getByText("refreshed")).toBeVisible();
    });

    it.each(["success", "failure"])("lets a new search supersede an older refresh and ignores its late %s", async (outcome) => {
        list.mockResolvedValueOnce(response([workflow()]));
        let resolveOld!: (value: WorkflowListResponse) => void;
        let rejectOld!: (reason: Error) => void;
        list.mockImplementationOnce(() => new Promise((done, reject) => { resolveOld = done; rejectOld = reject; }))
            .mockResolvedValueOnce(response([workflow({ workflow_id: "new-query" })]));
        renderDashboard(); await screen.findByText("workflow-123");
        fireEvent.click(screen.getByRole("button", { name: "Refresh" }));
        search("new-query");
        await screen.findByText("new-query");
        await act(async () => {
            if (outcome === "failure") rejectOld(new Error("Old refresh failed"));
            else resolveOld(response([workflow({ workflow_id: "old-refresh" })]));
        });
        expect(screen.queryByRole("alert")).not.toBeInTheDocument();
        expect(screen.queryByText("old-refresh")).not.toBeInTheDocument();
        expect(screen.getByText("new-query")).toBeVisible();
    });

    it.each(["success", "failure"])("keeps search available and ignores a superseded slow query's %s", async (outcome) => {
        list.mockResolvedValueOnce(response([workflow()]));
        let resolveOld!: (value: WorkflowListResponse) => void;
        let rejectOld!: (error: Error) => void;
        list.mockImplementationOnce(() => new Promise((resolve, reject) => { resolveOld = resolve; rejectOld = reject; }))
            .mockResolvedValueOnce(response([workflow({ workflow_id: "latest-query" })]));
        renderDashboard(); await screen.findByText("workflow-123");
        search("slow-query");
        expect(screen.getByLabelText("Workflow ID search")).toBeVisible();
        expect(screen.queryByText("workflow-123")).not.toBeInTheDocument();
        expect(screen.queryByText("Showing 1 of 1 matching workflows")).not.toBeInTheDocument();
        search("latest-query");
        expect(await screen.findByText("latest-query")).toBeVisible();
        await act(async () => {
            if (outcome === "success") resolveOld(response([workflow({ workflow_id: "slow-query" })]));
            else rejectOld(new Error("Superseded query failed"));
        });
        expect(screen.queryByText("slow-query", { selector: "h3" })).not.toBeInTheDocument();
        expect(screen.queryByRole("alert")).not.toBeInTheDocument();
        expect(screen.getByText("latest-query")).toBeVisible();
    });

    it("retries an initial outage without reloading", async () => {
        list.mockRejectedValueOnce(new Error("Atlas Agent unavailable")).mockResolvedValueOnce(response([workflow()]));
        renderDashboard(); await screen.findByRole("alert");
        fireEvent.click(screen.getByRole("button", { name: "Try again" }));
        expect(await screen.findByText("workflow-123")).toBeVisible();
        expect(list).toHaveBeenCalledTimes(2);
    });

    it("distinguishes an empty directory from no server-side filter matches", async () => {
        list.mockResolvedValue(response([])); renderDashboard();
        expect(await screen.findByText("No workflows yet.")).toBeVisible();
        expect(screen.getByRole("link", {name: "Review change proposals"})).toHaveAttribute("href", "/execution-candidates");
        expect(screen.getByRole("link", {name: "Choose maintenance"})).toHaveAttribute("href", "/operations/request");
        expect(list).toHaveBeenCalledTimes(1);
        search("missing");
        expect(await screen.findByText("No workflows match the current filters.")).toBeVisible();
        expect(screen.getByText("Try a broader search or clear the filters above.")).toBeVisible();
        expect(screen.queryByRole("link", {name: "Review change proposals"})).not.toBeInTheDocument();
        expect(screen.queryByRole("link", {name: "Choose maintenance"})).not.toBeInTheDocument();
        expect(list).toHaveBeenCalledTimes(2);
    });

    it("does not invent global counts for an older Agent", async () => {
        list.mockResolvedValue(response([workflow()], { state_counts: undefined }));
        renderDashboard(); await screen.findByText("workflow-123");
        const totals = screen.getByRole("region", { name: "Workflow totals" });
        expect(within(totals).queryByText("Unavailable", { exact: true })).not.toBeInTheDocument();
        expect(within(totals).getByRole("status")).toHaveTextContent("This version of Atlas Agent does not report workflow totals.");
        expect(within(totals).getByRole("status")).toHaveTextContent("You can still search and browse workflows");
        expect(screen.getByRole("heading", { name: "Update Compose Stack" })).toBeVisible();
    });

    it("refuses unsupported approval filtering and offers a working clear action", async () => {
        list.mockResolvedValue(response([workflow()], { state_counts: undefined }));
        renderDashboard(); await screen.findByText("workflow-123");
        fireEvent.change(screen.getByLabelText("Waiting for approval"), { target: { value: "yes" } });
        fireEvent.click(screen.getByRole("button", { name: "Apply filters" }));
        expect(await screen.findByRole("alert")).toHaveTextContent("requires an updated Atlas Agent");
        fireEvent.click(screen.getByRole("button", { name: "Clear filters" }));
        expect(await screen.findByText("workflow-123")).toBeVisible();
        expect(list.mock.lastCall![0]?.waiting_for_approval).toBeUndefined();
    });

    it("corrects a page emptied by deletion with one bounded read", async () => {
        const first = Array.from({ length: 10 }, (_, i) => workflow({ workflow_id: `workflow-${i}`, workflow_state: "completed" }));
        list.mockResolvedValueOnce(response(first, { total: 11, state_counts: { completed: 11 } }))
            .mockResolvedValueOnce(response([], { total: 1, offset: 10, state_counts: { completed: 1 } }))
            .mockResolvedValueOnce(response([workflow({ workflow_id: "last-survivor", workflow_state: "completed" })]));
        renderDashboard(); await screen.findByText("workflow-0");
        fireEvent.click(screen.getByRole("button", { name: "Next" }));
        expect(await screen.findByText("last-survivor")).toBeVisible();
        expect(list).toHaveBeenCalledTimes(3);
        expect(list.mock.calls.slice(1).map(([query]) => query?.offset)).toEqual([10, 0]);
    });

    it("bounds recovery when records keep disappearing between reads", async () => {
        const items = Array.from({ length: 10 }, (_, i) => workflow({ workflow_id: `workflow-${i}`, workflow_state: "completed" }));
        list.mockResolvedValueOnce(response(items, { total: 30, state_counts: { completed: 30 } }))
            .mockResolvedValueOnce(response(items, { total: 30, offset: 10, state_counts: { completed: 30 } }))
            .mockResolvedValueOnce(response([], { total: 15, offset: 20, state_counts: { completed: 15 } }))
            .mockResolvedValueOnce(response([], { total: 5, offset: 10, state_counts: { completed: 5 } }));
        renderDashboard(); await screen.findByText("workflow-0");
        fireEvent.click(screen.getByRole("button", { name: "Next" }));
        await screen.findByText("Page 2 of 3");
        fireEvent.click(screen.getByRole("button", { name: "Next" }));
        expect(await screen.findByRole("alert")).toHaveTextContent("workflow list changed while loading");
        expect(list.mock.calls.map(([query]) => query?.offset)).toEqual([0, 10, 20, 10]);
    });

    it.each([
        response([workflow()], { state_counts: { completed: 1 } }),
        response([workflow()], { total: 2 }),
        response([workflow()], { offset: 10 }),
        response([workflow()], { state_counts: { awaiting_implementation_approval: -1 } }),
    ])("refuses inconsistent pagination or aggregate data", async (invalid) => {
        list.mockResolvedValue(invalid); renderDashboard();
        expect(await screen.findByRole("alert")).toHaveTextContent(/inconsistent workflow/);
        expect(screen.queryByText("workflow-123")).not.toBeInTheDocument();
    });

    it("refreshes when an active workflow is off-page and stops after unmount", async () => {
        vi.useFakeTimers();
        const items = Array.from({ length: 10 }, (_, i) => workflow({ workflow_id: `completed-${i}`, workflow_state: "completed" }));
        list.mockResolvedValue(response(items, { total: 11, state_counts: { completed: 10, executing: 1 } }));
        const view = renderDashboard();
        await act(async () => { await vi.advanceTimersByTimeAsync(0); });
        expect(list).toHaveBeenCalledTimes(1);
        await act(async () => { await vi.advanceTimersByTimeAsync(5_000); });
        expect(list).toHaveBeenCalledTimes(2);
        view.unmount();
        await act(async () => { await vi.advanceTimersByTimeAsync(10_000); });
        expect(list).toHaveBeenCalledTimes(2);
        vi.useRealTimers();
    });

    it("loads once under Strict Mode replay", async () => {
        list.mockResolvedValue(response([]));
        render(<StrictMode><MemoryRouter><WorkflowDashboardPage /></MemoryRouter></StrictMode>);
        await screen.findByText("No workflows yet.");
        expect(list).toHaveBeenCalledTimes(1);
    });
    it.each(["awaiting_implementation_approval", "completed", "blocked"])("keeps %s directory results visible with supporting facts expandable", async workflow_state => {
        list.mockResolvedValue(response([workflow({workflow_state})]));
        renderDashboard();
        const heading = await screen.findByRole("heading", {name: "Update Compose Stack"});
        const card = within(heading.closest("article")!);
        expect(card.getByText("/repo")).toBeVisible();
        expect(card.getByText("No result yet")).toBeVisible();
        expect(card.getByText(workflow_state === "awaiting_implementation_approval" ? "Waiting for approval" : "Not waiting for approval")).toBeVisible();
        expect(card.getByRole("link", {name: "Open Workflow"})).toHaveAttribute("href", "/workflows/workflow-123");
        expect(card.getByText("candidate-123")).not.toBeVisible();
        expect(card.getByText("planning-123")).not.toBeVisible();
        const details = card.getByText("Workflow details");
        expect(details.closest("details")).not.toHaveAttribute("open");
        const progress = card.getByText("Workflow progress").closest("details");
        if (workflow_state === "blocked") expect(progress).toHaveAttribute("open");
        else expect(progress).not.toHaveAttribute("open");
        fireEvent.click(details);
        expect(card.getByText("candidate-123")).toBeVisible();
        expect(card.getByText("planning-123")).toBeVisible();
        expect(list).toHaveBeenCalledTimes(1);
    });

    it("keeps retained states and totals qualified through failed refresh and recovery", async () => {
        let rejectRefresh!: (reason: Error) => void;
        list.mockResolvedValueOnce(response([workflow()]))
            .mockImplementationOnce(() => new Promise((_, reject) => {rejectRefresh = reject;}))
            .mockResolvedValueOnce(response([workflow({workflow_state: "completed", last_result_summary: "Latest result"})]));
        renderDashboard(); await screen.findByText("workflow-123");
        fireEvent.click(screen.getByRole("button", {name: "Refresh"}));
        expect(screen.getByRole("heading", {name: "Last loaded totals for this search"})).toBeVisible();
        expect(screen.getByText("Last loaded stage: Implementation")).toBeVisible();
        expect(screen.getByText("Last loaded approval state")).toBeVisible();
        expect(screen.getByText("Showing the last loaded results. Current workflow states and totals are unconfirmed.")).toBeVisible();
        await act(async () => rejectRefresh(new Error("Refresh unavailable")));
        expect(screen.getByRole("alert")).toHaveTextContent("Refresh unavailable");
        expect(screen.getByText("Last loaded state")).toBeVisible();
        fireEvent.click(screen.getByRole("button", {name: "Refresh"}));
        await screen.findByText("Latest result");
        expect(screen.getByRole("heading", {name: "Totals for this search"})).toBeVisible();
        expect(screen.queryByText("Last loaded state")).not.toBeInTheDocument();
        expect(screen.queryByText(/Current workflow states and totals are unconfirmed/)).not.toBeInTheDocument();
        expect(screen.queryByRole("alert")).not.toBeInTheDocument();
        expect(list).toHaveBeenCalledTimes(3);
    });

    it.each([false, true])("keeps an empty retained list historical while retrying (filtered: %s)", async filtered => {
        let finishRetry!: (value: WorkflowListResponse) => void;
        list.mockResolvedValue(response([]));
        renderDashboard(); await screen.findByText("No workflows yet.");
        if (filtered) {search("missing"); await screen.findByText("No workflows match the current filters.");}
        list.mockRejectedValueOnce(new Error("Refresh unavailable"))
            .mockImplementationOnce(() => new Promise(resolve => {finishRetry = resolve;}));
        fireEvent.click(screen.getByRole("button", {name: "Refresh"}));
        await screen.findByRole("alert");
        const message = filtered ? "The last loaded search had no matches." : "The last loaded list was empty.";
        expect(screen.getByText(message)).toBeVisible();
        expect(screen.queryByRole("link", {name: "Review change proposals"})).not.toBeInTheDocument();
        fireEvent.click(screen.getByRole("button", {name: "Refresh"}));
        expect(screen.getByText(message)).toBeVisible();
        expect(screen.getByRole("button", {name: "Refresh"})).toBeDisabled();
        await act(async () => finishRetry(response([])));
        expect(screen.getByText(filtered ? "No workflows match the current filters." : "No workflows yet.")).toBeVisible();
        expect(screen.queryByText(message)).not.toBeInTheDocument();
        if (!filtered) expect(screen.getByRole("link", {name: "Review change proposals"})).toBeVisible();
        expect(list).toHaveBeenCalledTimes(filtered ? 4 : 3);
    });

    it.each([
        {repository: {}}, {target_id: {}}, {workflow_source: {}}, {candidate_id: {}}, {planning_session_id: 42},
        {last_result_summary: {}}, {last_result_summary: null}, {timeline: {}}, {timeline: null}, {timeline: [null]},
        {timeline: [{name: {}, status: "current"}]}, {timeline: [{name: "Execution", status: {}}]},
        {workflow_id: ""}, {workflow_id: "   "}, {workflow_id: "."}, {workflow_id: ".."}, {workflow_id: "\ud800"},
    ])("recovers an unreadable workflow record %j without rendering it", async patch => {
        const invalid = {...workflow(), ...patch} as unknown as WorkflowSummary;
        list.mockResolvedValueOnce(response([invalid])).mockResolvedValueOnce(response([workflow()]));
        renderDashboard();
        expect(await screen.findByRole("heading", {name: "Workflows unavailable"})).toBeVisible();
        expect(screen.getByRole("alert")).toHaveTextContent("inconsistent workflow page");
        fireEvent.click(screen.getByRole("button", {name: "Try again"}));
        expect(await screen.findByRole("heading", {name: "Update Compose Stack"})).toBeVisible();
        expect(list).toHaveBeenCalledTimes(2);
    });

    it("retains the last valid record when refresh returns malformed display fields", async () => {
        list.mockResolvedValueOnce(response([workflow()]))
            .mockResolvedValueOnce(response([{...workflow(), repository: {private: "not-displayable"}} as unknown as WorkflowSummary]))
            .mockResolvedValueOnce(response([workflow({last_result_summary: "Recovered record"})]));
        renderDashboard(); await screen.findByText("workflow-123");
        fireEvent.click(screen.getByRole("button", {name: "Refresh"}));
        expect(await screen.findByRole("alert")).toHaveTextContent("inconsistent workflow page");
        expect(screen.getByText("Last loaded state")).toBeVisible();
        expect(screen.getByText("/repo")).toBeVisible();
        expect(screen.queryByText("not-displayable")).not.toBeInTheDocument();
        fireEvent.click(screen.getByRole("button", {name: "Refresh"}));
        expect(await screen.findByText("Recovered record")).toBeVisible();
        expect(screen.queryByRole("alert")).not.toBeInTheDocument();
        expect(list).toHaveBeenCalledTimes(3);
    });

    it("preserves nullable metadata, empty timelines, extra fields and future string states", async () => {
        const compatible = {...workflow({candidate_id: null, planning_session_id: null, repository: null, target_id: null, timeline: []}),
            workflow_source: undefined, workflow_state: "future_state", extra_metadata: "not-a-public-field"} as unknown as WorkflowSummary;
        list.mockResolvedValue(response([compatible]));
        renderDashboard();
        expect(await screen.findByRole("heading", {name: "Update Compose Stack"})).toBeVisible();
        expect(screen.getByText("Other states")).toBeVisible();
        const card = within(screen.getByRole("heading", {name: "Update Compose Stack"}).closest("article")!);
        expect(card.getByText("Unknown — open workflow to review")).toBeVisible();
        expect(card.queryByText("Not waiting for approval")).not.toBeInTheDocument();
        expect(screen.queryByRole("alert")).not.toBeInTheDocument();
        expect(screen.queryByText("not-a-public-field")).not.toBeInTheDocument();
    });

});
