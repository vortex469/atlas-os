import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";
import { Overview } from "./MissionControl";
import type { Evidence } from "./useOverviewEvidence";

const data = (status = "online") => ({
    provider: { id: "runtime", name: "Runtime", online: status === "online" },
    health: { status, latency_ms: 12, details: { version: "1.2" } },
    models: { installed: [{ name: "model:latest" }], running: [{ model: "running-model" }] },
    errors: { installed_models: null, running_models: null },
});
function show(ai?: Evidence, loading = false) {
    render(<MemoryRouter><Overview evidence={{ ai }} loading={loading} /></MemoryRouter>);
    return within(screen.getByRole("region", { name: "AI provider" }));
}

describe("integrated Local AI runtime observations", () => {
    it.each([["online", "Healthy"], ["offline", "Unavailable"], ["degraded", "Degraded"], ["future", "Status unknown"]])("preserves %s provider health without claiming runtime availability", async (status, label) => {
        const user = userEvent.setup();
        const card = show({ data: data(status) });
        expect(card.getAllByText(label).length).toBeGreaterThan(0);
        expect(card.getByText("Atlas does not report where this provider runs or which model is selected or ready to use.")).toBeInTheDocument();
        expect(card.getByText("1.2")).toBeInTheDocument();
        expect(card.getByText("12 ms")).toBeInTheDocument();
        expect(card.getByText("Installed models: model:latest")).toBeInTheDocument();
        expect(card.getByText("Running models: running-model")).toBeInTheDocument();
        expect(card.getByText("Technical details")).toBeInTheDocument();
        expect(card.getByText("Version", { exact: true })).not.toBeVisible();
        await user.click(card.getByText("Technical details"));
        expect(card.getByText("Version", { exact: true })).toBeVisible();
        expect(card.getByText("1.2")).toBeVisible();
        expect(card.getByRole("link")).toHaveAttribute("href", "/providers/runtime");
        expect(card.queryByRole("button")).not.toBeInTheDocument();
        expect(screen.getByTestId("overview-grid").children).toHaveLength(6);
    });
    it("shows a clear empty state when no provider report is available", () => {
        const card = show({ data: undefined });
        expect(card.getByText("AI provider information is not available.")).toBeInTheDocument();
        expect(card.queryByText("Unknown", { exact: true })).not.toBeInTheDocument();
    });
    it.each([null, [], {}, { provider: { online: true } }, { health: [], models: { installed: [null], running: {} } }])("keeps malformed provider evidence unknown: %j", value => {
        const card = show({ data: value });
        expect(card.queryByText("Healthy")).not.toBeInTheDocument();
        expect(card.getByText(/^Installed models:/)).toHaveTextContent(/Not available|Model names unavailable/);
        expect(card.getByText(/Running models: Not available/)).toBeInTheDocument();
        expect(card.queryByRole("link")).not.toBeInTheDocument();
    });
    it("distinguishes empty inventory, partial identities, and independent inventory failures", () => {
        const card = show({ data: { ...data(), models: { installed: [], running: [null, { name: "one" }] } } });
        expect(card.getByText("Installed models: None reported")).toBeInTheDocument();
        expect(card.getByText("Running models: one · Some names unavailable")).toBeInTheDocument();
    });
    it.each(["private diagnostic", false, "", {}, []])("does not present errored inventory as empty: %j", error => {
        const card = show({ data: { ...data(), models: { installed: [], running: [{ model: "one" }] }, errors: { installed_models: error } } });
        expect(card.getByText("Installed models: Not available")).toBeInTheDocument();
        expect(card.getByText("Running models: one")).toBeInTheDocument();
        expect(card.queryByText(/private diagnostic/)).not.toBeInTheDocument();
    });
    it.each([null, [], "failed"])('rejects malformed inventory error envelopes: %j', errors => {
        const card = show({ data: { ...data(), errors } });
        expect(card.getByText("Running models: Not available")).toBeInTheDocument();
    });
    it("retains stale inventories explicitly as last-known and suppresses current health", () => {
        const card = show({ data: data(), stale: true, unavailable: true });
        expect(card.queryByText("Healthy", { exact: true })).not.toBeInTheDocument();
        expect(card.getByText("Status unknown", { exact: true })).toBeInTheDocument();
        expect(card.getByText("Last report: Healthy.")).toBeInTheDocument();
        expect(card.getByText("Last known running models: running-model")).toBeInTheDocument();
        expect(card.getByText(/Current version, response time, and model list are unknown/)).toBeInTheDocument();
    });
    it("distinguishes observation failure from runtime offline", () => {
        const card = show({ unavailable: true });
        expect(card.getByText("Provider details are unavailable.")).toBeInTheDocument();
        expect(card.queryByText("Use Refresh to try again.")).not.toBeInTheDocument();
        expect(card.queryByText("Current information could not be loaded.")).not.toBeInTheDocument();
        expect(card.queryByText("Unknown", { exact: true })).not.toBeInTheDocument();
        expect(card.queryByText("Configured provider: Unknown")).not.toBeInTheDocument();
        expect(card.queryByText("Unavailable", { exact: true })).not.toBeInTheDocument();
    });
    it("shows only a loading message before the first provider report", () => {
        const card = show(undefined, true);
        expect(card.getByText("Loading AI provider information…")).toBeInTheDocument();
        expect(card.queryByText("Unknown", { exact: true })).not.toBeInTheDocument();
        expect(card.queryByText("Configured provider: Unknown")).not.toBeInTheDocument();
    });
    it.each(["..", "https://user:password@host", "runtime/other", "\ud800", "token-abc"])('rejects unsafe provider links and withholds sensitive fields: %s', id => {
        const card = show({ data: { ...data(), provider: { id, name: "https://user:password@host" }, health: { status: "unknown", latency_ms: -1, details: { version: "token=private", endpoint: "private diagnostic" } }, models: { installed: [{ name: "https://user:password@host" }], running: [] } } });
        expect(card.queryByRole("link")).not.toBeInTheDocument();
        expect(card.queryByText(/user:password|token=private|private diagnostic/)).not.toBeInTheDocument();
        expect(card.queryByText("-1 ms")).not.toBeInTheDocument();
    });
    it("lets operators reveal all reported installed and running model names", async () => {
        const user = userEvent.setup();
        const card = show({ data: { ...data(), models: {
            installed: Array.from({ length: 4 }, (_, i) => ({ name: `installed-${i}` })),
            running: Array.from({ length: 5 }, (_, i) => ({ name: `model-${i}` })),
        } } });
        expect(card.getByText(/first 3 of 5/)).toBeInTheDocument();
        expect(card.getByText("model-4")).not.toBeVisible();
        expect(card.getByText("installed-3")).not.toBeVisible();

        await user.click(card.getByText("Technical details"));
        await user.click(card.getByText("Show all 4 installed model names"));
        await user.click(card.getByText("Show all 5 running model names"));
        expect(card.getByText("installed-3")).toBeVisible();
        expect(card.getByText("model-4")).toBeVisible();
    });
});
