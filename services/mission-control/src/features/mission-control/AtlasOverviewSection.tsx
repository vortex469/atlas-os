import { SectionHeader } from "../../components/SectionHeader";
import { HealthStatusCard } from "../../components/health/HealthStatusPrimitive";
import {
    mapServiceStatusToHealthState,
    isEvidenceStale,
} from "../../components/health/healthPresentation";
import { healthReason } from "../../utils/healthPresentation";
import type { ServiceHealth } from "../../types/health";

type CoreHealthProps = {
    atlasStatus: string | null | undefined;
    services: Record<string, ServiceHealth>;
    lastUpdated: Date | null;
};

/**
 * Atlas overall state and core health summary.
 * Displays Atlas status, critical service health, and core subsystem overview.
 */
export function AtlasOverviewSection({
    atlasStatus,
    services,
    lastUpdated,
}: CoreHealthProps) {
    const atlasHealthState = mapServiceStatusToHealthState(atlasStatus);
    const isStale = isEvidenceStale(lastUpdated);

    // Get critical services (sorted by importance)
    const criticalServices = Object.entries(services ?? {})
        .filter(([, service]) => mapServiceStatusToHealthState(service.status) !== "healthy")
        .slice(0, 3);

    return (
        <section>
            <SectionHeader
                title="Atlas health"
                description="See whether Atlas Core and its key services are responding."
            />

            <div className="grid gap-4 sm:grid-cols-2">
                <HealthStatusCard
                    state={atlasHealthState}
                    title="Atlas Core"
                    lastUpdated={lastUpdated}
                    isStale={isStale}
                    details={
                        criticalServices.length > 0 ? (
                            <div className="space-y-2 text-sm">
                                <p className="font-medium text-mc-text-secondary">
                                    Services needing attention:
                                </p>
                                <ul className="space-y-1">
                                    {criticalServices.map(([name, service]) => (
                                        <li
                                            key={name}
                                            className="text-xs text-mc-text-secondary"
                                        >
                                            {name}: {serviceHealthLabel(service.status)} · {service.latency_ms !== null
                                                ? `response time ${service.latency_ms} ms`
                                                : "response time not reported"}
                                        </li>
                                    ))}
                                </ul>
                            </div>
                        ) : undefined
                    }
                />

                {/* Health snapshot of critical services */}
                {Object.entries(services ?? {})
                    .slice(0, 1)
                    .map(([name, service]) => {
                        const healthState = mapServiceStatusToHealthState(
                            service.status,
                        );
                        return (
                            <HealthStatusCard
                                key={name}
                                state={healthState}
                                title={name}
                                reason={healthReason(service.message)
                                    ?? (service.http_status === 200
                                        ? undefined
                                        : service.http_status === null
                                            ? "Atlas Core could not confirm a healthy response."
                                            : `Atlas Core received an HTTP ${service.http_status} response.`)}
                                details={
                                    <div className="text-xs text-mc-text-secondary">
                                        {service.latency_ms !== null && (
                                            <p>Latency: {service.latency_ms}ms</p>
                                        )}
                                    </div>
                                }
                            />
                        );
                    })}
            </div>
        </section>
    );
}

function serviceHealthLabel(status: unknown): string {
    const state = mapServiceStatusToHealthState(status);
    return state === "unknown" ? "Status unknown" : `${state[0].toUpperCase()}${state.slice(1)}`;
}
