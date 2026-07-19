import {
    useCallback,
    useEffect,
    useRef,
    useState,
} from "react";

import { atlas } from "../api/atlas";
import type { AceSummary } from "../types/ace";
import type { AtlasHealth } from "../types/health";
import type { Provider } from "../types/provider";

const REFRESH_INTERVAL_MS = 30_000;

type MissionControlState = {
    summary: AceSummary | null;
    health: AtlasHealth | null;
    providers: Provider[];
    lastUpdated: Date | null;
    error: string | null;
    isLoading: boolean;
    isRefreshing: boolean;
    refresh: () => Promise<void>;
};

function sortProviders(providers: Provider[]): Provider[] {
    return [...providers].sort((first, second) => {
        const firstCritical = first.priority === "critical";
        const secondCritical = second.priority === "critical";

        if (firstCritical !== secondCritical) {
            return firstCritical ? -1 : 1;
        }

        const workspaceOrder = first.workspace.localeCompare(
            second.workspace,
        );

        if (workspaceOrder !== 0) {
            return workspaceOrder;
        }

        return first.name.localeCompare(second.name);
    });
}

export function useMissionControl(): MissionControlState {
    const [summary, setSummary] = useState<AceSummary | null>(null);
    const [health, setHealth] = useState<AtlasHealth | null>(null);
    const [providers, setProviders] = useState<Provider[]>([]);
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
            const [
                summaryResponse,
                healthResponse,
                providersResponse,
            ] = await Promise.all([
                atlas.get<AceSummary>("/ace/summary"),
                atlas.get<AtlasHealth>("/health"),
                atlas.get<Provider[]>("/providers"),
            ]);

            setSummary(summaryResponse.data);
            setHealth(healthResponse.data);
            setProviders(sortProviders(providersResponse.data));
            setLastUpdated(new Date());
            setError(null);

            hasLoadedRef.current = true;
        } catch (requestError) {
            console.error(
                "Unable to refresh Mission Control:",
                requestError,
            );

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

    return {
        summary,
        health,
        providers,
        lastUpdated,
        error,
        isLoading,
        isRefreshing,
        refresh,
    };
}
