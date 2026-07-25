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
        <header className="border-b border-slate-800 bg-slate-900">
            <div className="mx-auto flex min-h-20 max-w-7xl flex-col justify-between gap-4 px-8 py-4 sm:flex-row sm:items-center">
                <div>
                    <h1 className="text-xl font-bold tracking-[0.2em] text-slate-100">
                        ATLAS
                    </h1>
                    <p className="text-xs text-slate-400">
                        Mission Control
                    </p>
                </div>

                <div className="flex flex-wrap items-center gap-4">
                    <div className="text-left sm:text-right">
                        <p className="text-xs uppercase tracking-wider text-slate-500">
                            Last Updated
                        </p>
                        <p className="mt-1 text-sm text-slate-300">
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
                            className="rounded-lg border border-slate-700 bg-slate-950 px-4 py-2 text-sm font-medium text-slate-300 transition hover:border-slate-600 hover:text-slate-100 disabled:cursor-not-allowed disabled:opacity-50"
                        >
                            {isRefreshing ? "Refreshing..." : "Refresh"}
                        </button>
                    </div>
                </div>
            </div>
        </header>
    );
}
