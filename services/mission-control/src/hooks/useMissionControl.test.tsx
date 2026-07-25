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
import type { AtlasHealth } from "../types/health";
import type { Provider } from "../types/provider";
import { useMissionControl } from "./useMissionControl";

const summary: AceSummary = {
    score: 92,
    status: "healthy",
    summary: "Atlas is operating normally.",
    findings: [],
    assessments: [],
    recommendations: [],
};

const health: AtlasHealth = {
    atlas: "healthy",
    services: {},
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
        expect(
            result.current.providers.map(({ id }) => id),
        ).toEqual(["docker", "ollama"]);
        expect(result.current.lastUpdated).toBeInstanceOf(Date);
        expect(get).toHaveBeenCalledTimes(3);
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

        expect(get).toHaveBeenCalledTimes(6);
    });
});
