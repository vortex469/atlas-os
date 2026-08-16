import { render, screen, within } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { getProviderManagement } from "../api/providerManagement";
import { getProviderResources } from "../api/resources";
import { useOperatorSession } from "../hooks/operatorSessionContext";
import { useMissionControl } from "../hooks/useMissionControl";
import { ProviderPage } from "./ProviderPage";

vi.mock("../hooks/useMissionControl", () => ({ useMissionControl: vi.fn() }));
vi.mock("../hooks/operatorSessionContext", () => ({ useOperatorSession: vi.fn() }));
vi.mock("../api/providerManagement", () => ({
    getProviderManagement: vi.fn(),
    getAuthenticatedProviderManagement: vi.fn(),
    putProviderMonitoringIntent: vi.fn(),
}));
vi.mock("../api/resources", () => ({ getProviderResources: vi.fn(), refreshProviderResources: vi.fn() }));
vi.mock("../components/ProviderOverview", () => ({ ProviderOverview: () => <section><h2>Provider overview</h2></section> }));
vi.mock("../components/ProviderActions", () => ({ ProviderActions: () => <section><h2>Compatibility actions</h2></section> }));
vi.mock("../components/ProviderConnection", () => ({ ProviderConnection: () => null }));
vi.mock("../components/ProviderTelemetryTrend", () => ({ ProviderTelemetryTrend: () => null }));

describe("ProviderPage monitoring and legacy authority", () => {
    beforeEach(() => {
        vi.mocked(useOperatorSession).mockReturnValue({
            authenticated: false,
            principal: null,
            csrfToken: null,
            loading: false,
            error: null,
            login: vi.fn(),
            logout: vi.fn(),
            invalidate: vi.fn(),
        });
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
                capabilities: ["resources"],
                health: { status: "online", latency_ms: null, http_status: null, message: null, details: {} },
            }],
            policies: {
                proxmox: { guests: { "110": { expected: "stopped" } } },
                intelligence: { providers: {} },
            },
            telemetryHistory: [],
            lastUpdated: null,
            error: null,
            isLoading: false,
            isRefreshing: false,
            refresh: vi.fn(),
        } as unknown as ReturnType<typeof useMissionControl>);
        vi.mocked(getProviderResources).mockResolvedValue({
            provider_id: "proxmox",
            provider_name: "Proxmox",
            refreshed_at: "2026-08-16T00:00:00Z",
            resources: [{
                provider_id: "proxmox",
                resource_id: "110",
                display_name: "Frigate",
                resource_type: "qemu",
                current_state: "running",
                expectation: { value: "stopped", label: "Expected stopped", state: "configured", allowed_values: [] },
                configured: true,
                missing: false,
                needs_review: false,
                metadata: { vmid: 110 },
            }],
            summary: { total: 1, configured: 1, needs_review: 0, missing: 0, ignored: 0, by_type: { qemu: 1 }, by_state: { running: 1 } },
            metadata: {},
        });
        vi.mocked(getProviderManagement).mockResolvedValue({
            schema_version: "provider-management-v2",
            provider_id: "proxmox",
            provider_name: "Proxmox",
            sections: [],
            resource_types: [],
            provider_intent_activation: "activated",
            provider_intent_authority_status: "available",
            grants_permission: false,
            grants_execution: false,
            resources: [{
                provider_id: "proxmox",
                resource_id: "110",
                resource_type: "qemu",
                display_name: "Frigate",
                current_state: "running",
                missing: false,
                identity_assurance: "authoritative",
                management_fingerprint: `provider-management-fingerprint-v1:${"a".repeat(64)}`,
                intent_authority: "provider_intent",
                intent_status: "configured",
                intent_reason: "matching_active_intent",
                expectation: "running",
                record_version: 1,
                legacy_review_available: false,
                legacy_expectation: null,
                replacement_detected: false,
                mutation_available: false,
                operationally_requestable: false,
                grants_execution: false,
            }],
        });
    });

    it("keeps public v2 running current and YAML stopped only as legacy evidence", async () => {
        render(<MemoryRouter initialEntries={["/providers/proxmox"]}><Routes><Route path="/providers/:providerId" element={<ProviderPage />} /></Routes></MemoryRouter>);

        const monitoring = screen.getByRole("heading", { name: "Resources and monitoring" }).closest("section");
        const legacy = screen.getByRole("heading", { name: "Legacy policy evidence" }).closest("section");
        expect(monitoring).not.toBeNull();
        expect(legacy).not.toBeNull();
        expect(await within(monitoring!).findByText("Expected running")).toBeInTheDocument();
        expect(within(monitoring!).queryByText("Expected stopped")).not.toBeInTheDocument();
        expect(within(legacy!).getByText("110: stopped")).toBeInTheDocument();
        expect(within(legacy!).getByText(/non-authoritative review context/i)).toBeInTheDocument();
        expect(within(legacy!).queryByText(/currently enforced|current monitoring intent/i)).not.toBeInTheDocument();
    });
});
