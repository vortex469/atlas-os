import {
    useCallback,
    useEffect,
    useRef,
    useState,
} from "react";

import { normalizeAtlasHealth } from "../utils/healthPresentation";
import { atlas } from "../api/atlas";
import { parseProviderCatalog } from "../api/providerCatalogResponse";
import { parseAceSummary } from "../api/aceSummaryResponse";
import { parsePolicies } from "../api/policiesResponse";
import { parseIntelligenceHistory } from "../api/intelligenceHistoryResponse";
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
    policiesUnavailable: boolean;
    policyHealth: PolicyReloadHealth | null;
    telemetryHistory: IntelligenceTelemetrySnapshot[];
    telemetryHistoryUnavailable: boolean;
    telemetryRetention: IntelligenceTelemetryRetentionSummary | null;
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
    const [policies, setPolicies] = useState<AtlasPolicies | null>(
        null,
    );
    const [policiesUnavailable, setPoliciesUnavailable] = useState(false);
    const [policyHealth, setPolicyHealth] =
        useState<PolicyReloadHealth | null>(null);
    const [telemetryHistory, setTelemetryHistory] = useState<
        IntelligenceTelemetrySnapshot[]
    >([]);
    const [telemetryHistoryUnavailable, setTelemetryHistoryUnavailable] = useState(false);
    const [telemetryRetention, setTelemetryRetention] =
        useState<IntelligenceTelemetryRetentionSummary | null>(null);
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
                policiesResponse,
                policyHealthResponse,
                telemetryHistoryResponse,
                telemetryRetentionResponse,
            ] = await Promise.all([
                atlas.get<unknown>("/ace/summary").then(response => ({ data: parseAceSummary(response.data) })),
                atlas.get<AtlasHealth>("/health"),
                atlas.get<unknown>("/providers").then(response => ({ data: parseProviderCatalog(response.data) })),
                atlas
                    .get<unknown>("/policies")
                    .then(response => ({ data: parsePolicies(response.data) }))
                    .catch(() => null),
                atlas.get<PolicyReloadHealth>("/policies/status"),
                atlas
                    .get<unknown>(
                        "/intelligence/telemetry/history",
                        { params: { limit: 30 } },
                    )
                    .then(response => ({ data: parseIntelligenceHistory(response.data) }))
                    .catch(() => null),
                atlas
                    .get<IntelligenceTelemetryRetentionSummary>(
                        "/intelligence/telemetry/history/retention",
                    )
                    .catch(() => null),
            ]);

            const nextProviders = sortProviders(providersResponse.data);

            setSummary(summaryResponse.data);
            setHealth(normalizeAtlasHealth(healthResponse.data));
            setProviders(nextProviders);
            setPoliciesUnavailable(policiesResponse === null);
            if (policiesResponse !== null) {
                setPolicies(policiesResponse.data);
            }
            setPolicyHealth(policyHealthResponse.data);
            setTelemetryHistoryUnavailable(telemetryHistoryResponse === null);
            if (telemetryHistoryResponse !== null) {
                setTelemetryHistory(
                    telemetryHistoryResponse.data,
                );
            }
            if (telemetryRetentionResponse !== null) {
                setTelemetryRetention(
                    telemetryRetentionResponse.data,
                );
            }
            setLastUpdated(new Date());
            setError(null);

            hasLoadedRef.current = true;
        } catch (requestError) {
            console.error(
                "Unable to refresh Mission Control:",
                requestError,
            );

            setError(
                "Could not read the latest provider details. Use Refresh to try again.",
            );
        } finally {
            requestInFlightRef.current = false;
            setIsLoading(false);
            setIsRefreshing(false);
        }
    }, []);

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
        policiesUnavailable,
        policyHealth,
        telemetryHistory,
        telemetryHistoryUnavailable,
        telemetryRetention,
        lastUpdated,
        error,
        isLoading,
        isRefreshing,
        refresh,
    };
}
