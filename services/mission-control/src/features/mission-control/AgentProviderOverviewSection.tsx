import { Link } from "react-router-dom";
import { SectionHeader } from "../../components/SectionHeader";
import { HealthStatusCard } from "../../components/health/HealthStatusPrimitive";
import {
    mapServiceStatusToHealthState,
} from "../../components/health/healthPresentation";
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
    const available = providers.filter(
        (p) =>
            p.health?.status?.toLowerCase() === "healthy" ||
            p.health?.status?.toLowerCase() === "online",
    );
    const unavailable = providers.filter(
        (p) =>
            p.health?.status?.toLowerCase() === "offline" ||
            p.health?.status?.toLowerCase() === "unavailable",
    );
    const degraded = providers.filter(
        (p) =>
            p.health?.status?.toLowerCase() === "degraded" ||
            p.health?.status?.toLowerCase() === "warning",
    );

    const criticalProviders = providers.filter((p) => p.priority === "critical");
    const hasUnavailableCritical = criticalProviders.some(
        (p) =>
            p.health?.status?.toLowerCase() === "offline" ||
            p.health?.status?.toLowerCase() === "unavailable",
    );

    return (
        <section>
            <SectionHeader
                title="Agents & Providers"
                description="Configured AI providers and external integrations."
            />

            {providers.length === 0 ? (
                <div className="mc-surface rounded-mc-lg p-6">
                    <p className="text-sm text-mc-text-secondary">
                        No providers configured.
                    </p>
                    <p className="mt-2 text-xs text-mc-text-muted">
                        Add providers to enable agent capabilities.
                    </p>
                </div>
            ) : (
                <>
                    {/* Summary Cards */}
                    <div className="mb-6 grid gap-4 sm:grid-cols-2 md:grid-cols-4">
                        <div className="mc-surface rounded-mc-lg p-4">
                            <p className="text-xs font-medium uppercase tracking-wider text-mc-text-muted">
                                Total Providers
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
                                Degraded
                            </p>
                            <p className="mt-2 text-2xl font-bold text-amber-400">
                                {degraded.length}
                            </p>
                        </div>

                        <div className="mc-surface rounded-mc-lg p-4">
                            <p className="text-xs font-medium uppercase tracking-wider text-mc-text-muted">
                                Unavailable
                            </p>
                            <p className="mt-2 text-2xl font-bold text-red-400">
                                {unavailable.length}
                            </p>
                        </div>
                    </div>

                    {/* Critical provider warnings */}
                    {hasUnavailableCritical && (
                        <div className="mb-6 rounded-mc-lg border border-mc-border-subtle bg-mc-surface-elevated p-4">
                            <p className="text-sm font-medium text-mc-text-primary">
                                ⚠️ Critical Provider Unavailable
                            </p>
                            <div className="mt-2 space-y-1 text-xs text-mc-text-secondary">
                                {criticalProviders
                                    .filter(
                                        (p) =>
                                            p.health?.status?.toLowerCase() ===
                                                "offline" ||
                                            p.health?.status?.toLowerCase() ===
                                                "unavailable",
                                    )
                                    .map((p) => (
                                        <p key={p.id}>
                                            {p.name} is not responding.{" "}
                                            {p.health?.message &&
                                                ` ${p.health.message}`}
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
                            const isPriorityCritical = provider.priority === "critical";

                            return (
                                <HealthStatusCard
                                    key={provider.id}
                                    state={healthState}
                                    title={`${provider.name}${isPriorityCritical ? " ⭐" : ""}`}
                                    reason={
                                        provider.health?.message ||
                                        (provider.health?.http_status &&
                                        provider.health.http_status >= 400
                                            ? `HTTP ${provider.health.http_status}`
                                            : undefined)
                                    }
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
