import {
    act,
    renderHook,
} from "@testing-library/react";
import {
    afterEach,
    beforeEach,
    describe,
    expect,
    it,
    vi,
} from "vitest";

import { atlas } from "../api/atlas";
import type { AceSummary } from "../types/ace";
import type { IntelligenceTelemetrySnapshot } from "../types/ace";
import type { IntelligenceTelemetryRetentionSummary } from "../types/ace";
import type { AtlasHealth } from "../types/health";
import type { Provider } from "../types/provider";
import type {
    AtlasPolicies,
    PolicyReloadHealth,
} from "../types/policies";
import { useMissionControl } from "./useMissionControl";

const summary: AceSummary = {
    score: 92,
    status: "healthy",
    summary: "Atlas is operating normally.",
    findings: [],
    assessments: [],
    recommendations: [],
    telemetry: {
        provider_collection_duration_ms: 12,
        provider_timeout_seconds: 10,
        providers: [],
    },
};

const health: AtlasHealth = {
    atlas: "healthy",
    services: {},
};

const policies: AtlasPolicies = {
    proxmox: { guests: {} },
    docker: { containers: {} },
    homeassistant: { ignored_entities: [] },
    opnsense: {
        pending_update_warning_threshold: null,
        reboot_required_severity: "warning",
    },
    frigate: {
        cameras: {},
        stalled_camera_severity: "warning",
    },
    obsidian: {
        minimum_note_count: 1,
        stale_after_days: null,
        insufficient_notes_severity: "warning",
        stale_severity: "info",
        scan_truncated_severity: "warning",
    },
    qdrant: {
        expected_collections: [],
        missing_collection_severity: "warning",
        empty_instance_severity: "info",
    },
    n8n: {
        expected_active_workflows: [],
        inactive_workflow_severity: "warning",
        scan_truncated_severity: "warning",
        empty_instance_severity: "info",
    },
    intelligence: { providers: {} },
};

const policyHealth: PolicyReloadHealth = {
    status: "healthy",
    source_exists: true,
    checked_at: "2026-07-25T19:00:00Z",
    loaded_at: "2026-07-25T19:00:00Z",
    duration_ms: 1.2,
    error: null,
    diagnostics: [],
};

const telemetryHistory: IntelligenceTelemetrySnapshot[] = [
    {
        id: "snapshot-1",
        collected_at: "2026-07-25T19:00:00Z",
        telemetry: summary.telemetry,
    },
];

const telemetryRetention: IntelligenceTelemetryRetentionSummary = {
    entry_count: 1,
    max_entries: 10000,
    retention_days: 30,
    oldest_snapshot_at: "2026-07-25T19:00:00Z",
    newest_snapshot_at: "2026-07-25T19:00:00Z",
};

function provider(
    id: string,
    name: string,
    priority: string,
    workspace: string,
): Provider {
    return {
        id,
        name,
        priority,
        workspace,
        version: "1.0.0",
        description: `${name} provider`,
        icon: "server",
        capabilities: [],
        health: {
            status: "healthy",
            latency_ms: 5,
            http_status: 200,
            message: null,
            details: {},
        },
    };
}

describe("useMissionControl", () => {
    beforeEach(() => {
        vi.useFakeTimers();
    });

    afterEach(() => {
        vi.useRealTimers();
        vi.restoreAllMocks();
    });

    it("loads dashboard state and sorts critical providers first", async () => {
        const get = vi.spyOn(atlas, "get").mockImplementation(
            async (url) => {
                if (url === "/ace/summary") {
                    return { data: summary };
                }
                if (url === "/health") {
                    return { data: health };
                }
                if (url === "/policies") {
                    return { data: policies };
                }
                if (url === "/policies/status") {
                    return { data: policyHealth };
                }
                if (url === "/intelligence/telemetry/history") {
                    return { data: telemetryHistory };
                }
                if (
                    url ===
                    "/intelligence/telemetry/history/retention"
                ) {
                    return { data: telemetryRetention };
                }

                return {
                    data: [
                        provider(
                            "ollama",
                            "Ollama",
                            "standard",
                            "ai",
                        ),
                        provider(
                            "docker",
                            "Docker",
                            "critical",
                            "infrastructure",
                        ),
                    ],
                };
            },
        );

        const { result } = renderHook(() => useMissionControl());

        await act(async () => {
            await vi.advanceTimersByTimeAsync(0);
        });

        expect(result.current.isLoading).toBe(false);
        expect(result.current.summary).toEqual(summary);
        expect(result.current.health).toEqual(health);
        expect(result.current.policies).toEqual(policies);
        expect(result.current.policyHealth).toEqual(policyHealth);
        expect(result.current.telemetryHistory).toEqual(
            telemetryHistory,
        );
        expect(result.current.telemetryRetention).toEqual(
            telemetryRetention,
        );
        expect(
            result.current.providers.map(({ id }) => id),
        ).toEqual(["docker", "ollama"]);
        expect(result.current.lastUpdated).toBeInstanceOf(Date);
        expect(get).toHaveBeenCalledTimes(7);
    });

    it("reports optional history failures without losing provider data and recovers through reads", async () => {
        let available = false;
        let history = telemetryHistory;
        vi.spyOn(atlas, "get").mockImplementation(async url => {
            if (url === "/intelligence/telemetry/history" && !available) throw new Error("history unavailable");
            const data: Record<string, unknown> = {
                "/ace/summary": summary, "/health": health,
                "/providers": [provider("proxmox", "Proxmox", "critical", "operations")],
                "/policies": policies, "/policies/status": policyHealth,
                "/intelligence/telemetry/history": history,
                "/intelligence/telemetry/history/retention": telemetryRetention,
            };
            return { data: data[url!] };
        });
        const { result } = renderHook(() => useMissionControl());
        await act(async () => { await vi.advanceTimersByTimeAsync(0); });
        expect(result.current.telemetryHistoryUnavailable).toBe(true);
        expect(result.current.error).toBeNull();
        expect(result.current.providers).toHaveLength(1);
        expect(result.current.telemetryHistory).toEqual([]);
        available = true;
        await act(async () => { await result.current.refresh(); });
        expect(result.current.telemetryHistoryUnavailable).toBe(false);
        expect(result.current.telemetryHistory).toEqual(telemetryHistory);
        available = false;
        await act(async () => { await result.current.refresh(); });
        expect(result.current.telemetryHistoryUnavailable).toBe(true);
        expect(result.current.telemetryHistory).toEqual(telemetryHistory);
        expect(result.current.error).toBeNull();
        available = true;
        history = [];
        await act(async () => { await result.current.refresh(); });
        expect(result.current.telemetryHistoryUnavailable).toBe(false);
        expect(result.current.telemetryHistory).toEqual([]);
    });

    it("reports optional policy failures while retaining settings and recovers without losing provider health", async () => {
        let available = false;
        vi.spyOn(atlas, "get").mockImplementation(async url => {
            if (url === "/policies" && !available) throw new Error("policies unavailable");
            const data: Record<string, unknown> = {
                "/ace/summary": summary, "/health": health,
                "/providers": [provider("proxmox", "Proxmox", "critical", "operations")],
                "/policies": policies, "/policies/status": policyHealth,
                "/intelligence/telemetry/history": telemetryHistory,
                "/intelligence/telemetry/history/retention": telemetryRetention,
            };
            return { data: data[url!] };
        });
        const { result } = renderHook(() => useMissionControl());
        await act(async () => { await vi.advanceTimersByTimeAsync(0); });
        expect(result.current.policiesUnavailable).toBe(true);
        expect(result.current.policies).toBeNull();
        expect(result.current.error).toBeNull();
        available = true;
        await act(async () => { await result.current.refresh(); });
        expect(result.current.policiesUnavailable).toBe(false);
        expect(result.current.policies).toEqual(policies);
        available = false;
        await act(async () => { await result.current.refresh(); });
        expect(result.current.policiesUnavailable).toBe(true);
        expect(result.current.policies).toEqual(policies);
        expect(result.current.error).toBeNull();
        available = true;
        await act(async () => { await result.current.refresh(); });
        expect(result.current.policiesUnavailable).toBe(false);
    });

    it.each([
        { name: "null", value: null },
        { name: "object", value: { items: [] } },
        { name: "invalid snapshot", value: [{ id: "bad", collected_at: "2026-02-30T12:00:00Z", telemetry: {} }] },
    ])("isolates a malformed $name history response and retains the last valid history", async ({ value }) => {
        let body: unknown = telemetryHistory;
        vi.spyOn(atlas, "get").mockImplementation(async url => {
            const data: Record<string, unknown> = {
                "/ace/summary": summary, "/health": health,
                "/providers": [provider("proxmox", "Proxmox", "critical", "operations")],
                "/policies": policies, "/policies/status": policyHealth,
                "/intelligence/telemetry/history": body,
                "/intelligence/telemetry/history/retention": telemetryRetention,
            };
            return { data: data[url!] };
        });
        const { result } = renderHook(() => useMissionControl());
        await act(async () => { await vi.advanceTimersByTimeAsync(0); });
        body = value;
        await act(async () => { await result.current.refresh(); });
        expect(result.current.telemetryHistoryUnavailable).toBe(true);
        expect(result.current.telemetryHistory).toEqual(telemetryHistory);
        expect(result.current.providers).toHaveLength(1);
        expect(result.current.error).toBeNull();
        body = [];
        await act(async () => { await result.current.refresh(); });
        expect(result.current.telemetryHistoryUnavailable).toBe(false);
        expect(result.current.telemetryHistory).toEqual([]);
    });

    it.each([
        { name: "missing sections", value: { proxmox: { guests: {} } } },
        { name: "invalid nested policy", value: { ...policies, proxmox: { guests: { "110": null } } } },
        { name: "invalid threshold", value: { ...policies, intelligence: { providers: { proxmox: { maximum_collection_duration_ms: null, severity: "warning" } } } } },
    ])("isolates $name in a successful settings response and recovers through reads", async ({ value }) => {
        let body: unknown = policies;
        vi.spyOn(atlas, "get").mockImplementation(async url => ({ data: ({
            "/ace/summary": summary, "/health": health,
            "/providers": [provider("proxmox", "Proxmox", "critical", "operations")],
            "/policies": body, "/policies/status": policyHealth,
            "/intelligence/telemetry/history": telemetryHistory,
            "/intelligence/telemetry/history/retention": telemetryRetention,
        } as Record<string, unknown>)[url!] }));
        const { result } = renderHook(() => useMissionControl());
        await act(async () => { await vi.advanceTimersByTimeAsync(0); });
        body = value;
        await act(async () => { await result.current.refresh(); });
        expect(result.current.policiesUnavailable).toBe(true);
        expect(result.current.policies).toEqual(policies);
        expect(result.current.providers).toHaveLength(1);
        expect(result.current.error).toBeNull();
        body = policies;
        await act(async () => { await result.current.refresh(); });
        expect(result.current.policiesUnavailable).toBe(false);
        expect(result.current.policies).toEqual(policies);
    });

    it.each([
        { name: "null findings", value: { ...summary, findings: null } },
        { name: "invalid finding", value: { ...summary, findings: [{ source: { private: "PRIVATE-SUMMARY-CANARY" } }] } },
        { name: "invalid recommendation", value: { ...summary, recommendations: [{ priority: null }] } },
    ])("rejects $name before publishing and retains the last coherent snapshot", async ({ value }) => {
        let body: unknown = summary;
        let healthy = true;
        vi.spyOn(console, "error").mockImplementation(() => undefined);
        vi.spyOn(atlas, "get").mockImplementation(async url => ({ data: ({
            "/ace/summary": body, "/health": health,
            "/providers": [provider("proxmox", "Proxmox", "critical", "operations")].map(p => ({ ...p, health: { ...p.health, status: healthy ? "healthy" : "offline" } })),
            "/policies": policies, "/policies/status": policyHealth,
            "/intelligence/telemetry/history": telemetryHistory,
            "/intelligence/telemetry/history/retention": telemetryRetention,
        } as Record<string, unknown>)[url!] }));
        const { result } = renderHook(() => useMissionControl());
        await act(async () => { await vi.advanceTimersByTimeAsync(0); });
        const lastUpdated = result.current.lastUpdated;
        body = value;
        healthy = false;
        await act(async () => { await result.current.refresh(); });
        expect(result.current.error).not.toBeNull();
        expect(result.current.summary).toEqual(summary);
        expect(result.current.providers[0].health.status).toBe("healthy");
        expect(result.current.lastUpdated).toEqual(lastUpdated);
        body = summary;
        await act(async () => { await result.current.refresh(); });
        expect(result.current.error).toBeNull();
        expect(result.current.providers[0].health.status).toBe("offline");
    });

    it.each([
        { name: "invalid capabilities", value: [{ ...provider("proxmox", "Proxmox", "critical", "operations"), capabilities: null }] },
        { name: "invalid name", value: [{ ...provider("proxmox", "Proxmox", "critical", "operations"), name: { private: "PRIVATE-CATALOG-CANARY" } }] },
        { name: "duplicate identities", value: [provider("proxmox", "Proxmox", "critical", "operations"), provider("proxmox", "Duplicate", "critical", "operations")] },
    ])("rejects $name before replacing the coherent provider snapshot", async ({ value }) => {
        const valid = [provider("proxmox", "Proxmox", "critical", "operations")];
        let body: unknown = valid;
        vi.spyOn(console, "error").mockImplementation(() => undefined);
        vi.spyOn(atlas, "get").mockImplementation(async url => ({ data: ({
            "/ace/summary": summary, "/health": health, "/providers": body,
            "/policies": policies, "/policies/status": policyHealth,
            "/intelligence/telemetry/history": telemetryHistory,
            "/intelligence/telemetry/history/retention": telemetryRetention,
        } as Record<string, unknown>)[url!] }));
        const { result } = renderHook(() => useMissionControl());
        await act(async () => { await vi.advanceTimersByTimeAsync(0); });
        const lastUpdated = result.current.lastUpdated;
        body = value;
        await act(async () => { await result.current.refresh(); });
        expect(result.current.error).not.toBeNull();
        expect(result.current.providers).toEqual(valid);
        expect(result.current.lastUpdated).toEqual(lastUpdated);
        body = [];
        await act(async () => { await result.current.refresh(); });
        expect(result.current.error).toBeNull();
        expect(result.current.providers).toEqual([]);
    });

    it("normalizes malformed health API data before publishing dashboard state", async () => {
        vi.spyOn(atlas, "get").mockImplementation(async (url) => {
            const data: Record<string, unknown> = {
                "/ace/summary": summary,
                "/health": { atlas: {}, services: { broken: null } },
                "/providers": [{ ...provider("docker", "Docker", "critical", "infrastructure"), health: null }],
                "/policies": policies,
                "/policies/status": policyHealth,
                "/intelligence/telemetry/history": [],
                "/intelligence/telemetry/history/retention": telemetryRetention,
            };
            return { data: data[url!] };
        });
        const { result } = renderHook(() => useMissionControl());
        await act(async () => { await vi.advanceTimersByTimeAsync(0); });
        expect(result.current.health?.atlas).toBe("unknown");
        expect(result.current.health?.services.broken.status).toBe("unknown");
        expect(result.current.providers[0].health.status).toBe("unknown");
        expect(result.current.providers[0].health.http_status).toBeNull();
    });

    it("preserves current data when a manual refresh fails", async () => {
        const get = vi
            .spyOn(atlas, "get")
            .mockImplementation(async (url) => {
                if (url === "/ace/summary") {
                    return { data: summary };
                }
                if (url === "/health") {
                    return { data: health };
                }
                if (url === "/policies") {
                    return { data: policies };
                }
                if (url === "/policies/status") {
                    return { data: policyHealth };
                }
                if (url === "/intelligence/telemetry/history") {
                    return { data: telemetryHistory };
                }
                if (
                    url ===
                    "/intelligence/telemetry/history/retention"
                ) {
                    return { data: telemetryRetention };
                }

                return { data: [] };
            });
        vi.spyOn(console, "error").mockImplementation(
            () => undefined,
        );

        const { result } = renderHook(() => useMissionControl());
        await act(async () => {
            await vi.advanceTimersByTimeAsync(0);
        });
        const firstUpdatedAt = result.current.lastUpdated;

        get.mockRejectedValue(new Error("Atlas unavailable"));
        await act(async () => {
            await result.current.refresh();
        });

        expect(result.current.summary).toEqual(summary);
        expect(result.current.lastUpdated).toBe(firstUpdatedAt);
        expect(result.current.isRefreshing).toBe(false);
        expect(result.current.error).toBe(
            "Mission Control could not retrieve the latest state from Atlas Core.",
        );

        expect(get).toHaveBeenCalledTimes(14);
    });

    it("keeps dashboard data available when policy reload fails", async () => {
        const degradedHealth: PolicyReloadHealth = {
            status: "degraded",
            source_exists: true,
            checked_at: "2026-07-25T19:05:00Z",
            loaded_at: null,
            duration_ms: 0.5,
            error: "Atlas policy reload failed.",
            diagnostics: [
                {
                    path: "qdrant.expected_collections",
                    error_type: "value_error",
                    message: "Duplicate collection name.",
                    line: null,
                    column: null,
                },
            ],
        };
        vi.spyOn(atlas, "get").mockImplementation(async (url) => {
            if (url === "/ace/summary") {
                return { data: summary };
            }
            if (url === "/health") {
                return { data: health };
            }
            if (url === "/providers") {
                return { data: [] };
            }
            if (url === "/policies/status") {
                return { data: degradedHealth };
            }
            if (url === "/intelligence/telemetry/history") {
                return { data: [] };
            }
            if (
                url ===
                "/intelligence/telemetry/history/retention"
            ) {
                return { data: telemetryRetention };
            }

            throw new Error("Invalid policy file");
        });

        const { result } = renderHook(() => useMissionControl());
        await act(async () => {
            await vi.advanceTimersByTimeAsync(0);
        });

        expect(result.current.summary).toEqual(summary);
        expect(result.current.policies).toBeNull();
        expect(result.current.policyHealth).toEqual(
            degradedHealth,
        );
        expect(result.current.error).toBeNull();
    });
});
