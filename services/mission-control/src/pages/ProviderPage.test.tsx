import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { useMissionControl } from "../hooks/useMissionControl";
import { ProviderPage } from "./ProviderPage";

vi.mock("../hooks/useMissionControl", () => ({ useMissionControl: vi.fn() }));
vi.mock("../components/ProviderOverview", () => ({ ProviderOverview: () => <section><h2>Provider overview</h2></section> }));
vi.mock("../components/ProviderResources", () => ({ ProviderResources: () => <section><h2>Resources and monitoring</h2></section> }));
vi.mock("../components/ProviderActions", () => ({ ProviderActions: () => <section><h2>Provider actions</h2></section> }));
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
        expect(screen.getByRole("link", { name: "Return to Mission Control" })).toHaveAttribute("href", "/");
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
        { isLoading: true, error: null },
        { isLoading: false, error: "Could not load providers" },
    ])("does not call a provider missing before its catalog is available: %j", (state) => {
        vi.mocked(useMissionControl).mockReturnValue(providerPageState(undefined, { providers: [], ...state }));
        render(<MemoryRouter initialEntries={["/providers/proxmox"]}><Routes><Route path="/providers/:providerId" element={<ProviderPage />} /></Routes></MemoryRouter>);
        expect(screen.queryByRole("heading", { name: "Provider not found" })).not.toBeInTheDocument();
        expect(screen.getByText(state.isLoading ? "Loading provider details..." : "Atlas Core unavailable")).toBeInTheDocument();
    });

    it("orders monitoring, diagnostics, compatibility, maintenance, and retained evidence distinctly", () => {
        render(<MemoryRouter initialEntries={["/providers/proxmox"]}><Routes><Route path="/providers/:providerId" element={<ProviderPage />} /></Routes></MemoryRouter>);

        const ordered = [
            position("Provider overview"),
            position("Resources and monitoring"),
            position("Diagnostics"),
            position("Advisory recommendations"),
            position("Provider actions"),
            position("Operational maintenance"),
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
        expect(screen.getByText(/start a request, review its proposal and plan, then approve the exact action/)).toBeInTheDocument();
        expect(screen.getByRole("link", { name: "Request operational maintenance" })).toHaveAttribute("href", "/operations/request");
    });
});
