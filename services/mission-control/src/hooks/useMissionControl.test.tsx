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
        expect(result.current.failedSources).toEqual([]);
        expect(result.current.providerCatalogUnavailable).toBe(false);
        expect(result.current.summaryUnavailable).toBe(false);
        expect(result.current.telemetryHistoryUnavailable).toBe(false);
        let refreshSucceeded = false;
        await act(async () => { refreshSucceeded = await result.current.refresh(); });
        expect(refreshSucceeded).toBe(true);
        expect(get).toHaveBeenCalledTimes(14);
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

    it("does not treat a malformed provider catalog as an empty catalog", async () => {
        vi.spyOn(atlas, "get").mockImplementation(async (url) => {
            const data: Record<string, unknown> = {
                "/ace/summary": summary,
                "/health": health,
                "/providers": [null],
                "/policies": policies,
                "/policies/status": policyHealth,
                "/intelligence/telemetry/history": [],
                "/intelligence/telemetry/history/retention": telemetryRetention,
            };
            return { data: data[url!] };
        });

        const { result } = renderHook(() => useMissionControl());
        await act(async () => { await vi.advanceTimersByTimeAsync(0); });

        expect(result.current.providers).toEqual([]);
        expect(result.current.providerCatalogUnavailable).toBe(true);
        expect(result.current.failedSources).toContain("provider catalog");
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
        let refreshResults: boolean[] = [];
        await act(async () => {
            refreshResults = await Promise.all([
                result.current.refresh(),
                result.current.refresh(),
            ]);
        });

        expect(refreshResults).toEqual([false, false]);
        expect(result.current.summary).toEqual(summary);
        expect(result.current.lastUpdated).toBe(firstUpdatedAt);
        expect(result.current.isRefreshing).toBe(false);
        expect(result.current.error).toBe(
            "Some provider information could not be refreshed. Existing information may be out of date.",
        );
        expect(result.current.failedSources).toEqual([
            "diagnostics", "health status", "provider catalog", "monitoring policies",
            "policy status", "provider check history", "history retention details",
        ]);

        expect(get).toHaveBeenCalledTimes(14);
    });

    it("keeps provider data available when an unrelated diagnostics read fails", async () => {
        vi.spyOn(atlas, "get").mockImplementation(async (url) => {
            if (url === "/ace/summary") throw new Error("Diagnostics unavailable");
            if (url === "/health") return { data: health };
            if (url === "/providers") return { data: [provider("docker", "Docker", "critical", "infrastructure")] };
            if (url === "/policies") return { data: policies };
            if (url === "/policies/status") return { data: policyHealth };
            if (url === "/intelligence/telemetry/history") return { data: telemetryHistory };
            return { data: telemetryRetention };
        });

        const { result } = renderHook(() => useMissionControl());
        await act(async () => { await vi.advanceTimersByTimeAsync(0); });

        let refreshConfirmed = true;
        await act(async () => { refreshConfirmed = await result.current.refresh(); });

        expect(refreshConfirmed).toBe(false);
        expect(result.current.summary).toBeNull();
        expect(result.current.providers.map(({ id }) => id)).toEqual(["docker"]);
        expect(result.current.error).toBe("Some provider information could not be refreshed. Existing information may be out of date.");
        expect(result.current.failedSources).toEqual(["diagnostics"]);
        expect(result.current.summaryUnavailable).toBe(true);
        expect(result.current.providerCatalogUnavailable).toBe(false);
        expect(result.current.isLoading).toBe(false);
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
        expect(result.current.error).toBe("Some provider information could not be refreshed. Existing information may be out of date.");
        expect(result.current.failedSources).toEqual(["monitoring policies"]);
    });
});
