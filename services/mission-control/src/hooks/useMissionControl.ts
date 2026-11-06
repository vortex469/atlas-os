import {
    useCallback,
    useEffect,
    useRef,
    useState,
} from "react";

import { normalizeAtlasHealth, normalizeServiceHealth } from "../utils/healthPresentation";
import { atlas } from "../api/atlas";
import type {
    AceSummary,
    IntelligenceTelemetrySnapshot,
    IntelligenceTelemetryRetentionSummary,
} from "../types/ace";
import type { AtlasHealth } from "../types/health";
import type { Provider } from "../types/provider";
import type {
    AtlasPolicies,
    PolicyReloadHealth,
} from "../types/policies";

const REFRESH_INTERVAL_MS = 30_000;

type MissionControlState = {
    summary: AceSummary | null;
    health: AtlasHealth | null;
    providers: Provider[];
    policies: AtlasPolicies | null;
    policyHealth: PolicyReloadHealth | null;
    telemetryHistory: IntelligenceTelemetrySnapshot[];
    telemetryRetention: IntelligenceTelemetryRetentionSummary | null;
    lastUpdated: Date | null;
    error: string | null;
    failedSources: string[];
    providerCatalogUnavailable: boolean;
    summaryUnavailable: boolean;
    telemetryHistoryUnavailable: boolean;
    isLoading: boolean;
    isRefreshing: boolean;
    refresh: () => Promise<boolean>;
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
    const [policies, setPolicies] = useState<AtlasPolicies | null>(
        null,
    );
    const [policyHealth, setPolicyHealth] =
        useState<PolicyReloadHealth | null>(null);
    const [telemetryHistory, setTelemetryHistory] = useState<
        IntelligenceTelemetrySnapshot[]
    >([]);
    const [telemetryRetention, setTelemetryRetention] =
        useState<IntelligenceTelemetryRetentionSummary | null>(null);
    const [lastUpdated, setLastUpdated] = useState<Date | null>(null);
    const [error, setError] = useState<string | null>(null);
    const [failedSources, setFailedSources] = useState<string[]>([]);
    const [providerCatalogUnavailable, setProviderCatalogUnavailable] = useState(false);
    const [summaryUnavailable, setSummaryUnavailable] = useState(false);
    const [telemetryHistoryUnavailable, setTelemetryHistoryUnavailable] = useState(false);
    const [isLoading, setIsLoading] = useState(true);
    const [isRefreshing, setIsRefreshing] = useState(false);

    const hasLoadedRef = useRef(false);
    const refreshPromiseRef = useRef<Promise<boolean> | null>(null);

    const performRefresh = useCallback(async () => {
        if (hasLoadedRef.current) {
            setIsRefreshing(true);
        } else {
            setIsLoading(true);
        }

        try {
            const [
                summaryResult,
                healthResult,
                providersResult,
                policiesResult,
                policyHealthResult,
                telemetryHistoryResult,
                telemetryRetentionResult,
            ] = await Promise.allSettled([
                atlas.get<AceSummary>("/ace/summary"),
                atlas.get<AtlasHealth>("/health"),
                atlas.get<Provider[]>("/providers"),
                atlas.get<AtlasPolicies>("/policies"),
                atlas.get<PolicyReloadHealth>("/policies/status"),
                atlas.get<IntelligenceTelemetrySnapshot[]>(
                    "/intelligence/telemetry/history",
                    { params: { limit: 30 } },
                ),
                atlas.get<IntelligenceTelemetryRetentionSummary>(
                    "/intelligence/telemetry/history/retention",
                ),
            ]);

            const failed: string[] = [];
            let requiredReadFailed = false;

            if (summaryResult.status === "fulfilled") {
                setSummary(summaryResult.value.data);
                setSummaryUnavailable(false);
            } else {
                failed.push("diagnostics");
                requiredReadFailed = true;
                setSummaryUnavailable(true);
            }

            if (healthResult.status === "fulfilled") {
                setHealth(normalizeAtlasHealth(healthResult.value.data));
            } else {
                failed.push("health status");
                requiredReadFailed = true;
            }

            let providerCatalogFailed = false;
            if (providersResult.status === "fulfilled" && Array.isArray(providersResult.value.data)) {
                try {
                    const nextProviders = sortProviders(providersResult.value.data.map((provider) => ({
                        ...provider, health: normalizeServiceHealth(provider.health),
                    })));
                    setProviders(nextProviders);
                } catch {
                    providerCatalogFailed = true;
                }
            } else {
                providerCatalogFailed = true;
            }
            if (providerCatalogFailed) {
                failed.push("provider catalog");
                requiredReadFailed = true;
            }
            setProviderCatalogUnavailable(providerCatalogFailed);

            if (policiesResult.status === "fulfilled") {
                setPolicies(policiesResult.value.data);
            } else {
                failed.push("monitoring policies");
            }

            if (policyHealthResult.status === "fulfilled") {
                setPolicyHealth(policyHealthResult.value.data);
            } else {
                failed.push("policy status");
                requiredReadFailed = true;
            }

            if (telemetryHistoryResult.status === "fulfilled") {
                setTelemetryHistory(telemetryHistoryResult.value.data);
                setTelemetryHistoryUnavailable(false);
            } else {
                failed.push("provider check history");
                setTelemetryHistoryUnavailable(true);
            }

            if (telemetryRetentionResult.status === "fulfilled") {
                setTelemetryRetention(telemetryRetentionResult.value.data);
            } else {
                failed.push("history retention details");
            }

            setFailedSources(failed);
            setError(failed.length > 0
                ? "Some provider information could not be refreshed. Existing information may be out of date."
                : null);
            if (!requiredReadFailed) setLastUpdated(new Date());
            hasLoadedRef.current = true;
            return failed.length === 0;
        } catch (requestError) {
            console.error(
                "Unable to refresh Mission Control:",
                requestError,
            );

            setError(
                "Mission Control could not retrieve the latest state from Atlas Core.",
            );
            return false;
        } finally {
            setIsLoading(false);
            setIsRefreshing(false);
        }
    }, []);

    const refresh = useCallback((): Promise<boolean> => {
        if (refreshPromiseRef.current) return refreshPromiseRef.current;

        const request = performRefresh();
        refreshPromiseRef.current = request;
        void request.then(() => {
            if (refreshPromiseRef.current === request) refreshPromiseRef.current = null;
        });
        return request;
    }, [performRefresh]);

    useEffect(() => {
        const initialRefreshId = window.setTimeout(() => {
            void refresh();
        }, 0);

        const intervalId = window.setInterval(() => {
            void refresh();
        }, REFRESH_INTERVAL_MS);

        return () => {
            window.clearTimeout(initialRefreshId);
            window.clearInterval(intervalId);
        };
    }, [refresh]);

    return {
        summary,
        health,
        providers,
        policies,
        policyHealth,
        telemetryHistory,
        telemetryRetention,
        lastUpdated,
        error,
        failedSources,
        providerCatalogUnavailable,
        summaryUnavailable,
        telemetryHistoryUnavailable,
        isLoading,
        isRefreshing,
        refresh,
    };
}
