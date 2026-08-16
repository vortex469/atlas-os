import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { getAuthenticatedProviderManagement, getProviderManagement } from "../api/providerManagement";
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
            summary: {
                findings: [{
                    id: "finding-1",
                    source: "proxmox",
                    component: "proxmox",
                    category: "state_mismatch",
                    severity: "warning",
                    title: "Provider monitoring evidence",
                    message: "Observed and expected state are evaluated independently.",
                    affects_health: false,
                    score_penalty: 0,
                    details: {},
                }],
                recommendations: [{
                    title: "Review provider evidence",
                    reason: "Operator review is advisory and does not grant authority.",
                    component: "proxmox",
                    priority: "low",
                    confidence: 0.9,
                    estimated_effort: "low",
                }],
            },
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
        expect(within(monitoring!).getByText("Running")).toBeInTheDocument();
        expect(within(monitoring!).getByText("Authoritative")).toBeInTheDocument();
        expect(within(monitoring!).getByText("Configured — matches observed state")).toBeInTheDocument();
        expect(within(monitoring!).queryByText("Expected stopped")).not.toBeInTheDocument();
        expect(screen.getByText(/Advisory finding · Proxmox/)).toBeInTheDocument();
        expect(screen.getByText("Advisory recommendation")).toBeInTheDocument();
        expect(screen.getByRole("heading", { name: "Compatibility actions" })).toBeInTheDocument();
        expect(screen.getByRole("link", { name: "Request operational maintenance" })).toHaveAttribute("href", "/operations/request");
        expect(within(legacy!).getByText("110: stopped")).toBeInTheDocument();
        expect(within(legacy!).getByText(/non-authoritative review context/i)).toBeInTheDocument();
        expect(within(legacy!).queryByText(/currently enforced|current monitoring intent/i)).not.toBeInTheDocument();
    });

    it("exposes editing only for the supported live authoritative QEMU coordinate", async () => {
        const user = userEvent.setup();
        vi.mocked(useOperatorSession).mockReturnValue({
            authenticated: true,
            principal: null,
            csrfToken: "csrf",
            loading: false,
            error: null,
            login: vi.fn(),
            logout: vi.fn(),
            invalidate: vi.fn(),
        });
        const inventory = await vi.mocked(getProviderResources)("proxmox");
        vi.mocked(getProviderResources).mockResolvedValue({
            ...inventory,
            resources: [
                inventory.resources[0],
                { ...inventory.resources[0], resource_type: "lxc", resource_id: "110", display_name: "Legacy container" },
            ],
            summary: { ...inventory.summary, total: 2, by_type: { qemu: 1, lxc: 1 } },
        });
        const publicDescriptor = await vi.mocked(getProviderManagement)("proxmox");
        const lxc = {
            ...publicDescriptor.resources[0],
            resource_type: "lxc",
            display_name: "Legacy container",
            identity_assurance: "unsupported" as const,
            management_fingerprint: null,
            intent_status: "unsupported" as const,
            intent_reason: "resource_type_unsupported" as const,
            expectation: null,
            record_version: null,
        };
        vi.mocked(getProviderManagement).mockResolvedValue({ ...publicDescriptor, resources: [publicDescriptor.resources[0], lxc] });
        vi.mocked(getAuthenticatedProviderManagement).mockResolvedValue({
            schema_version: "provider-management-v3",
            provider_id: "proxmox",
            provider_name: "Proxmox",
            sections: [],
            resource_types: [],
            provider_intent_activation: "activated",
            provider_intent_authority_status: "available",
            caller_has_provider_intent_update: true,
            grants_permission: false,
            grants_execution: false,
            resources: [{
                ...publicDescriptor.resources[0],
                resource_live: true,
                provider_intent_mutation_supported: true,
                mutation_readiness: "ready",
                editable_in_principle: true,
                caller_can_mutate: true,
                operationally_requestable: false,
                grants_permission: false,
            }],
        });

        render(<MemoryRouter initialEntries={["/providers/proxmox"]}><Routes><Route path="/providers/:providerId" element={<ProviderPage />} /></Routes></MemoryRouter>);
        const selector = await screen.findByLabelText("Monitoring expectation for Frigate");
        for (let index = 0; index < 8 && selector !== document.activeElement; index += 1) {
            await user.tab();
        }
        expect(selector).toHaveFocus();
        await user.selectOptions(selector, "ignored");
        await user.tab();
        expect(screen.getByRole("checkbox")).toHaveFocus();
        await user.keyboard(" ");
        expect(screen.getByRole("checkbox")).toBeChecked();
        await user.tab();
        expect(screen.getByRole("button", { name: "Save" })).toHaveFocus();
        expect(screen.getByRole("button", { name: "Save" })).toBeEnabled();
        expect(screen.getAllByRole("button", { name: "Save" })).toHaveLength(1);
        expect(screen.getByText("Unsupported for identity-bound monitoring")).toBeInTheDocument();
        expect(within(screen.getByTestId("resource-row-lxc-110")).queryByRole("button", { name: "Save" })).not.toBeInTheDocument();
        expect(screen.queryByRole("button", { name: /Start|Restart|Remediate/i })).not.toBeInTheDocument();
    });

    it("preserves observed facts and legacy evidence when public v2 fails", async () => {
        vi.mocked(getProviderManagement).mockRejectedValue(new Error("offline"));
        render(<MemoryRouter initialEntries={["/providers/proxmox"]}><Routes><Route path="/providers/:providerId" element={<ProviderPage />} /></Routes></MemoryRouter>);
        expect(await screen.findByText("Frigate")).toBeInTheDocument();
        expect(screen.getByText("Running")).toBeInTheDocument();
        expect(screen.getByText("Monitoring unavailable", { selector: "p.font-semibold" })).toBeInTheDocument();
        expect(screen.queryByRole("button", { name: "Save" })).not.toBeInTheDocument();
        expect(screen.getByText("110: stopped")).toBeInTheDocument();
    });
});
