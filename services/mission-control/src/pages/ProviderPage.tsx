import { Link, useParams } from "react-router-dom";

import { FindingCard } from "../components/FindingCard";
import { ProviderActions } from "../components/ProviderActions";
import { ProviderOverview } from "../components/ProviderOverview";
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
        lastUpdated,
        error,
        isLoading,
        isRefreshing,
        refresh,
    } = useMissionControl();

    const provider = providers.find(
        (candidate) => candidate.id === providerId,
    );

    const providerName =
        provider?.name ?? formatProviderId(providerId);

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
        <main className="mx-auto max-w-7xl space-y-8 p-8">
            <div className="flex flex-wrap items-center justify-between gap-4">
                <div>
                    <Link
                        to="/"
                        className="text-sm font-medium text-blue-400 transition hover:text-blue-300"
                    >
                        ← Mission Control
                    </Link>

                    <p className="mt-2 text-xs text-slate-500">
                        Mission Control / {providerName}
                    </p>
                </div>

                <div className="flex items-center gap-4">
                    <div className="text-right">
                        <p className="text-xs uppercase tracking-wider text-slate-500">
                            Last Updated
                        </p>

                        <p className="mt-1 text-sm text-slate-300">
                            {lastUpdated
                                ? lastUpdated.toLocaleTimeString()
                                : "Connecting..."}
                        </p>
                    </div>

                    <RefreshIndicator active={isRefreshing} />

                    <button
                        type="button"
                        onClick={() => void refresh()}
                        disabled={isRefreshing}
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
                    <p className="font-semibold text-red-300">
                        Atlas Core unavailable
                    </p>

                    <p className="mt-1 text-sm text-red-200/80">
                        {error}
                    </p>
                </div>
            )}

            {isLoading && providers.length === 0 && (
                <section className="rounded-lg border border-slate-800 bg-slate-900 p-8">
                    <p className="font-medium text-slate-200">
                        Loading provider details...
                    </p>

                    <p className="mt-2 text-sm text-slate-500">
                        Retrieving the provider catalog from Atlas Core.
                    </p>
                </section>
            )}

            {!isLoading &&
                providers.length > 0 &&
                !provider && (
                    <section className="rounded-lg border border-amber-500/30 bg-amber-500/10 p-8">
                        <p className="text-xs font-semibold uppercase tracking-[0.18em] text-amber-400">
                            Provider unavailable
                        </p>

                        <h1 className="mt-3 text-2xl font-bold text-slate-100">
                            {providerName}
                        </h1>

                        <p className="mt-3 text-sm leading-6 text-slate-300">
                            This provider was not found in the Atlas
                            Provider Registry.
                        </p>

                        <Link
                            to="/"
                            className="mt-6 inline-flex text-sm font-medium text-blue-400 hover:text-blue-300"
                        >
                            Return to Mission Control
                        </Link>
                    </section>
                )}

            {provider && (
                <>
                    <ProviderOverview provider={provider} />
                    <ProviderActions
                        provider={provider}
                        onActionCompleted={refresh}
                    />

                    <section>
                        <SectionHeader
                            title="Related Recommendations"
                            description="Actions ACE recommends for this provider."
                        />

                        {relatedRecommendations.length > 0 ? (
                            <div className="grid gap-4 lg:grid-cols-2">
                                {relatedRecommendations.map(
                                    (recommendation, index) => (
                                        <RecommendationCard
                                            key={`${recommendation.title}-${index}`}
                                            recommendation={
                                                recommendation
                                            }
                                        />
                                    ),
                                )}
                            </div>
                        ) : (
                            <div className="rounded-lg border border-slate-800 bg-slate-900 p-6 text-sm text-slate-400">
                                ACE has no current recommendations for this
                                provider.
                            </div>
                        )}
                    </section>

                    <section>
                        <SectionHeader
                            title="Related Findings"
                            description="Evidence ACE has collected for this provider."
                        />

                        {relatedFindings.length > 0 ? (
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
                                ACE has no current findings for this
                                provider.
                            </div>
                        )}
                    </section>
                </>
            )}
        </main>
    );
}
