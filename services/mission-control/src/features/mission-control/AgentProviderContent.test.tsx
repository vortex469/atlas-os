import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";
import { Overview } from "./MissionControl";
import type { OverviewEvidence } from "./useOverviewEvidence";

const provider = (id: string, status: unknown) => ({ id, name: id, health: { status } });
function show(evidence: OverviewEvidence, loading = false) {
    return render(<MemoryRouter><Overview evidence={evidence} loading={loading} /></MemoryRouter>);
}
const registry = () => within(screen.getByRole("region", { name: "Providers" }));

describe("integrated agent/provider evidence", () => {
    it("summarizes provider health and keeps the full status list collapsed", async () => {
        const user = userEvent.setup();
        show({ providers: { data: [
            { id: "degraded", name: "Degraded", health: { status: "degraded" } },
            { id: "healthy", name: "Healthy", health: { status: "healthy" } },
            { id: "offline", name: "Offline", health: { status: "offline" } },
            { id: "blocked", name: "Blocked", health: { status: "blocked" } },
            { id: "unknown", name: "Unknown", health: { status: "future_state" } },
        ] } });
        expect(registry().getByText("Atlas Core reports 5 providers. 3 need attention. 1 status is unknown.")).toBeVisible();
        expect(registry().getByRole("article", { name: "Blocked" })).not.toBeVisible();
        await user.click(registry().getByText("Show provider status (5)"));
        expect(registry().getAllByRole("article").map(row => row.getAttribute("aria-label"))).toEqual([
            "Blocked", "Offline", "Degraded", "Unknown", "Healthy",
        ]);
    });

    it("distinguishes first-load, unavailable, and missing states", () => {
        const view = show({}, true);
        const agent = within(screen.getByRole("region", { name: "Agent details" }));
        expect(agent.getByRole("status")).toHaveTextContent("Loading Agent details…");
        expect(registry().getByRole("status")).toHaveTextContent("Loading providers…");

        view.rerender(<MemoryRouter><Overview evidence={{ agent: { unavailable: true }, providers: { unavailable: true } }} /></MemoryRouter>);
        expect(agent.getByText("Agent details could not be loaded.")).toBeVisible();
        expect(agent.queryByRole("status")).not.toBeInTheDocument();
        expect(registry().getByText("Atlas Core’s provider list could not be loaded.")).toBeVisible();
        expect(registry().queryByRole("status")).not.toBeInTheDocument();

        view.rerender(<MemoryRouter><Overview evidence={{}} /></MemoryRouter>);
        expect(agent.getByText("Agent details are not available.")).toBeVisible();
        expect(agent.queryByText("Loading Agent details…")).not.toBeInTheDocument();
        expect(registry().getByText("Atlas Core’s provider list is not available.")).toBeVisible();
        expect(registry().queryByText("Loading providers…")).not.toBeInTheDocument();
    });

    it("keeps Agent identity separate from health and workflow navigation", async () => {
        const user = userEvent.setup();
        show({ agent: { data: { app_name: "Development Agent", token: "private-canary" } }, providers: { data: [provider("alpha", "healthy"), provider("beta", "failed"), provider("gamma", "offline"), provider("delta", "degraded"), provider("epsilon", "configured")] } });
        const agent = within(screen.getByRole("region", { name: "Agent details" }));
        expect(agent.getByText("Development Agent")).toBeInTheDocument();
        expect(agent.getByText("Agent", { exact: true }).tagName).toBe("DT");
        expect(agent.getByText("Version", { exact: true }).tagName).toBe("DT");
        expect(agent.getByText("Not reported")).toBeInTheDocument();
        expect(agent.queryByText(/workflow availability/i)).not.toBeInTheDocument();
        expect(agent.queryByText("Unknown", { exact: true })).not.toBeInTheDocument();
        expect(agent.queryByText("Check time unavailable.")).not.toBeInTheDocument();
        expect(agent.queryByText("Evidence unknown.")).not.toBeInTheDocument();
        expect(agent.queryByText("Evidence unavailable.")).not.toBeInTheDocument();
        expect(agent.queryByRole("link", { name: "View agent workflows" })).not.toBeInTheDocument();
        expect(agent.queryByRole("link", { name: "Open deployment analysis →" })).not.toBeInTheDocument();
        expect(within(screen.getByRole("region", { name: "Work activity" })).getByRole("link", { name: "Review workflows →" })).toHaveAttribute("href", "/workflows");
        expect(registry().getByText("Atlas Core reports 5 providers. 3 need attention. 1 status is unknown.")).toBeInTheDocument();
        await user.click(registry().getByText("Show provider status (5)"));
        expect(registry().getByText("Healthy")).toBeInTheDocument();
        expect(registry().getByText("Reported status: failed")).toBeInTheDocument();
        expect(registry().getByText("Unavailable")).toBeInTheDocument();
        expect(registry().queryByText("Reported status: offline")).not.toBeInTheDocument();
        expect(registry().queryByText("Check time unavailable.")).not.toBeInTheDocument();
        expect(registry().getByText("Status unknown")).toBeInTheDocument();
        expect(registry().getByRole("link", { name: "View alpha →", hidden: true })).toHaveAttribute("href", "/providers/alpha");
        expect(registry().getByText(/does not allow provider actions/)).not.toBeVisible();
        expect(registry().queryByText(/which model an Agent uses/)).not.toBeInTheDocument();
        await user.click(registry().getByText("About provider status"));
        expect(registry().getByText(/does not allow provider actions/)).toBeVisible();
        expect(screen.queryByText(/private-canary/)).not.toBeInTheDocument();
        expect(screen.getByTestId("overview-grid").children).toHaveLength(6);
    });
    it("uses the product name for the known service identifier and labels its version", () => {
        show({ agent: { data: { app_name: "atlas-agent", version: "0.22.0" } } });
        const agent = within(screen.getByRole("region", { name: "Agent details" }));

        const agentField = agent.getByText("Agent", { exact: true }).parentElement;
        const versionField = agent.getByText("Version", { exact: true }).parentElement;
        expect(agentField).toHaveTextContent("Atlas Agent");
        expect(versionField).toHaveTextContent("0.22.0");
        expect(agent.queryByText("atlas-agent", { exact: true })).not.toBeInTheDocument();
        expect(agent.queryByText("This report includes only the Agent name and version.")).not.toBeInTheDocument();
    });
    it("explains unavailable Agent details without inventing a health state", () => {
        show({ agent: { unavailable: true } });
        const agent = within(screen.getByRole("region", { name: "Agent details" }));
        expect(agent.getByText("Agent details could not be loaded.")).toBeInTheDocument();
        expect(agent.queryByText(/workflow availability/i)).not.toBeInTheDocument();
        expect(agent.queryByText("Unknown", { exact: true })).not.toBeInTheDocument();
        expect(agent.queryByText("Check time unavailable.")).not.toBeInTheDocument();
        expect(agent.queryByText("Evidence unavailable.")).not.toBeInTheDocument();
    });
    it("explains when the latest Agent report could not be loaded", () => {
        show({ agent: { data: { app_name: "Development Agent" }, unavailable: true, stale: true } });
        const agent = within(screen.getByRole("region", { name: "Agent details" }));
        expect(agent.getByText("Development Agent")).toBeInTheDocument();
        expect(agent.getByText("Showing the last Agent report; current details could not be loaded.")).toBeInTheDocument();
        expect(agent.queryByText(/workflow availability/i)).not.toBeInTheDocument();
        expect(agent.queryByText("Unknown", { exact: true })).not.toBeInTheDocument();
    });
    it("retains stale observations without presenting cached success as current", async () => {
        const user = userEvent.setup();
        const view = show({ providers: { data: [provider("alpha", "healthy")], stale: true, unavailable: true }, agent: { unavailable: true } });
        expect(registry().getByRole("article", { name: "alpha" })).not.toBeVisible();
        expect(registry().getByText("Last report included 1 provider; current status may have changed.")).toBeInTheDocument();
        await user.click(registry().getByText("Show provider status (1)"));
        expect(registry().getByText("Last known report (out of date): Healthy.")).toBeVisible();
        view.rerender(<MemoryRouter><Overview evidence={{ providers: { data: [], stale: true, unavailable: true } }} /></MemoryRouter>);
        expect(registry().queryByText("No providers configured.")).not.toBeInTheDocument();
        expect(registry().getByText("No providers were in the last Atlas Core report; the current list is unknown.")).toBeInTheDocument();
    });
    it.each([undefined, null, {}, { providers: [] }])("does not present malformed or missing registries as empty: %s", data => {
        show({ providers: { data } });
        const expected = data === undefined ? "Atlas Core’s provider list is not available." : "Provider list could not be read.";
        expect(registry().getByText(expected)).toBeInTheDocument();
        expect(registry().queryByText("No providers configured.")).not.toBeInTheDocument();
    });
    it("rejects malformed and duplicate identities and unsafe links in the collapsed list", async () => {
        const user = userEvent.setup();
        show({ providers: { data: [null, {}, provider("duplicate", "healthy"), provider("duplicate", "healthy"), ...["..", "../escape", "https://host", "a/b", "%2e%2e", "\ud800", "token-private"].map(id => provider(id, "healthy")), { ...provider("bad-name", "healthy"), name: { secret: "private-canary" } }, provider("valid", {})] } });
        registry().getAllByRole("article", { name: "Provider information unavailable" }).forEach(row => expect(row).not.toBeVisible());
        await user.click(registry().getByText("Show provider status (13)"));
        expect(within(registry().getByRole("article", { name: "valid" })).getByText("Status unknown")).toBeVisible();
        expect(registry().getAllByRole("link", { hidden: true })).toHaveLength(2);
        expect(registry().getByRole("link", { name: "View valid →", hidden: true })).toHaveAttribute("href", "/providers/valid");
    });
    it("withholds sensitive configuration, diagnostics, and identity labels", () => {
        const view = show({ providers: { data: [{ ...provider("safe", "healthy"), config: { key: "private-canary" }, model: "private-canary", health: { status: "healthy", message: "Bearer private-canary", details: { password: "private-canary" } } }] }, agent: { data: { app_name: "Bearer private-canary", version: {} } } });
        expect(view.container.innerHTML).not.toContain("private-canary");
    });
});
