import { DashboardHeader } from "../../components/DashboardHeader";
import { HealthCard } from "../../components/HealthCard";
import { ProviderCard } from "../../components/ProviderCard";
import { SectionHeader } from "../../components/SectionHeader";
import { useMissionControl } from "../../hooks/useMissionControl";
import { FindingsSection } from "./FindingsSection";
import { RecommendationsSection } from "./RecommendationsSection";
import { ServiceHealthSection } from "./ServiceHealthSection";

export function MissionControl() {
    const {
        summary,
        health,
        providers,
        lastUpdated,
        error,
        isLoading,
        isRefreshing,
        refresh,
    } = useMissionControl();

    return (
        <div className="min-h-screen">
            <DashboardHeader
                lastUpdated={lastUpdated}
                atlasStatus={health?.atlas ?? null}
                isRefreshing={isRefreshing}
                onRefresh={refresh}
            />

            <main className="mx-auto max-w-7xl space-y-8 p-8">
                {error && (
                    <div
                        role="alert"
                        className="flex items-center justify-between gap-6 rounded-lg border border-red-500/30 bg-red-500/10 p-4"
                    >
                        <div>
                            <p className="font-semibold text-red-300">
                                Atlas Core unavailable
                            </p>
                            <p className="mt-1 text-sm text-red-200/80">
                                {error}
                            </p>
                        </div>

                        <button
                            type="button"
                            onClick={() => void refresh()}
                            disabled={isRefreshing}
                            className="rounded-lg border border-red-400/30 px-4 py-2 text-sm font-medium text-red-200 transition hover:bg-red-400/10 disabled:cursor-not-allowed disabled:opacity-50"
                        >
                            Retry
                        </button>
                    </div>
                )}

                {isLoading &&
                    !summary &&
                    !health &&
                    providers.length === 0 && (
                        <div className="rounded-lg border border-slate-800 bg-slate-900 p-8">
                            <p className="text-sm font-medium text-slate-300">
                                Connecting to Atlas Core...
                            </p>
                            <p className="mt-2 text-sm text-slate-500">
                                Loading the current ACE situation report,
                                platform health, and provider catalog.
                            </p>
                        </div>
                    )}

                {summary && (
                    <>
                        <HealthCard
                            score={summary.score}
                            status={summary.status}
                            summary={summary.summary}
                        />

                        <RecommendationsSection
                            recommendations={summary.recommendations}
                        />
                    </>
                )}

                {health && (
                    <ServiceHealthSection
                        services={health.services}
                        isRefreshing={isRefreshing}
                        onRefresh={() => void refresh()}
                    />
                )}

                {(health || providers.length > 0) && (
                    <section>
                        <SectionHeader
                            title="Providers"
                            description="Registry-backed Atlas capabilities and connected infrastructure."
                        />

                        {providers.length > 0 ? (
                            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
                                {providers.map((provider) => (
                                    <ProviderCard
                                        key={provider.id}
                                        provider={provider}
                                    />
                                ))}
                            </div>
                        ) : (
                            !isLoading && (
                                <div className="rounded-lg border border-slate-800 bg-slate-900 p-6">
                                    <p className="text-sm font-medium text-slate-300">
                                        No providers registered
                                    </p>
                                    <p className="mt-2 text-sm text-slate-500">
                                        Atlas Core did not return any
                                        providers from the registry.
                                    </p>
                                </div>
                            )
                        )}
                    </section>
                )}

                {summary && (
                    <FindingsSection findings={summary.findings} />
                )}
            </main>
        </div>
    );
}
