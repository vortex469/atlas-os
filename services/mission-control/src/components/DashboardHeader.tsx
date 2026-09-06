import type { ServiceStatus } from "../types/health";
import { RefreshIndicator } from "./RefreshIndicator";
import { StatusBadge } from "./StatusBadge";

type DashboardHeaderProps = {
    lastUpdated: Date | null;
    atlasStatus: ServiceStatus | string | null;
    isRefreshing: boolean;
    onRefresh: () => Promise<void>;
};

export function DashboardHeader({
    lastUpdated,
    atlasStatus,
    isRefreshing,
    onRefresh,
}: DashboardHeaderProps) {
    return (
        <header className="border-b border-mc-divider bg-mc-surface">
            <div className="mc-container flex min-h-20 flex-col justify-between gap-4 py-4 sm:flex-row sm:items-center">
                <div>
                    <h1 className="text-xl font-bold tracking-[0.2em] text-mc-text-primary">
                        ATLAS
                    </h1>
                    <p className="text-xs text-mc-text-muted">
                        Mission Control
                    </p>
                </div>

                <div className="flex flex-wrap items-center gap-4">
                    <div className="text-left sm:text-right">
                        <p className="text-xs uppercase tracking-wider text-mc-text-muted">
                            Last Updated
                        </p>
                        <p className="mt-1 text-sm text-mc-text-secondary">
                            {lastUpdated
                                ? lastUpdated.toLocaleTimeString()
                                : "Connecting..."}
                        </p>
                    </div>

                    <div className="flex items-center gap-3">
                        <RefreshIndicator active={isRefreshing} />

                        {atlasStatus && (
                            <StatusBadge status={atlasStatus} />
                        )}

                        <button
                            type="button"
                            onClick={() => void onRefresh()}
                            disabled={isRefreshing}
                            className="mc-control mc-focusable px-4 py-2 text-sm"
                        >
                            {isRefreshing ? "Refreshing..." : "Refresh"}
                        </button>
                    </div>
                </div>
            </div>
        </header>
    );
}
