import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";
import { Overview } from "./MissionControl";
import type { OverviewEvidence } from "./useOverviewEvidence";

const provider = (id: string, status: unknown) => ({ id, name: id, health: { status } });
function show(evidence: OverviewEvidence) {
    return render(<MemoryRouter><Overview evidence={evidence} /></MemoryRouter>);
}
const registry = () => within(screen.getByRole("region", { name: "Providers" }));

describe("integrated agent/provider evidence", () => {
    it("keeps identity separate from health and supplies existing read-only navigation", async () => {
        const user = userEvent.setup();
        show({ agent: { data: { app_name: "Development Agent", token: "private-canary" } }, providers: { data: [provider("alpha", "healthy"), provider("beta", "failed"), provider("gamma", "offline"), provider("delta", "degraded"), provider("epsilon", "configured")] } });
        const agent = within(screen.getByRole("region", { name: "Agent state" }));
        expect(agent.getByText("Development Agent")).toBeInTheDocument();
        expect(agent.getByText("Agent details do not include health or workflow status.")).toBeInTheDocument();
        expect(agent.queryByText("Unknown", { exact: true })).not.toBeInTheDocument();
        expect(agent.queryByText("Check time unavailable.")).not.toBeInTheDocument();
        expect(agent.queryByText("Evidence unknown.")).not.toBeInTheDocument();
        expect(agent.queryByText("Evidence unavailable.")).not.toBeInTheDocument();
        expect(agent.getByRole("link", { name: "View agent workflows" })).toHaveAttribute("href", "/workflows");
        expect(registry().getByText("Saved providers and their reported status. A saved provider may still be unavailable.")).toBeInTheDocument();
        expect(registry().getByText("Healthy")).toBeInTheDocument();
        expect(registry().getByText("Reported status: failed")).toBeInTheDocument();
        expect(registry().getByText("Unavailable")).toBeInTheDocument();
        expect(registry().queryByText("Reported status: offline")).not.toBeInTheDocument();
        expect(registry().queryByText("Check time unavailable.")).not.toBeInTheDocument();
        expect(registry().getByText("Unknown")).toBeInTheDocument();
        expect(registry().getByRole("link", { name: "View alpha →", hidden: true })).toHaveAttribute("href", "/providers/alpha");
        expect(registry().getByText(/permission to run actions/)).not.toBeVisible();
        await user.click(registry().getByText("Technical details"));
        expect(registry().getByText(/permission to run actions/)).toBeVisible();
        expect(screen.queryByText(/private-canary/)).not.toBeInTheDocument();
        expect(screen.getByTestId("overview-grid").children).toHaveLength(6);
    });
    it("explains unavailable Agent details without inventing a health state", () => {
        show({ agent: { unavailable: true } });
        const agent = within(screen.getByRole("region", { name: "Agent state" }));
        expect(agent.getByText("Agent details are unavailable. Workflow availability is unknown.")).toBeInTheDocument();
        expect(agent.queryByText("Unknown", { exact: true })).not.toBeInTheDocument();
        expect(agent.queryByText("Check time unavailable.")).not.toBeInTheDocument();
        expect(agent.queryByText("Evidence unavailable.")).not.toBeInTheDocument();
    });
    it("labels retained Agent identity as last-known", () => {
        show({ agent: { data: { app_name: "Development Agent" }, unavailable: true, stale: true } });
        const agent = within(screen.getByRole("region", { name: "Agent state" }));
        expect(agent.getByText("Development Agent")).toBeInTheDocument();
        expect(agent.getByText("Last-known Agent details. Current workflow availability is unknown.")).toBeInTheDocument();
        expect(agent.queryByText("Unknown", { exact: true })).not.toBeInTheDocument();
    });
    it("retains stale observations without presenting cached success as current", () => {
        const view = show({ providers: { data: [provider("alpha", "healthy")], stale: true, unavailable: true }, agent: { unavailable: true } });
        expect(registry().queryByText("Healthy", { exact: true })).not.toBeInTheDocument();
        expect(registry().getByText(/Last known status: Healthy/)).toBeInTheDocument();
        view.rerender(<MemoryRouter><Overview evidence={{ providers: { data: [], stale: true, unavailable: true } }} /></MemoryRouter>);
        expect(registry().queryByText("No providers configured.")).not.toBeInTheDocument();
        expect(registry().getByText(/current list is unknown/)).toBeInTheDocument();
    });
    it.each([undefined, null, {}, { providers: [] }])("does not present malformed or missing registries as empty: %s", data => {
        show({ providers: { data } });
        expect(registry().getByText("Provider configuration unknown.")).toBeInTheDocument();
        expect(registry().queryByText("No providers configured.")).not.toBeInTheDocument();
    });
    it("rejects malformed and duplicate identities and unsafe links even in expanded rows", () => {
        show({ providers: { data: [null, {}, provider("duplicate", "healthy"), provider("duplicate", "healthy"), ...["..", "../escape", "https://host", "a/b", "%2e%2e", "\ud800", "token-private"].map(id => provider(id, "healthy")), { ...provider("bad-name", "healthy"), name: { secret: "private-canary" } }, provider("valid", {})] } });
        expect(registry().queryByText("Healthy")).not.toBeInTheDocument();
        expect(registry().getAllByRole("link", { hidden: true })).toHaveLength(2);
        expect(registry().getByRole("link", { name: "View valid →", hidden: true })).toHaveAttribute("href", "/providers/valid");
    });
    it("withholds sensitive configuration, diagnostics, and identity labels", () => {
        const view = show({ providers: { data: [{ ...provider("safe", "healthy"), config: { key: "private-canary" }, model: "private-canary", health: { status: "healthy", message: "Bearer private-canary", details: { password: "private-canary" } } }] }, agent: { data: { app_name: "Bearer private-canary", version: {} } } });
        expect(view.container.innerHTML).not.toContain("private-canary");
    });
});
