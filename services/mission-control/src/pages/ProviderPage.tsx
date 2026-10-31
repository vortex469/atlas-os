import { Link, useParams } from "react-router-dom";

import { FindingCard } from "../components/FindingCard";
import { ProviderActions } from "../components/ProviderActions";
import { ProviderConnection } from "../components/ProviderConnection";
import { ProviderOverview } from "../components/ProviderOverview";
import { ProviderPolicyDetails } from "../components/ProviderPolicyDetails";
import { ProviderResources } from "../components/ProviderResources";
import { ProviderTelemetryTrend } from "../components/ProviderTelemetryTrend";
import { RecommendationCard } from "../components/RecommendationCard";
import { RefreshIndicator } from "../components/RefreshIndicator";
import { SectionHeader } from "../components/SectionHeader";
import { useMissionControl } from "../hooks/useMissionControl";
import {
    createProviderId,
    formatProviderId,
    providerValuesMatch,
} from "../utils/providers";

export function ProviderPage() {
    const { providerId = "" } = useParams<{
        providerId: string;
    }>();

    const {
        summary,
        providers,
        policies,
        telemetryHistory,
        lastUpdated,
        error,
        failedSources = [],
        providerCatalogUnavailable = false,
        summaryUnavailable = false,
        telemetryHistoryUnavailable = false,
        isLoading,
        isRefreshing,
        refresh,
    } = useMissionControl();

    const provider = providers.find(
        (candidate) => candidate.id === providerId,
    );
    const capabilities = Array.isArray(provider?.capabilities)
        ? provider.capabilities
        : null;

    const providerName =
        provider?.name ?? formatProviderId(providerId);
    const policiesUnavailable = failedSources.includes("monitoring policies");

    const relatedFindings =
        summary?.findings.filter(
            (finding) =>
                providerValuesMatch(
                    finding.source,
                    providerName,
                ) ||
                providerValuesMatch(
                    finding.component,
                    providerName,
                ) ||
                createProviderId(finding.source) ===
                    providerId ||
                (finding.component !== null &&
                    createProviderId(finding.component) ===
                        providerId),
        ) ?? [];

    const relatedRecommendations =
        summary?.recommendations.filter(
            (recommendation) =>
                providerValuesMatch(
                    recommendation.component,
                    providerName,
                ) ||
                (recommendation.component !== null &&
                    createProviderId(
                        recommendation.component,
                    ) === providerId),
        ) ?? [];

    return (
        <main className="mx-auto max-w-7xl space-y-8 p-4 sm:p-8">
            <div className="flex flex-wrap items-center justify-between gap-4">
                <div>
                    <Link
                        to="/providers"
                        className="text-sm font-medium text-blue-400 transition hover:text-blue-300"
                    >
                        ← All providers
                    </Link>

                    <p className="mt-2 text-xs text-slate-500">
                        Mission Control / {providerName}
                    </p>
                </div>

                <div className="flex items-center gap-4">
                    {lastUpdated && <div className="text-right">
                        <p className="text-xs uppercase tracking-wider text-slate-500">
                            Last checked (local time)
                        </p>
                        <p className="mt-1 text-sm text-slate-300">
                            <time dateTime={lastUpdated.toISOString()}>
                                {lastUpdated.toLocaleString(undefined, {
                                    dateStyle: "medium",
                                    timeStyle: "short",
                                })}
                            </time>
                        </p>
                    </div>}

                    {isRefreshing && <RefreshIndicator active />}

                    <button
                        type="button"
                        onClick={() => void refresh()}
                        disabled={isLoading || isRefreshing}
                        className="rounded-lg border border-slate-700 bg-slate-900 px-4 py-2 text-sm font-medium text-slate-300 transition hover:border-slate-600 hover:text-white disabled:cursor-not-allowed disabled:opacity-50"
                    >
                        Refresh
                    </button>
                </div>
            </div>

            {error && (
                <div
                    role="alert"
                    className="rounded-lg border border-red-500/30 bg-red-500/10 p-5"
                >
                    <p className="font-semibold text-red-300">Some information could not be refreshed</p>
                    <p className="mt-1 text-sm text-red-200/80">Provider details may be out of date. Use Refresh above to check again.</p>
                    {(failedSources.length > 0 || error) && <details className="mt-3">
                        <summary className="cursor-pointer text-sm font-medium text-slate-300 focus:outline-none focus:ring-2 focus:ring-blue-300">Technical details</summary>
                        <div className="mt-2 space-y-1 text-sm text-slate-400">
                            {error && <p>{error}</p>}
                            {failedSources.length > 0 && <p>Unavailable: {failedSources.join(", ")}.</p>}
                        </div>
                    </details>}
                    {providerCatalogUnavailable && !provider && <p className="mt-2 text-sm text-red-200/80">Atlas could not confirm whether this provider is currently listed.</p>}
                </div>
            )}

            {isLoading && providers.length === 0 && (
                <section role="status" aria-live="polite" className="rounded-lg border border-slate-800 bg-slate-900 p-5 sm:p-8">
                    <p className="font-medium text-slate-200">Loading provider details…</p>
                </section>
            )}

            {!isLoading &&
                !providerCatalogUnavailable &&
                !provider && (
                    <section className="rounded-lg border border-amber-500/30 bg-amber-500/10 p-5 sm:p-8">
                        <h1 className="mt-3 text-2xl font-bold text-slate-100">
                            Provider not found
                        </h1>

                        <p className="mt-3 text-sm leading-6 text-slate-300">
                            This provider is not in the current catalog.
                        </p>
                    </section>
                )}

            {provider && (
                <>
                    <ProviderOverview provider={provider} stale={providerCatalogUnavailable} />

                    {capabilities === null && <p role="status" className="rounded-lg border border-amber-500/30 bg-amber-500/10 p-4 text-sm text-amber-100">Supported provider features could not be loaded. Some provider sections are hidden.</p>}

                    {capabilities?.includes("resources") && (
                        <section aria-label="Monitoring policy boundary">
                            <p className="mb-4 rounded-lg border border-slate-800 bg-slate-900/70 p-4 text-sm text-slate-300">
                                Monitoring expectations describe monitoring policy. They do not start, stop, restart, or remediate resources.
                            </p>
                            <ProviderResources provider={provider} />
                        </section>
                    )}

                    {summaryUnavailable && summary !== null && <p role="status" className="rounded-lg border border-amber-500/30 bg-amber-500/10 p-4 text-sm text-amber-100">Diagnostics and recommendations show the last available report. Atlas could not confirm current results.</p>}

                    <section>
                        <SectionHeader
                            title="Diagnostics"
                            description="Health and monitoring messages for this provider."
                        />

                        {summaryUnavailable && summary === null ? (
                            <div className="rounded-lg border border-amber-500/30 bg-amber-500/10 p-6 text-sm text-amber-100">Diagnostics could not be loaded.</div>
                        ) : relatedFindings.length > 0 ? (
                            <div className="grid gap-4 xl:grid-cols-2">
                                {relatedFindings.map((finding) => (
                                    <div
                                        key={finding.id}
                                        className={
                                            Array.isArray(
                                                finding.details
                                                    .unavailable_entities,
                                            )
                                                ? "xl:col-span-2"
                                                : ""
                                        }
                                    >
                                        <FindingCard
                                            finding={finding}
                                        />
                                    </div>
                                ))}
                            </div>
                        ) : (
                            <div className="rounded-lg border border-slate-800 bg-slate-900 p-6 text-sm text-slate-400">
                                {summaryUnavailable
                                    ? "The last available report had no messages about this provider."
                                    : "No messages about this provider right now."}
                            </div>
                        )}
                    </section>

                    <section>
                        <SectionHeader
                            title="Recommendations"
                            description="Suggestions for you to review. They don't change settings or run actions."
                        />

                        {summaryUnavailable && summary === null ? (
                            <div className="rounded-lg border border-amber-500/30 bg-amber-500/10 p-6 text-sm text-amber-100">Recommendations could not be loaded.</div>
                        ) : relatedRecommendations.length > 0 ? (
                            <div className="grid gap-4 lg:grid-cols-2">
                                {relatedRecommendations.map(
                                    (recommendation, index) => (
                                        <RecommendationCard
                                            key={`${recommendation.title}-${index}`}
                                            recommendation={recommendation}
                                        />
                                    ),
                                )}
                            </div>
                        ) : (
                            <div className="rounded-lg border border-slate-800 bg-slate-900 p-6 text-sm text-slate-400">
                                {summaryUnavailable
                                    ? "The last available report had no recommendations for this provider."
                                    : "No recommendations for this provider right now."}
                            </div>
                        )}
                    </section>

                    {provider.id === "proxmox" && <section aria-labelledby="operational-maintenance-heading" className="rounded-lg border border-slate-800 bg-slate-900/70 p-6">
                        <h2 id="operational-maintenance-heading" className="text-sm font-semibold uppercase tracking-[0.15em] text-slate-200">Planned maintenance</h2>
                        <p className="mt-2 text-sm leading-6 text-slate-400">Submit a request, review the plan, and approve it before Atlas starts maintenance.</p>
                        <Link to="/operations/request" className="mt-4 inline-flex rounded-lg border border-cyan-400/50 px-4 py-2 text-sm font-semibold text-cyan-100 transition hover:border-cyan-300">Request maintenance</Link>
                    </section>}

                    <ProviderActions
                        provider={provider}
                        onActionCompleted={refresh}
                    />

                    {capabilities?.includes("connection") && (
                        <ProviderConnection provider={provider} />
                    )}

                    <ProviderTelemetryTrend
                        providerId={provider.id}
                        snapshots={telemetryHistory}
                        performancePolicy={policies?.intelligence.providers[provider.id] ?? null}
                        performancePolicyStale={policiesUnavailable && policies?.intelligence.providers[provider.id] !== undefined}
                        unavailable={telemetryHistoryUnavailable}
                    />

                    {policies && (
                        <ProviderPolicyDetails
                            providerId={provider.id}
                            policies={policies}
                            stale={policiesUnavailable}
                        />
                    )}
                    {!policies && policiesUnavailable && <section aria-label="Provider monitoring settings" className="rounded-lg border border-amber-500/30 bg-amber-500/10 p-5"><SectionHeader title="Provider monitoring settings" description="Settings that help explain provider checks." /><p role="status" className="text-sm text-amber-100">Current monitoring settings could not be loaded. Refresh to try again.</p></section>}
                </>
            )}
        </main>
    );
}
