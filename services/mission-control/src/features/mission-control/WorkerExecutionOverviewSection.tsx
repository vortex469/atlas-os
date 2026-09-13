import { Link } from "react-router-dom";
import { SectionHeader } from "../../components/SectionHeader";
import { HealthStatusCard } from "../../components/health/HealthStatusPrimitive";
import type { HealthState } from "../../components/health/HealthStatusPrimitive";

type ExecutionMetric = {
    label: string;
    value: number;
    link?: string;
};

type WorkerExecutionOverviewProps = {
    /** Execution candidates eligible for processing */
    eligibleCount?: number;
    /** Execution candidates not eligible */
    notEligibleCount?: number;
    /** Active/running executions */
    runningCount?: number;
    /** Blocked/waiting executions */
    blockedCount?: number;
    /** Queued work items */
    queuedCount?: number;
};

/**
 * Worker and execution activity overview.
 * Displays worker availability, active work, and execution queue status.
 * Uses existing authoritative evidence, preserves fail-closed semantics.
 */
export function WorkerExecutionOverviewSection({
    eligibleCount = 0,
    notEligibleCount = 0,
    runningCount = 0,
    blockedCount = 0,
    queuedCount = 0,
}: WorkerExecutionOverviewProps) {
    const totalWorkItems = eligibleCount + notEligibleCount;
    const hasActiveWork =
        runningCount > 0 || queuedCount > 0;
    const isBlocked = blockedCount > 0;

    // Determine health state based on evidence
    let healthState: HealthState;
    let reason: string | undefined;

    if (isBlocked) {
        healthState = "blocked";
        reason = `${blockedCount} work item${blockedCount !== 1 ? "s" : ""} blocked`;
    } else if (hasActiveWork && runningCount === 0) {
        healthState = "degraded";
        reason = `${queuedCount} item${queuedCount !== 1 ? "s" : ""} queued, not executing`;
    } else if (runningCount > 0) {
        healthState = "healthy";
        reason = `${runningCount} active execution${runningCount !== 1 ? "s" : ""}`;
    } else if (totalWorkItems > 0 || queuedCount > 0) {
        healthState = "healthy";
        reason = `Ready for execution`;
    } else {
        healthState = "unknown";
        reason = "No execution evidence available";
    }

    const executionMetrics: ExecutionMetric[] = [
        { label: "Eligible", value: eligibleCount, link: "/execution-candidates" },
        { label: "Not Eligible", value: notEligibleCount },
        { label: "Active", value: runningCount },
        { label: "Queued", value: queuedCount },
    ];

    return (
        <section>
            <SectionHeader
                title="Worker & Execution"
                description="Atlas worker availability and execution queue status."
            />

            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
                <HealthStatusCard
                    state={healthState}
                    title="Execution Status"
                    reason={reason}
                    compact={true}
                />

                {executionMetrics.map((metric) => (
                    <div
                        key={metric.label}
                        className="mc-surface rounded-mc-lg p-4"
                    >
                        <p className="text-xs font-medium uppercase tracking-wider text-mc-text-muted">
                            {metric.label}
                        </p>
                        <p className="mt-2 text-2xl font-bold text-mc-text-primary">
                            {metric.value}
                        </p>
                        {metric.link && (
                            <Link
                                to={metric.link}
                                className="mt-3 inline-flex text-xs font-medium text-mc-primary transition hover:text-mc-primary/80 focus:outline-none focus:ring-1 focus:ring-mc-primary"
                            >
                                View details →
                            </Link>
                        )}
                    </div>
                ))}

                {isBlocked && (
                    <div className="md:col-span-2 lg:col-span-4 rounded-mc-lg border border-mc-border-subtle bg-mc-surface-elevated p-4">
                        <p className="text-sm text-mc-text-secondary">
                            ⚠️ {blockedCount} execution
                            {blockedCount !== 1 ? "s" : ""} blocked from
                            proceeding. Operator action may be required.
                        </p>
                    </div>
                )}
            </div>
        </section>
    );
}
