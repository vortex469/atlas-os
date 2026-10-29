import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { useMissionControl } from "../hooks/useMissionControl";
import { ProviderPage } from "./ProviderPage";

vi.mock("../hooks/useMissionControl", () => ({ useMissionControl: vi.fn() }));
vi.mock("../components/ProviderOverview", () => ({ ProviderOverview: () => <section><h2>Provider overview</h2></section> }));
vi.mock("../components/ProviderResources", () => ({ ProviderResources: () => <section><h2>Resources and monitoring</h2></section> }));
vi.mock("../components/ProviderActions", () => ({ ProviderActions: () => <section><h2>Direct provider actions</h2></section> }));
vi.mock("../components/ProviderConnection", () => ({ ProviderConnection: () => <section><h2>Connection</h2></section> }));
vi.mock("../components/ProviderTelemetryTrend", () => ({ ProviderTelemetryTrend: () => <section><h2>Telemetry</h2></section> }));
vi.mock("../components/ProviderPolicyDetails", () => ({ ProviderPolicyDetails: () => <section><h2>Older VM settings</h2></section> }));

function position(name: string): Element {
    return screen.getByRole("heading", { name });
}

function providerPageState(capabilities: unknown, overrides: Record<string, unknown> = {}) {
    return {
        summary: { findings: [], recommendations: [] },
        providers: [{
            id: "proxmox",
            name: "Proxmox",
            workspace: "operations",
            priority: "critical",
            version: "1",
            description: "Virtualization",
            icon: "server",
            capabilities,
            health: { status: "online", latency_ms: null, http_status: null, message: null, details: {} },
        }],
        policies: { intelligence: { providers: {} } },
        telemetryHistory: [],
        lastUpdated: null,
        error: null,
        isLoading: false,
        isRefreshing: false,
        refresh: vi.fn(),
        ...overrides,
    } as unknown as ReturnType<typeof useMissionControl>;
}

describe("ProviderPage authority layout", () => {
    beforeEach(() => {
        vi.mocked(useMissionControl).mockReturnValue(providerPageState(["resources", "connection"]));
    });

    it("explains an empty provider catalog instead of leaving the detail screen blank", () => {
        vi.mocked(useMissionControl).mockReturnValue(providerPageState(undefined, { providers: [] }));
        render(<MemoryRouter initialEntries={["/providers/proxmox"]}><Routes><Route path="/providers/:providerId" element={<ProviderPage />} /></Routes></MemoryRouter>);
        expect(screen.getByRole("heading", { name: "Provider not found" })).toBeInTheDocument();
        expect(screen.getByText("This provider is not in the current catalog.")).toBeInTheDocument();
        expect(screen.getByRole("link", { name: "← All providers" })).toHaveAttribute("href", "/providers");
        expect(screen.queryByText(/Refresh to check again/)).not.toBeInTheDocument();
    });

    it("keeps provider details usable when supported-feature data is missing", () => {
        vi.mocked(useMissionControl).mockReturnValue(providerPageState(undefined));
        render(<MemoryRouter initialEntries={["/providers/proxmox"]}><Routes><Route path="/providers/:providerId" element={<ProviderPage />} /></Routes></MemoryRouter>);
        expect(screen.getByRole("status")).toHaveTextContent("Supported provider features could not be loaded. Some provider sections are hidden.");
        expect(screen.getByRole("heading", { name: "Provider overview" })).toBeInTheDocument();
        expect(screen.getByRole("heading", { name: "Diagnostics" })).toBeInTheDocument();
        expect(screen.queryByRole("heading", { name: "Resources and monitoring" })).not.toBeInTheDocument();
        expect(screen.queryByRole("heading", { name: "Connection" })).not.toBeInTheDocument();
    });

    it.each([
        { isLoading: true, error: null, providerCatalogUnavailable: false },
        { isLoading: false, error: "Some provider information could not be refreshed. Existing information may be out of date.", providerCatalogUnavailable: true, failedSources: ["provider catalog"] },
    ])("does not call a provider missing before its catalog is available: %j", (state) => {
        vi.mocked(useMissionControl).mockReturnValue(providerPageState(undefined, { providers: [], ...state }));
        render(<MemoryRouter initialEntries={["/providers/proxmox"]}><Routes><Route path="/providers/:providerId" element={<ProviderPage />} /></Routes></MemoryRouter>);
        expect(screen.queryByRole("heading", { name: "Provider not found" })).not.toBeInTheDocument();
        expect(screen.getByText(state.isLoading ? "Loading provider details..." : "Some information could not be refreshed")).toBeInTheDocument();
    });

    it("keeps provider details visible when the diagnostics source is unavailable", () => {
        vi.mocked(useMissionControl).mockReturnValue(providerPageState(["resources", "connection"], {
            summary: null,
            error: "Some provider information could not be refreshed. Existing information may be out of date.",
            failedSources: ["diagnostics"],
            summaryUnavailable: true,
        }));
        render(<MemoryRouter initialEntries={["/providers/proxmox"]}><Routes><Route path="/providers/:providerId" element={<ProviderPage />} /></Routes></MemoryRouter>);

        expect(screen.getByRole("heading", { name: "Provider overview" })).toBeInTheDocument();
        expect(screen.getByText("Some information could not be refreshed")).toBeInTheDocument();
        expect(screen.getByText("Unavailable: diagnostics.")).toBeInTheDocument();
        expect(screen.getByText("Diagnostics could not be loaded.")).toBeInTheDocument();
        expect(screen.getByText("Recommendations could not be loaded.")).toBeInTheDocument();
        expect(screen.queryByText("No messages about this provider right now.")).not.toBeInTheDocument();
        expect(screen.queryByText("No recommendations for this provider right now.")).not.toBeInTheDocument();
    });

    it("does not call a provider missing when the provider catalog could not be checked", () => {
        vi.mocked(useMissionControl).mockReturnValue(providerPageState(undefined, {
            providers: [],
            error: "Some provider information could not be refreshed. Existing information may be out of date.",
            failedSources: ["provider catalog"],
            providerCatalogUnavailable: true,
        }));
        render(<MemoryRouter initialEntries={["/providers/proxmox"]}><Routes><Route path="/providers/:providerId" element={<ProviderPage />} /></Routes></MemoryRouter>);

        expect(screen.getByText("Atlas could not confirm whether this provider is currently listed.")).toBeInTheDocument();
        expect(screen.queryByRole("heading", { name: "Provider not found" })).not.toBeInTheDocument();
    });

    it("puts reviewed maintenance before direct actions, connection details, and retained evidence", () => {
        render(<MemoryRouter initialEntries={["/providers/proxmox"]}><Routes><Route path="/providers/:providerId" element={<ProviderPage />} /></Routes></MemoryRouter>);

        const ordered = [
            position("Provider overview"),
            position("Resources and monitoring"),
            position("Diagnostics"),
            position("Recommendations"),
            position("Planned maintenance"),
            position("Direct provider actions"),
            position("Connection"),
            position("Telemetry"),
            position("Older VM settings"),
        ];
        for (let index = 1; index < ordered.length; index += 1) {
            expect(ordered[index - 1].compareDocumentPosition(ordered[index]) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
        }
    });

    it("states that monitoring is policy-only and maintenance is a separate workflow", () => {
        render(<MemoryRouter initialEntries={["/providers/proxmox"]}><Routes><Route path="/providers/:providerId" element={<ProviderPage />} /></Routes></MemoryRouter>);
        expect(screen.getByText("Health and monitoring messages for this provider.")).toBeInTheDocument();
        expect(screen.getByText("No messages about this provider right now.")).toBeInTheDocument();
        expect(screen.getByText(/Monitoring expectations describe monitoring policy/)).toHaveTextContent("do not start, stop, restart, or remediate resources");
        expect(screen.getByText("Submit a request, review the plan, and approve it before Atlas starts maintenance.")).toBeInTheDocument();
        expect(screen.queryByText(/exact action/i)).not.toBeInTheDocument();
        expect(screen.getByRole("link", { name: "Request maintenance" })).toHaveAttribute("href", "/operations/request");
    });

    it("explains recommendations are suggestions and shows a plain empty state", () => {
        render(<MemoryRouter initialEntries={["/providers/proxmox"]}><Routes><Route path="/providers/:providerId" element={<ProviderPage />} /></Routes></MemoryRouter>);

        expect(screen.getByRole("heading", { name: "Recommendations" })).toBeInTheDocument();
        expect(screen.getByText("Suggestions for you to review. They don't change settings or run actions.")).toBeInTheDocument();
        expect(screen.getByText("No recommendations for this provider right now.")).toBeInTheDocument();
    });
});
