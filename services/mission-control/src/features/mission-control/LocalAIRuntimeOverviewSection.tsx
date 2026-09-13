import type { ReactNode } from "react";
import { SectionHeader } from "../../components/SectionHeader";
import { HealthStatusCard } from "../../components/health/HealthStatusPrimitive";
import type { HealthState } from "../../components/health/HealthStatusPrimitive";

type LocalAIOverviewProps = {
    /**
     * Whether local AI capabilities are available.
     * Unknown if not yet determined from Atlas evidence.
     */
    isAvailable?: boolean;
    /**
     * Configured model identity when available (from authoritative source).
     * Null/undefined if not exposed or not configured.
     */
    modelIdentity?: string | null;
    /**
     * Endpoint health when available (from authoritative source).
     * If not available, remains unknown.
     */
    endpointHealthy?: boolean | null;
    /**
     * Optional detailed status message from runtime.
     */
    statusMessage?: string | null;
};

/**
 * Local AI runtime overview for the dashboard.
 * Treats as observation/presentation only, not authority.
 * Clear separation between available/unavailable/unknown states.
 * Extension point for future Atlas Local AI Runtime project.
 *
 * Preserves:
 * - No inference/execution authority added here
 * - No GPU scheduling logic
 * - No model routing decisions
 * - Fail-closed semantics for missing evidence
 */
export function LocalAIRuntimeOverviewSection({
    isAvailable = undefined,
    modelIdentity = undefined,
    endpointHealthy = undefined,
    statusMessage = undefined,
}: LocalAIOverviewProps) {
    // Determine health state from available evidence
    let healthState: HealthState;
    let reason: string | undefined;
    let details: ReactNode | undefined;

    if (isAvailable === undefined) {
        // No evidence about local AI availability
        healthState = "unknown";
        reason = "No authoritative evidence available";
        details = (
            <p className="text-xs text-mc-text-secondary">
                Local AI runtime status is not exposed by Atlas Core. Enable or
                configure the Local AI runtime to see status here.
            </p>
        );
    } else if (isAvailable === false) {
        // Explicitly unavailable
        healthState = "unavailable";
        reason = "Local AI runtime not available";
        details = (
            <p className="text-xs text-mc-text-secondary">
                The Local AI runtime is not running or not accessible. Deploy and
                start the runtime to enable local inference.
            </p>
        );
    } else if (endpointHealthy === false) {
        // Available but endpoint unhealthy
        healthState = "degraded";
        reason = "Endpoint unhealthy or not responding";
        details = (
            <div className="space-y-2 text-xs text-mc-text-secondary">
                {statusMessage && <p>{statusMessage}</p>}
                <p>Check runtime logs and network connectivity.</p>
            </div>
        );
    } else if (endpointHealthy === true) {
        // Healthy
        healthState = "healthy";
        reason = "Local AI runtime operational";
        details = (
            <div className="space-y-2 text-xs text-mc-text-secondary">
                {modelIdentity && (
                    <p>
                        <span className="font-medium">Model:</span> {modelIdentity}
                    </p>
                )}
                {statusMessage && <p>{statusMessage}</p>}
            </div>
        );
    } else {
        // Available but endpoint status unknown
        healthState = "unknown";
        reason = "Endpoint status unknown";
        details = (
            <p className="text-xs text-mc-text-secondary">
                Local AI runtime is available but endpoint health status is not
                exposed.
            </p>
        );
    }

    return (
        <section>
            <SectionHeader
                title="Local AI Runtime"
                description="Local inference runtime status and configuration."
            />

            <HealthStatusCard
                state={healthState}
                title="Local AI Availability"
                reason={reason}
                details={details}
            />

            {/* Extension point note for future Atlas Local AI Runtime */}
            <div className="mt-4 rounded-mc-lg border border-mc-border-subtle bg-mc-surface-muted p-3 text-xs text-mc-text-muted">
                <p>
                    This section will expand as the Atlas Local AI Runtime project
                    provides:
                </p>
                <ul className="mt-2 list-inside list-disc space-y-1">
                    <li>Model availability and version information</li>
                    <li>GPU/accelerator status and resource utilization</li>
                    <li>Inference queue depth and latency metrics</li>
                    <li>Model routing and load balancing status</li>
                </ul>
            </div>
        </section>
    );
}
