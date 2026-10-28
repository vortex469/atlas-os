import { beforeEach, describe, expect, it, vi } from "vitest";

const { mockGet } = vi.hoisted(() => ({ mockGet: vi.fn() }));

vi.mock("axios", () => ({
    default: { create: () => ({ get: mockGet, post: vi.fn() }) },
}));

import {
    getProviderActionHistory,
    getProviderActionHistoryEntry,
    getProviderActionHistoryProviders,
    getProviderActionHistorySummary,
} from "./atlas";

function entry(overrides: Record<string, unknown> = {}) {
    return {
        id: "audit-1",
        provider_id: "proxmox",
        provider_name: "Proxmox",
        action_id: "restart-service",
        action_label: "Restart service",
        status: "succeeded",
        success: true,
        message: "The service restarted.",
        confirmed: true,
        destructive: true,
        parameter_names: ["resource_id"],
        request_id: "request-1",
        started_at: "2026-10-25T15:00:00Z",
        completed_at: "2026-10-25T15:00:01Z",
        duration_ms: 1000,
        ...overrides,
    };
}

describe("Atlas Core action history responses", () => {
    beforeEach(() => mockGet.mockReset());

    it("accepts valid history pages, entries, and retention summaries", async () => {
        const historyPage = { items: [entry()], total: 1, offset: 0, limit: 25, has_more: false };
        const summary = {
            entry_count: 1,
            max_entries: 5000,
            retention_days: 90,
            oldest_entry_at: "2026-10-25T15:00:01Z",
            newest_entry_at: "2026-10-25T15:00:01Z",
        };
        mockGet
            .mockResolvedValueOnce({ data: historyPage })
            .mockResolvedValueOnce({ data: entry() })
            .mockResolvedValueOnce({ data: summary });

        await expect(getProviderActionHistory()).resolves.toEqual(historyPage);
        await expect(getProviderActionHistoryEntry("audit-1")).resolves.toEqual(entry());
        await expect(getProviderActionHistorySummary()).resolves.toEqual(summary);
    });

    it("rejects malformed and duplicate history rows before display", async () => {
        mockGet
            .mockResolvedValueOnce({ data: { items: [null], total: 1, offset: 0, limit: 25, has_more: false } })
            .mockResolvedValueOnce({ data: { items: [entry(), entry()], total: 2, offset: 0, limit: 25, has_more: false } })
            .mockResolvedValueOnce({ data: entry({ duration_ms: -1 }) });

        await expect(getProviderActionHistory()).rejects.toThrow("Malformed provider action history entry payload.");
        await expect(getProviderActionHistory()).rejects.toThrow("Malformed provider action history page payload.");
        await expect(getProviderActionHistoryEntry("audit-1")).rejects.toThrow("Malformed provider action history entry payload.");
    });

    it("rejects an invalid retention period before it can enable deletion", async () => {
        mockGet.mockResolvedValueOnce({ data: {
            entry_count: 1,
            max_entries: 5000,
            retention_days: 0,
            oldest_entry_at: null,
            newest_entry_at: null,
        } });

        await expect(getProviderActionHistorySummary()).rejects.toThrow("Malformed provider action history summary payload.");
    });

    it("rejects malformed provider filter options", async () => {
        mockGet.mockResolvedValueOnce({ data: [{ id: "proxmox", name: "Proxmox" }, null] });

        await expect(getProviderActionHistoryProviders()).rejects.toThrow("Malformed provider action history providers payload.");
    });
});
