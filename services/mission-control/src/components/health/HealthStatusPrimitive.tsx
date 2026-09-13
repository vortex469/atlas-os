import type { ReactNode } from "react";

/**
 * Unified health states across all dashboard sections.
 * Maps authoritative evidence from Atlas Core into consistent presentation.
 */
export type HealthState = "healthy" | "degraded" | "unavailable" | "blocked" | "unknown";

export type HealthStatusProps = {
    /** Current health state */
    state: HealthState;
    /** Optional title/label for the status */
    title?: string;
    /** Optional reason why degraded/unavailable/blocked when evidence provides one */
    reason?: string | null;
    /** Optional last-known update timestamp from authoritative source */
    lastUpdated?: Date | null;
    /** Whether the evidence is stale (timestamp significantly in the past) */
    isStale?: boolean;
    /** Compact variant for inline display (skip title/description) */
    compact?: boolean;
    /** Custom content/details to display below main status */
    details?: ReactNode;
};

const stateConfig: Record<
    HealthState,
    {
        label: string;
        variant: string;
        description: string;
    }
> = {
    healthy: {
        label: "Healthy",
        variant: "mc-status-success",
        description: "System is operating normally with no known issues",
    },
    degraded: {
        label: "Degraded",
        variant: "mc-status-warning",
        description: "System is operational but experiencing issues",
    },
    unavailable: {
        label: "Unavailable",
        variant: "mc-status-error",
        description: "System is not responding or cannot be accessed",
    },
    blocked: {
        label: "Blocked",
        variant: "mc-status-error",
        description: "System is operational but blocked from proceeding",
    },
    unknown: {
        label: "Unknown",
        variant: "mc-status-neutral",
        description: "No authoritative evidence available",
    },
};

function formatLastUpdated(date: Date, isStale?: boolean): string {
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffSecs = Math.floor(diffMs / 1000);
    const diffMins = Math.floor(diffSecs / 60);
    const diffHours = Math.floor(diffMins / 60);
    const diffDays = Math.floor(diffHours / 24);

    let timeStr: string;
    if (diffMins === 0) {
        timeStr = "just now";
    } else if (diffMins < 60) {
        timeStr = `${diffMins}m ago`;
    } else if (diffHours < 24) {
        timeStr = `${diffHours}h ago`;
    } else {
        timeStr = `${diffDays}d ago`;
    }

    if (isStale) {
        return `${timeStr} (stale)`;
    }
    return timeStr;
}

/**
 * Compact health status indicator with optional reason and staleness indicator.
 * Use in summary cards and inline displays.
 */
export function HealthStatusBadge({
    state,
    title,
    reason,
    lastUpdated,
    isStale,
}: HealthStatusProps) {
    const config = stateConfig[state] ?? stateConfig.unknown;

    return (
        <div className="flex min-w-0 flex-wrap items-center gap-2">
            <span
                className={["mc-status-badge", config.variant].join(" ")}
                data-mc-status={config.variant.replace("mc-status-", "")}
            >
                <span className="mc-status-dot" aria-hidden="true" />
                {title || config.label}
            </span>

            {reason && (
                <span className="text-xs text-mc-text-secondary">
                    {reason}
                </span>
            )}

            {lastUpdated && Number.isFinite(lastUpdated.getTime()) && (
                <span
                    className={[
                        "text-xs",
                        isStale
                            ? "text-mc-text-disabled"
                            : "text-mc-text-muted",
                    ].join(" ")}
                >
                    {formatLastUpdated(lastUpdated, isStale)}
                </span>
            )}
        </div>
    );
}

/**
 * Full health status display with title, state, reason, and details.
 * Use as a primary component in dashboard sections.
 */
export function HealthStatusCard({
    state,
    title,
    reason,
    lastUpdated,
    isStale,
    compact = false,
    details,
}: HealthStatusProps) {
    if (compact) {
        return (
            <HealthStatusBadge
                state={state}
                title={title}
                reason={reason}
                lastUpdated={lastUpdated}
                isStale={isStale}
            />
        );
    }

    return (
        <div className="mc-surface rounded-mc-lg p-4">
            <div className="flex items-start gap-3">
                <div className="flex-1">
                    {title && (
                        <h3 className="text-sm font-medium text-mc-text-primary">
                            {title}
                        </h3>
                    )}

                    <div className="mt-2">
                        <HealthStatusBadge
                            state={state}
                            title={title ? undefined : undefined}
                            reason={reason}
                            lastUpdated={lastUpdated}
                            isStale={isStale}
                        />
                    </div>

                    {reason && (
                        <p className="mt-2 text-xs text-mc-text-secondary">
                            {reason}
                        </p>
                    )}

                    {details && (
                        <div className="mt-3 border-t border-mc-divider pt-3">
                            {details}
                        </div>
                    )}
                </div>
            </div>

            {isStale && (
                <div
                    className="mt-3 border-t border-mc-border-subtle pt-2 text-[11px] text-mc-text-disabled"
                    role="status"
                >
                    ⚠️ This evidence is stale. Refresh to get current status.
                </div>
            )}
        </div>
    );
}

