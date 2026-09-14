import { render, screen, within } from "@testing-library/react";
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
function show(ai?: Evidence) {
    render(<MemoryRouter><Overview evidence={{ ai }} /></MemoryRouter>);
    return within(screen.getByRole("region", { name: "Local AI / Runtime" }));
}

describe("integrated Local AI runtime observations", () => {
    it.each([["online", "Healthy"], ["offline", "Unavailable"], ["degraded", "Degraded"], ["future", "Unknown"]])("preserves %s provider health without claiming runtime availability", (status, label) => {
        const card = show({ data: data(status) });
        expect(card.getAllByText(label).length).toBeGreaterThan(0);
        expect(card.getByText(/Local AI availability is unknown/)).toBeInTheDocument();
        expect(card.getByText("1.2")).toBeInTheDocument();
        expect(card.getByText("12 ms")).toBeInTheDocument();
        expect(card.getByText("Reported installed models: model:latest")).toBeInTheDocument();
        expect(card.getByText("Reported running models: running-model")).toBeInTheDocument();
        expect(card.getByText("Configured model identity: Unknown.")).toBeInTheDocument();
        expect(card.getByRole("link")).toHaveAttribute("href", "/providers/runtime");
        expect(card.queryByRole("button")).not.toBeInTheDocument();
        expect(screen.getByTestId("overview-grid").children).toHaveLength(6);
    });
    it.each([undefined, null, [], {}, { provider: { online: true } }, { health: [], models: { installed: [null], running: {} } }])("keeps absent or malformed evidence unknown: %j", value => {
        const card = show({ data: value });
        expect(card.queryByText("Healthy")).not.toBeInTheDocument();
        expect(card.getByText(/Reported installed models: Unknown/)).toBeInTheDocument();
        expect(card.getByText(/Reported running models: Unknown/)).toBeInTheDocument();
        expect(card.queryByRole("link")).not.toBeInTheDocument();
    });
    it("distinguishes empty inventory, partial identities, and independent inventory failures", () => {
        const card = show({ data: { ...data(), models: { installed: [], running: [null, { name: "one" }] } } });
        expect(card.getByText("Reported installed models: None reported")).toBeInTheDocument();
        expect(card.getByText("Reported running models: one · Some model identities unknown")).toBeInTheDocument();
    });
    it.each(["private diagnostic", false, "", {}, []])("does not present errored inventory as empty: %j", error => {
        const card = show({ data: { ...data(), models: { installed: [], running: [{ model: "one" }] }, errors: { installed_models: error } } });
        expect(card.getByText("Reported installed models: Unknown — inventory unavailable")).toBeInTheDocument();
        expect(card.getByText("Reported running models: one")).toBeInTheDocument();
        expect(card.queryByText(/private diagnostic/)).not.toBeInTheDocument();
    });
    it.each([null, [], "failed"])('rejects malformed inventory error envelopes: %j', errors => {
        const card = show({ data: { ...data(), errors } });
        expect(card.getByText("Reported running models: Unknown — inventory unavailable")).toBeInTheDocument();
    });
    it("retains stale inventories explicitly as last-known and suppresses current health", () => {
        const card = show({ data: data(), stale: true, unavailable: true });
        expect(card.queryByText("Healthy", { exact: true })).not.toBeInTheDocument();
        expect(card.getByText("Unknown · Stale evidence")).toBeInTheDocument();
        expect(card.getByText("Last-known running models: running-model")).toBeInTheDocument();
        expect(card.getByText(/current version, latency, and model inventory unknown/)).toBeInTheDocument();
    });
    it("distinguishes observation failure from runtime offline", () => {
        const card = show({ unavailable: true });
        expect(card.getByText(/AI status observation unavailable; runtime availability is unknown/)).toBeInTheDocument();
        expect(card.queryByText("Unavailable", { exact: true })).not.toBeInTheDocument();
    });
    it.each(["..", "https://user:password@host", "runtime/other", "\ud800", "token-abc"])('rejects unsafe provider links and withholds sensitive fields: %s', id => {
        const card = show({ data: { ...data(), provider: { id, name: "https://user:password@host" }, health: { status: "unknown", latency_ms: -1, details: { version: "token=private", endpoint: "private diagnostic" } }, models: { installed: [{ name: "https://user:password@host" }], running: [] } } });
        expect(card.queryByRole("link")).not.toBeInTheDocument();
        expect(card.queryByText(/user:password|token=private|private diagnostic/)).not.toBeInTheDocument();
        expect(card.queryByText("-1 ms")).not.toBeInTheDocument();
    });
    it("bounds inventories while disclosing omitted identities", () => {
        const card = show({ data: { ...data(), models: { running: Array.from({ length: 5 }, (_, i) => ({ name: `model-${i}` })) } } });
        expect(card.getByText(/showing 3 of 5 reported identities/)).toBeInTheDocument();
        expect(card.queryByText(/model-4/)).not.toBeInTheDocument();
    });
});
