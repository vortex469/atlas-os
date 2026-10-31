import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { useMissionControl } from "../hooks/useMissionControl";
import { ProviderPage } from "./ProviderPage";

vi.mock("../hooks/useMissionControl", () => ({ useMissionControl: vi.fn() }));
vi.mock("../components/ProviderOverview", () => ({ ProviderOverview: ({ stale }: { stale?: boolean }) => <section><h2>Provider overview</h2>{stale && <p>Last known provider status</p>}</section> }));
vi.mock("../components/ProviderResources", () => ({ ProviderResources: () => <section><h2>Resources and monitoring</h2></section> }));
vi.mock("../components/ProviderActions", () => ({ ProviderActions: () => <section><h2>Direct provider actions</h2></section> }));
vi.mock("../components/ProviderConnection", () => ({ ProviderConnection: () => <section><h2>Connection</h2></section> }));
vi.mock("../components/ProviderTelemetryTrend", () => ({ ProviderTelemetryTrend: ({ performancePolicyStale }: { performancePolicyStale?: boolean }) => <section><h2>Telemetry</h2>{performancePolicyStale && <p>Last known performance limit</p>}</section> }));
vi.mock("../components/ProviderPolicyDetails", () => ({ ProviderPolicyDetails: ({ stale }: { stale?: boolean }) => <section><h2>Older VM settings</h2>{stale && <p>Last known policy settings</p>}</section> }));

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

    it("labels the initial provider-data load without implying a connectivity check", () => {
        vi.mocked(useMissionControl).mockReturnValue(providerPageState(["resources", "connection"], {
            isLoading: true,
            lastUpdated: null,
            providers: [],
        }));
        render(<MemoryRouter initialEntries={["/providers/proxmox"]}><Routes><Route path="/providers/:providerId" element={<ProviderPage />} /></Routes></MemoryRouter>);

        expect(screen.getByRole("status")).toHaveTextContent("Loading provider details…");
        expect(screen.getByRole("button", { name: "Refresh" })).toBeDisabled();
        expect(screen.queryByText("Live", { exact: true })).not.toBeInTheDocument();
        expect(screen.queryByText("Last checked (local time)", { exact: true })).not.toBeInTheDocument();
        expect(screen.queryByText("Connecting...", { exact: true })).not.toBeInTheDocument();
    });

    it.each([
        { isLoading: true, isRefreshing: false, disabled: true, indicator: null },
        { isLoading: false, isRefreshing: true, disabled: true, indicator: "Refreshing" },
        { isLoading: false, isRefreshing: false, disabled: false, indicator: null },
    ])("shows one clear provider refresh state: %j", (state) => {
        vi.mocked(useMissionControl).mockReturnValue(providerPageState(["resources", "connection"], state));
        render(<MemoryRouter initialEntries={["/providers/proxmox"]}><Routes><Route path="/providers/:providerId" element={<ProviderPage />} /></Routes></MemoryRouter>);

        const button = screen.getByRole("button", { name: "Refresh" }) as HTMLButtonElement;
        expect(button.disabled).toBe(state.disabled);
        if (state.indicator) expect(screen.getByText(state.indicator, { exact: true })).toBeInTheDocument();
        else expect(screen.queryByText("Live", { exact: true })).not.toBeInTheDocument();
        expect(screen.queryByRole("button", { name: "Loading…" })).not.toBeInTheDocument();
        expect(screen.queryByRole("button", { name: "Refreshing…" })).not.toBeInTheDocument();
    });

    it("explains an empty provider catalog instead of leaving the detail screen blank", () => {
        vi.mocked(useMissionControl).mockReturnValue(providerPageState(undefined, { providers: [] }));
        render(<MemoryRouter initialEntries={["/providers/proxmox"]}><Routes><Route path="/providers/:providerId" element={<ProviderPage />} /></Routes></MemoryRouter>);
        expect(screen.getByRole("heading", { name: "Provider not found" })).toBeInTheDocument();
        expect(screen.getByText("Atlas doesn't list this provider right now.")).toBeInTheDocument();
        expect(screen.getByRole("link", { name: "← All providers" })).toHaveAttribute("href", "/providers");
        expect(screen.queryByText(/Refresh to check again/)).not.toBeInTheDocument();
    });

    it("keeps provider details usable when supported-feature data is missing", () => {
        vi.mocked(useMissionControl).mockReturnValue(providerPageState(undefined));
        render(<MemoryRouter initialEntries={["/providers/proxmox"]}><Routes><Route path="/providers/:providerId" element={<ProviderPage />} /></Routes></MemoryRouter>);
        expect(screen.queryByRole("status")).not.toBeInTheDocument();
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
        if (state.isLoading) {
            expect(screen.getByRole("status")).toHaveTextContent("Loading provider details…");
        } else {
            expect(screen.getByText("Some information could not be refreshed")).toBeInTheDocument();
        }
    });

    it("keeps provider details visible when the diagnostics source is unavailable", () => {
        vi.mocked(useMissionControl).mockReturnValue(providerPageState(["resources", "connection"], {
            summary: null,
            error: "Some provider information could not be refreshed. Existing information may be out of date.",
            failedSources: ["provider catalog", "diagnostics"],
            providerCatalogUnavailable: true,
            summaryUnavailable: true,
        }));
        render(<MemoryRouter initialEntries={["/providers/proxmox"]}><Routes><Route path="/providers/:providerId" element={<ProviderPage />} /></Routes></MemoryRouter>);

        expect(screen.getByRole("heading", { name: "Provider overview" })).toBeInTheDocument();
        expect(screen.getByText("Last known provider status")).toBeInTheDocument();
        expect(screen.getByText("Some information could not be refreshed")).toBeInTheDocument();
        expect(screen.getByText("Some information may be out of date. Use Refresh above to check again.")).toBeInTheDocument();
        const technicalDetails = screen.getByText("Technical details").closest("details");
        expect(technicalDetails).not.toHaveAttribute("open");
        expect(screen.getByText("Unavailable: provider catalog, diagnostics.")).not.toBeVisible();
        fireEvent.click(screen.getByText("Technical details"));
        expect(screen.getByText("Unavailable: provider catalog, diagnostics.")).toBeVisible();
        expect(screen.getByText("Diagnostics could not be loaded.")).toBeInTheDocument();
        expect(screen.getByText("Recommendations could not be loaded.")).toBeInTheDocument();
        expect(screen.queryByText("No messages about this provider right now.")).not.toBeInTheDocument();
        expect(screen.queryByText("No recommendations for this provider right now.")).not.toBeInTheDocument();
    });

    it("marks cached empty diagnostics and recommendations as last known", () => {
        vi.mocked(useMissionControl).mockReturnValue(providerPageState(["resources", "connection"], {
            summary: { findings: [], recommendations: [] },
            error: "Some provider information could not be refreshed. Existing information may be out of date.",
            failedSources: ["diagnostics"],
            summaryUnavailable: true,
        }));
        render(<MemoryRouter initialEntries={["/providers/proxmox"]}><Routes><Route path="/providers/:providerId" element={<ProviderPage />} /></Routes></MemoryRouter>);

        expect(screen.getByRole("status")).toHaveTextContent("Diagnostics and recommendations show the last available report. Atlas could not confirm current results.");
        expect(screen.getByText("The last available report had no messages about this provider.")).toBeInTheDocument();
        expect(screen.getByText("The last available report had no recommendations for this provider.")).toBeInTheDocument();
        expect(screen.queryByText("No messages about this provider right now.")).not.toBeInTheDocument();
        expect(screen.queryByText("No recommendations for this provider right now.")).not.toBeInTheDocument();
    });

    it("marks cached monitoring settings and limits after a policy refresh failure", () => {
        const policies = providerPageState(["resources", "connection"]).policies!;
        vi.mocked(useMissionControl).mockReturnValue(providerPageState(["resources", "connection"], {
            policies: {
                ...policies,
                intelligence: { providers: { proxmox: { maximum_collection_duration_ms: 250, severity: "critical" } } },
            },
            error: "Some provider information could not be refreshed. Existing information may be out of date.",
            failedSources: ["monitoring policies"],
        }));
        render(<MemoryRouter initialEntries={["/providers/proxmox"]}><Routes><Route path="/providers/:providerId" element={<ProviderPage />} /></Routes></MemoryRouter>);

        expect(screen.getByText("Last known policy settings")).toBeInTheDocument();
        expect(screen.getByText("Last known performance limit")).toBeInTheDocument();
    });

    it("explains when current policy settings could not be loaded", () => {
        vi.mocked(useMissionControl).mockReturnValue(providerPageState(["resources", "connection"], {
            policies: null,
            error: "Some provider information could not be refreshed. Existing information may be out of date.",
            failedSources: ["monitoring policies"],
        }));
        render(<MemoryRouter initialEntries={["/providers/proxmox"]}><Routes><Route path="/providers/:providerId" element={<ProviderPage />} /></Routes></MemoryRouter>);

        expect(screen.getByRole("status")).toHaveTextContent("Current monitoring settings could not be loaded. Refresh to try again.");
    });

    it("does not call a provider missing when the provider catalog could not be checked", () => {
        vi.mocked(useMissionControl).mockReturnValue(providerPageState(undefined, {
            providers: [],
            error: "Some provider information could not be refreshed. Existing information may be out of date.",
            failedSources: ["provider catalog"],
            providerCatalogUnavailable: true,
        }));
        render(<MemoryRouter initialEntries={["/providers/proxmox"]}><Routes><Route path="/providers/:providerId" element={<ProviderPage />} /></Routes></MemoryRouter>);

        expect(screen.getByText("Atlas couldn't check whether this provider is listed.")).toBeInTheDocument();
        expect(screen.queryByRole("heading", { name: "Provider not found" })).not.toBeInTheDocument();
    });

    it("shows one provider-specific stale notice when the catalog refresh fails", () => {
        vi.mocked(useMissionControl).mockReturnValue(providerPageState(["resources", "connection"], {
            error: "Some provider information could not be refreshed. Existing information may be out of date.",
            failedSources: ["provider catalog"],
            providerCatalogUnavailable: true,
        }));
        render(<MemoryRouter initialEntries={["/providers/proxmox"]}><Routes><Route path="/providers/:providerId" element={<ProviderPage />} /></Routes></MemoryRouter>);

        expect(screen.getByText("Last known provider status")).toBeInTheDocument();
        expect(screen.queryByRole("alert")).not.toBeInTheDocument();
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

    it("labels the last provider data refresh as local time and preserves its UTC instant", () => {
        const lastUpdated = new Date("2026-10-29T07:00:00.000Z");
        vi.mocked(useMissionControl).mockReturnValue(providerPageState(["resources", "connection"], { lastUpdated }));
        render(<MemoryRouter initialEntries={["/providers/proxmox"]}><Routes><Route path="/providers/:providerId" element={<ProviderPage />} /></Routes></MemoryRouter>);

        expect(screen.getByText("Last checked (local time)")).toBeInTheDocument();
        const time = screen.getByText(lastUpdated.toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" }));
        expect(time.tagName).toBe("TIME");
        expect(time).toHaveAttribute("datetime", lastUpdated.toISOString());
    });
});
