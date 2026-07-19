import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { atlas } from "../api/atlas";
import type { AceSummary } from "../types/ace";
import type { AtlasHealth, ServiceHealth } from "../types/health";

const REFRESH_INTERVAL_MS = 30_000;

export type ServiceEntry = [string, ServiceHealth];

type MissionControlState = {
    summary: AceSummary | null;
    health: AtlasHealth | null;
    services: ServiceEntry[];
    lastUpdated: Date | null;
    error: string | null;
    isLoading: boolean;
    isRefreshing: boolean;
    refresh: () => Promise<void>;
};

export function useMissionControl(): MissionControlState {
    const [summary, setSummary] = useState<AceSummary | null>(null);
    const [health, setHealth] = useState<AtlasHealth | null>(null);
    const [lastUpdated, setLastUpdated] = useState<Date | null>(null);
    const [error, setError] = useState<string | null>(null);
    const [isLoading, setIsLoading] = useState(true);
    const [isRefreshing, setIsRefreshing] = useState(false);

    const hasLoadedRef = useRef(false);
    const requestInFlightRef = useRef(false);

    const refresh = useCallback(async () => {
        if (requestInFlightRef.current) {
            return;
        }

        requestInFlightRef.current = true;

        if (hasLoadedRef.current) {
            setIsRefreshing(true);
        } else {
            setIsLoading(true);
        }

        try {
            const [summaryResponse, healthResponse] = await Promise.all([
                atlas.get<AceSummary>("/ace/summary"),
                atlas.get<AtlasHealth>("/health"),
            ]);

            setSummary(summaryResponse.data);
            setHealth(healthResponse.data);
            setLastUpdated(new Date());
            setError(null);

            hasLoadedRef.current = true;
        } catch (requestError) {
            console.error("Unable to refresh Mission Control:", requestError);

            setError(
                "Mission Control could not retrieve the latest state from Atlas Core.",
            );
        } finally {
            requestInFlightRef.current = false;
            setIsLoading(false);
            setIsRefreshing(false);
        }
    }, []);

    useEffect(() => {
        void refresh();

        const intervalId = window.setInterval(() => {
            void refresh();
        }, REFRESH_INTERVAL_MS);

        return () => {
            window.clearInterval(intervalId);
        };
    }, [refresh]);

    const services = useMemo<ServiceEntry[]>(() => {
        if (!health) {
            return [];
        }

        return Object.entries(health.services).sort(
            ([firstName, first], [secondName, second]) => {
                if (first.critical !== second.critical) {
                    return first.critical ? -1 : 1;
                }

                return firstName.localeCompare(secondName);
            },
        );
    }, [health]);

    return {
        summary,
        health,
        services,
        lastUpdated,
        error,
        isLoading,
        isRefreshing,
        refresh,
    };
}
