import { render, screen, within } from "@testing-library/react";
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
        expect(registry().getByText("Healthy")).toBeInTheDocument();
        expect(registry().getByText("Source status: failed")).toBeInTheDocument();
        expect(registry().getByText("Unavailable")).toBeInTheDocument();
        expect(registry().getByText("Unknown")).toBeInTheDocument();
        expect(registry().getByRole("link", { name: "Inspect alpha →", hidden: true })).toHaveAttribute("href", "/providers/alpha");
        expect(screen.queryByText(/private-canary/)).not.toBeInTheDocument();
        expect(screen.getByTestId("overview-grid").children).toHaveLength(6);
    });
    it("retains stale observations without presenting cached success as current", () => {
        const view = show({ providers: { data: [provider("alpha", "healthy")], stale: true, unavailable: true }, agent: { unavailable: true } });
        expect(registry().queryByText("Healthy", { exact: true })).not.toBeInTheDocument();
        expect(registry().getByText(/Last-known status: Healthy/)).toBeInTheDocument();
        view.rerender(<MemoryRouter><Overview evidence={{ providers: { data: [], stale: true, unavailable: true } }} /></MemoryRouter>);
        expect(registry().queryByText("No providers configured.")).not.toBeInTheDocument();
        expect(registry().getByText(/current configuration unknown/)).toBeInTheDocument();
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
        expect(registry().getByRole("link", { name: "Inspect valid →", hidden: true })).toHaveAttribute("href", "/providers/valid");
    });
    it("withholds sensitive configuration, diagnostics, and identity labels", () => {
        const view = show({ providers: { data: [{ ...provider("safe", "healthy"), config: { key: "private-canary" }, model: "private-canary", health: { status: "healthy", message: "Bearer private-canary", details: { password: "private-canary" } } }] }, agent: { data: { app_name: "Bearer private-canary", version: {} } } });
        expect(view.container.innerHTML).not.toContain("private-canary");
    });
});
