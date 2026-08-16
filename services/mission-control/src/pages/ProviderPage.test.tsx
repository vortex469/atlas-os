import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { useMissionControl } from "../hooks/useMissionControl";
import { ProviderPage } from "./ProviderPage";

vi.mock("../hooks/useMissionControl", () => ({ useMissionControl: vi.fn() }));
vi.mock("../components/ProviderOverview", () => ({ ProviderOverview: () => <section><h2>Provider overview</h2></section> }));
vi.mock("../components/ProviderResources", () => ({ ProviderResources: () => <section><h2>Resources and monitoring</h2></section> }));
vi.mock("../components/ProviderActions", () => ({ ProviderActions: () => <section><h2>Compatibility actions</h2></section> }));
vi.mock("../components/ProviderConnection", () => ({ ProviderConnection: () => <section><h2>Connection</h2></section> }));
vi.mock("../components/ProviderTelemetryTrend", () => ({ ProviderTelemetryTrend: () => <section><h2>Telemetry</h2></section> }));
vi.mock("../components/ProviderPolicyDetails", () => ({ ProviderPolicyDetails: () => <section><h2>Legacy policy evidence</h2></section> }));

function position(name: string): Element {
    return screen.getByRole("heading", { name });
}

describe("ProviderPage authority layout", () => {
    beforeEach(() => {
        vi.mocked(useMissionControl).mockReturnValue({
            summary: { findings: [], recommendations: [] },
            providers: [{
                id: "proxmox",
                name: "Proxmox",
                workspace: "operations",
                priority: "critical",
                version: "1",
                description: "Virtualization",
                icon: "server",
                capabilities: ["resources", "connection"],
                health: { status: "online", latency_ms: null, http_status: null, message: null, details: {} },
            }],
            policies: { intelligence: { providers: {} } },
            telemetryHistory: [],
            lastUpdated: null,
            error: null,
            isLoading: false,
            isRefreshing: false,
            refresh: vi.fn(),
        } as unknown as ReturnType<typeof useMissionControl>);
    });

    it("orders monitoring, diagnostics, compatibility, maintenance, and retained evidence distinctly", () => {
        render(<MemoryRouter initialEntries={["/providers/proxmox"]}><Routes><Route path="/providers/:providerId" element={<ProviderPage />} /></Routes></MemoryRouter>);

        const ordered = [
            position("Provider overview"),
            position("Resources and monitoring"),
            position("Diagnostics"),
            position("Advisory recommendations"),
            position("Compatibility actions"),
            position("Operational maintenance"),
            position("Connection"),
            position("Telemetry"),
            position("Legacy policy evidence"),
        ];
        for (let index = 1; index < ordered.length; index += 1) {
            expect(ordered[index - 1].compareDocumentPosition(ordered[index]) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
        }
    });

    it("states that monitoring is policy-only and maintenance is a separate workflow", () => {
        render(<MemoryRouter initialEntries={["/providers/proxmox"]}><Routes><Route path="/providers/:providerId" element={<ProviderPage />} /></Routes></MemoryRouter>);
        expect(screen.getByText(/Monitoring expectations describe monitoring policy/)).toHaveTextContent("do not start, stop, restart, or remediate resources");
        expect(screen.getByText(/distinct authenticated request, candidate, planning, and approval workflow/)).toBeInTheDocument();
        expect(screen.getByRole("link", { name: "Request operational maintenance" })).toHaveAttribute("href", "/operations/request");
    });
});
