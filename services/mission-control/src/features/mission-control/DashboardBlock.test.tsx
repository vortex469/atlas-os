import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it } from "vitest";
import { Overview } from "./MissionControl";
import type { OverviewEvidence } from "./useOverviewEvidence";

const event = { id: "audit/1", action_label: "Restart", provider_name: "Provider", status: "succeeded", completed_at: "2026-09-01T12:00:00Z" };
function dashboard(evidence: OverviewEvidence) {
    return <MemoryRouter><Routes><Route path="/" element={<Overview evidence={evidence} />} />
        <Route path="/operations/actions/:id" element={<p>Action detail</p>} />
        <Route path="/workflows/:id" element={<p>Workflow detail</p>} />
    </Routes></MemoryRouter>;
}
const attention = () => within(screen.getByRole("region", { name: "Operator Attention" }));
const activity = () => within(screen.getByRole("region", { name: "Recent Activity" }));

describe("integrated attention and activity", () => {
    it("shows the required approval stage, deduplicates, and navigates", async () => {
        const items = ["blocked", "awaiting_approval", "awaiting_implementation_approval", "awaiting_verification_approval", "awaiting_commit_approval", "completed", "executing", "mystery"].map(state => ({ workflow_id: state, workflow_state: state }));
        render(dashboard({ workflows: { data: { items: [...items, items[1], null] } } }));
        const conditions = within(attention().getByRole("list", { name: "Reported attention conditions" }));
        expect(conditions.getAllByRole("listitem")).toHaveLength(5);
        expect(conditions.getAllByRole("listitem")[0]).toHaveTextContent("Blocked");
        expect(attention().getAllByText(/^Action needed: Waiting for/)).toHaveLength(4);
        expect(attention().queryByRole("link", { name: "mystery" })).not.toBeInTheDocument();
        await userEvent.click(within(conditions.getAllByRole("listitem")[1]).getByRole("link", { name: "Workflow" }));
        expect(screen.getByText("Workflow detail")).toBeVisible();
    });
    it.each([" ", "", "..", "\ud800", {}])("rejects malformed workflow identity %j without requiring human action", id => {
        render(dashboard({ workflows: { data: { items: [{ workflow_id: id, workflow_state: "awaiting_approval" }] } } }));
        expect(within(attention().getByRole("list", { name: "Reported attention conditions" })).queryByRole("listitem")).not.toBeInTheDocument();
        const sourceStatus = attention().getByText("Source status").closest("details");
        expect(sourceStatus).not.toHaveAttribute("open");
        expect(sourceStatus).toHaveTextContent(/workflow results are incomplete/i);
    });
    it("keeps stale approval requirements historical and clears them on recovery", () => {
        const view = render(dashboard({ workflows: { stale: true, unavailable: true, data: { items: [{ workflow_id: "w", workflow_state: "awaiting_approval" }] } } }));
        expect(attention().getByText("Last-known status: Waiting for approval. Current status unknown.")).toBeVisible();
        expect(attention().queryByText("Human action required", { exact: true })).not.toBeInTheDocument();
        view.rerender(dashboard({ workflows: { data: { items: [], total: 0, limit: 200, offset: 0 } } }));
        expect(within(attention().getByRole("list", { name: "Reported attention conditions" })).queryByRole("listitem")).not.toBeInTheDocument();
    });
    it("never creates action requirements from absent or malformed evidence or historical failures", () => {
        render(dashboard({ summary: { data: { findings: [{ severity: { toString: null } }] } }, health: { unavailable: true }, activity: { data: { items: [{ ...event, status: "failed" }] } } }));
        expect(within(attention().getByRole("list", { name: "Reported attention conditions" })).queryByRole("listitem")).not.toBeInTheDocument();
        expect(attention().getByText("Some information is missing. Atlas cannot confirm this list includes everything that needs attention.")).toBeVisible();
        expect(activity().getByText("Failed · Restart")).toBeVisible();
    });
    it("orders and deduplicates source history with provider context and safe detail navigation", async () => {
        render(dashboard({ activity: { data: { items: [event, event, { ...event, id: "new", status: "failed", completed_at: "2026-09-02T12:00:00Z" }] } } }));
        const entries = activity().getAllByRole("listitem");
        expect(entries).toHaveLength(2);
        expect(entries[0]).toHaveTextContent("Failed · Restart");
        expect(entries[1]).toHaveTextContent("Succeeded · Restart");
        const completedAt = within(entries[1]).getByText(/^Completed /);
        expect(completedAt.tagName).toBe("TIME");
        const canonicalTime = new Date(event.completed_at).toISOString();
        expect(completedAt).toHaveAttribute("datetime", canonicalTime);
        expect(completedAt).toHaveAttribute("title", `UTC ${canonicalTime}`);
        expect(completedAt).not.toHaveTextContent("T12:00:00Z");
        expect(entries[1]).toHaveTextContent("Provider");
        expect(within(entries[1]).getByRole("link")).toHaveAttribute("href", "/operations/actions/audit%2F1");
        await userEvent.click(within(entries[1]).getByRole("link"));
        expect(screen.getByText("Action detail")).toBeVisible();
    });
    it.each([null, {}, { items: [null] }, { items: [], total: 1 }, { items: [], has_more: true }, { items: [], has_more: {} }, ...["..", ".", " ", "\ud800", {}].map(id => ({ items: [{ ...event, id }] }))])("does not turn malformed history into an empty success: %j", data => {
        render(dashboard({ activity: { data } }));
        expect(activity().queryByText("No recent actions recorded.")).not.toBeInTheDocument();
        expect(activity().queryByRole("listitem")).not.toBeInTheDocument();
    });
    it("preserves usable rows and explicit unknown outcomes/times without leaking arbitrary fields", () => {
        render(dashboard({ activity: { data: { items: [null, { ...event, status: { toString: null }, completed_at: "bad", provider_name: "token=private", message: "https://user:pass@host", details: { secret: "private-value" }, href: "javascript:alert(1)" }] } } }));
        expect(activity().getByText("Outcome unknown · Restart")).toBeVisible();
        expect(activity().getByText("Completion time unknown.")).toBeVisible();
        expect(activity().getByText("Some recent activity records could not be read.")).toBeVisible();
        expect(screen.queryByText(/private-value|token=private|user:pass/)).not.toBeInTheDocument();
        expect(activity().getByRole("link", { name: "Inspect action →" })).toHaveAttribute("href", "/operations/actions/audit%2F1");
    });
    it("shows unavailable, stale, and recovered history without accumulating a client audit log", () => {
        const view = render(dashboard({ activity: { unavailable: true } }));
        expect(activity().getByText("Recent activity could not be loaded.")).toBeVisible();
        view.rerender(dashboard({ activity: { stale: true, unavailable: true, data: { items: [event] } } }));
        expect(activity().getByText("Refresh failed. Showing the last available actions; current activity may have changed.")).toBeVisible();
        expect(activity().getAllByRole("listitem")).toHaveLength(1);
        view.rerender(dashboard({ activity: { data: { items: [] } } }));
        expect(activity().getByText("No recent actions recorded.")).toBeVisible();
        expect(activity().queryByRole("listitem")).not.toBeInTheDocument();
        expect(activity().queryByText(/Refresh failed/)).not.toBeInTheDocument();
    });
});
