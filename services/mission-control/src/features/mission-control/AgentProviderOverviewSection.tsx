import { Link } from "react-router-dom";
import { SectionHeader } from "../../components/SectionHeader";
import { HealthStatusCard } from "../../components/health/HealthStatusPrimitive";
import {
    mapServiceStatusToHealthState,
} from "../../components/health/healthPresentation";
import { healthReason } from "../../utils/healthPresentation";
import type { Provider } from "../../types/provider";

type AgentProviderOverviewProps = {
    providers: Provider[];
};

/**
 * Agent and provider availability overview.
 * Shows configured providers, distinguishes available/unavailable/unknown states.
 * Redacts sensitive data (secrets, tokens, credentials).
 * Neutral provider presentation - no hardcoding of specific providers.
 */
export function AgentProviderOverviewSection({
    providers,
}: AgentProviderOverviewProps) {
    const available = providers.filter((provider) => mapServiceStatusToHealthState(provider.health?.status) === "healthy");
    const needsAttention = providers.length - available.length;
    const unavailableCriticalProviders = providers.filter((provider) =>
        provider.priority === "critical"
        && mapServiceStatusToHealthState(provider.health?.status) === "unavailable",
    );

    return (
        <section>
            <SectionHeader
                title="Providers & integrations"
                description="See whether configured AI providers and external services are responding."
            />

            {providers.length === 0 ? (
                <div className="mc-surface rounded-mc-lg p-6">
                    <p className="text-sm text-mc-text-secondary">
                            No providers are set up yet.
                    </p>
                    <p className="mt-2 text-xs text-mc-text-muted">
                            Add a provider to connect an AI or external service.
                    </p>
                </div>
            ) : (
                <>
                    {/* Summary Cards */}
                    <div className="mb-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                        <div className="mc-surface rounded-mc-lg p-4">
                            <p className="text-xs font-medium uppercase tracking-wider text-mc-text-muted">
                                Total providers
                            </p>
                            <p className="mt-2 text-2xl font-bold text-mc-text-primary">
                                {providers.length}
                            </p>
                        </div>

                        <div className="mc-surface rounded-mc-lg p-4">
                            <p className="text-xs font-medium uppercase tracking-wider text-mc-text-muted">
                                Available
                            </p>
                            <p className="mt-2 text-2xl font-bold text-emerald-400">
                                {available.length}
                            </p>
                        </div>

                        <div className="mc-surface rounded-mc-lg p-4">
                            <p className="text-xs font-medium uppercase tracking-wider text-mc-text-muted">
                                Needs attention
                            </p>
                            <p className="mt-2 text-2xl font-bold text-amber-400">
                                {needsAttention}
                            </p>
                        </div>
                    </div>

                    {/* Critical provider warnings */}
                    {unavailableCriticalProviders.length > 0 && (
                        <div className="mb-6 rounded-mc-lg border border-mc-border-subtle bg-mc-surface-elevated p-4">
                            <p className="text-sm font-medium text-mc-text-primary">
                                Critical provider unavailable
                            </p>
                            <div className="mt-2 space-y-1 text-xs text-mc-text-secondary">
                                {unavailableCriticalProviders.map((provider) => (
                                    <p key={provider.id}>
                                        {provider.name} is unavailable. {healthReason(provider.health?.message) ?? "Atlas Core could not confirm a response."}
                                    </p>
                                ))}
                            </div>
                        </div>
                    )}

                    {/* Provider health grid */}
                    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                        {providers.map((provider) => {
                            const healthState = mapServiceStatusToHealthState(
                                provider.health?.status,
                            );
                            const stateLabel = healthState === "unknown"
                                ? "Status unknown"
                                : `${healthState[0].toUpperCase()}${healthState.slice(1)}`;

                            return (
                                <HealthStatusCard
                                    key={provider.id}
                                    state={healthState}
                                    title={`${provider.name} — ${stateLabel}${provider.priority === "critical" ? " (critical)" : ""}`}
                                    reason={healthReason(provider.health?.message)
                                        ?? (provider.health?.http_status != null && provider.health.http_status >= 400
                                            ? `Atlas Core received an HTTP ${provider.health.http_status} response.`
                                            : undefined)}
                                    compact={true}
                                />
                            );
                        })}
                    </div>

                    {/* Provider details link */}
                    <div className="mt-6 text-center">
                        <Link
                            to="/providers"
                            className="inline-flex rounded-mc-md border border-mc-border-subtle bg-mc-surface px-4 py-2 text-sm font-medium text-mc-primary transition hover:bg-mc-surface-elevated focus:outline-none focus:ring-2 focus:ring-mc-primary"
                        >
                            Manage Providers
                        </Link>
                    </div>
                </>
            )}
        </section>
    );
}
