import { fireEvent, render, screen, within } from "@testing-library/react";
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
    it("keeps identity separate from health and supplies existing read-only navigation", () => {
        show({ agent: { data: { app_name: "Development Agent", token: "private-canary" } }, providers: { data: [provider("alpha", "healthy"), provider("beta", "failed"), provider("gamma", "offline"), provider("delta", "degraded"), provider("epsilon", "configured")] } });
        const agent = within(screen.getByRole("region", { name: "Agent state" }));
        expect(agent.getByText("Unknown")).toBeInTheDocument();
        expect(agent.getByRole("link", { name: "View agent workflows" })).toHaveAttribute("href", "/workflows");
        expect(agent.getByRole("link", { name: "Open Forge →" })).toBeVisible();
        expect(agent.getByText("Development Agent")).not.toBeVisible();
        expect(agent.getByText(/name and version do not show whether it can run workflows/)).not.toBeVisible();
        fireEvent.click(agent.getByText("Agent details"));
        expect(agent.getByText("Development Agent")).toBeVisible();
        expect(agent.getByText(/The name and version do not show whether it can run workflows/)).toBeVisible();
        expect(agent.getByText("Unknown")).toBeVisible();
        fireEvent.click(agent.getByText("Agent details"));
        expect(agent.getByText("Development Agent")).not.toBeVisible();
        expect(registry().getByText("5 providers reported.")).toBeVisible();
        const providerDetails = registry().getByText("Show provider status (5)", { exact: true });
        expect(providerDetails.closest("details")).not.toHaveAttribute("open");
        expect(registry().getByText("Healthy")).not.toBeVisible();
        expect(registry().getByRole("link", { name: "Inspect alpha →", hidden: true })).toHaveAttribute("href", "/providers/alpha");
        expect(registry().getByText("Source status: failed")).not.toBeVisible();
        expect(screen.queryByText(/private-canary/)).not.toBeInTheDocument();
        expect(screen.getByTestId("overview-grid").children).toHaveLength(6);
    });
    it("retains stale observations without presenting cached success as current", () => {
        const view = show({ providers: { data: [provider("alpha", "healthy")], stale: true, unavailable: true }, agent: { unavailable: true } });
        expect(registry().queryByText("Healthy", { exact: true })).not.toBeInTheDocument();
        expect(registry().getByText(/Showing last reported details for 1 provider/)).toBeVisible();
        expect(registry().getByText(/Last-known status: Healthy/)).not.toBeVisible();
        view.rerender(<MemoryRouter><Overview evidence={{ providers: { data: [], stale: true, unavailable: true } }} /></MemoryRouter>);
        expect(registry().queryByText("No providers configured.")).not.toBeInTheDocument();
        expect(registry().getByText(/Current configuration is unknown/)).toBeInTheDocument();
    });
    it("shows a reported Agent version when its name is unavailable", () => {
        show({ agent: { data: { version: "0.4.2" } } });
        const agent = within(screen.getByRole("region", { name: "Agent state" }));
        fireEvent.click(agent.getByText("Agent details"));
        expect(agent.getByText("0.4.2", { exact: true })).toBeVisible();
        expect(agent.getByText(/Agent name or version reported by Atlas Agent/)).toBeVisible();
    });
    it.each([undefined, null, {}, { providers: [] }])("does not present malformed or missing registries as empty: %s", data => {
        show({ providers: { data } });
        expect(registry().getByText("Provider configuration is not available.")).toBeInTheDocument();
        expect(registry().queryByText("No providers configured.")).not.toBeInTheDocument();
    });
    it("rejects malformed and duplicate identities and unsafe links even in expanded rows", () => {
        show({ providers: { data: [null, {}, provider("duplicate", "healthy"), provider("duplicate", "healthy"), ...["..", "../escape", "https://host", "a/b", "%2e%2e", "\ud800", "token-private"].map(id => provider(id, "healthy")), { ...provider("bad-name", "healthy"), name: { secret: "private-canary" } }, provider("valid", {})] } });
        expect(registry().queryByText("Healthy")).not.toBeInTheDocument();
        expect(registry().getAllByRole("link", { hidden: true })).toHaveLength(2);
        expect(registry().getByRole("link", { name: "Inspect valid →", hidden: true })).toHaveAttribute("href", "/providers/valid");
    });
    it("withholds sensitive configuration, diagnostics, and identity labels", () => {
        const view = show({ providers: { data: [{ ...provider("safe", "healthy"), config: { key: "private-canary" }, model: "private-canary", health: { status: "healthy", message: "Bearer private-canary", details: { password: "private-canary" } } }] }, agent: { data: { app_name: "Bearer private-canary", version: {} } } });
        expect(view.container.innerHTML).not.toContain("private-canary");
    });
});
