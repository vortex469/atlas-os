import {
    useCallback,
    useEffect,
    useRef,
    useState,
} from "react";

import {
    getAtlasErrorMessage,
    getProviderActionHistory,
} from "../api/atlas";
import type {
    ActionHistoryStatus,
    ProviderActionAuditEntry,
} from "../types/actionHistory";

type HistoryFilter = "all" | ActionHistoryStatus;

function formatTimestamp(timestamp: string): string {
    const date = new Date(timestamp);

    if (Number.isNaN(date.getTime())) {
        return "Unknown time";
    }

    return date.toLocaleString();
}

function statusClasses(status: ActionHistoryStatus): string {
    return status === "succeeded"
        ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-300"
        : "border-red-500/30 bg-red-500/10 text-red-300";
}

export function OperationsPage() {
    const [entries, setEntries] = useState<
        ProviderActionAuditEntry[]
    >([]);
    const [filter, setFilter] = useState<HistoryFilter>("all");
    const [isLoading, setIsLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const requestSequence = useRef(0);

    const loadHistory = useCallback(async () => {
        const requestId = requestSequence.current + 1;
        requestSequence.current = requestId;
        setIsLoading(true);
        setError(null);

        try {
            const history = await getProviderActionHistory({
                limit: 100,
                status: filter === "all" ? undefined : filter,
            });

            if (requestSequence.current === requestId) {
                setEntries(history);
            }
        } catch (requestError) {
            if (requestSequence.current !== requestId) {
                return;
            }

            console.error(
                "Unable to load provider action history:",
                requestError,
            );
            setError(
                getAtlasErrorMessage(
                    requestError,
                    "Mission Control could not load action history.",
                ),
            );
        } finally {
            if (requestSequence.current === requestId) {
                setIsLoading(false);
            }
        }
    }, [filter]);

    useEffect(() => {
        const timeoutId = window.setTimeout(() => {
            void loadHistory();
        }, 0);

        return () => {
            window.clearTimeout(timeoutId);
        };
    }, [loadHistory]);

    return (
        <main className="mx-auto max-w-7xl space-y-6 p-8">
            <header className="flex flex-col justify-between gap-4 border-b border-slate-800 pb-6 sm:flex-row sm:items-end">
                <div>
                    <p className="text-xs font-semibold uppercase tracking-[0.2em] text-cyan-400">
                        Operations
                    </p>
                    <h1 className="mt-2 text-3xl font-semibold text-slate-100">
                        Action History
                    </h1>
                    <p className="mt-2 max-w-2xl text-sm text-slate-400">
                        Recent provider operations, outcomes, and request
                        correlation from Atlas Core.
                    </p>
                </div>

                <button
                    type="button"
                    onClick={() => void loadHistory()}
                    disabled={isLoading}
                    className="rounded-lg border border-cyan-500/30 bg-cyan-500/10 px-4 py-2 text-sm font-semibold text-cyan-200 transition hover:bg-cyan-500/20 disabled:cursor-not-allowed disabled:opacity-50"
                >
                    {isLoading ? "Refreshing..." : "Refresh history"}
                </button>
            </header>

            <div className="flex flex-wrap items-center justify-between gap-4">
                <div
                    className="flex rounded-lg border border-slate-800 bg-slate-900 p-1"
                    aria-label="Filter action history"
                >
                    {(
                        [
                            ["all", "All"],
                            ["succeeded", "Succeeded"],
                            ["failed", "Failed"],
                        ] as const
                    ).map(([value, label]) => (
                        <button
                            key={value}
                            type="button"
                            onClick={() => setFilter(value)}
                            className={
                                filter === value
                                    ? "rounded-md bg-slate-700 px-3 py-2 text-sm font-medium text-white"
                                    : "rounded-md px-3 py-2 text-sm font-medium text-slate-400 transition hover:text-white"
                            }
                        >
                            {label}
                        </button>
                    ))}
                </div>

                <p className="text-xs text-slate-500">
                    Persistent audit history · retention managed by Atlas Core
                </p>
            </div>

            {error && (
                <div
                    role="alert"
                    className="rounded-lg border border-red-500/30 bg-red-500/10 p-5"
                >
                    <p className="font-semibold text-red-300">
                        History unavailable
                    </p>
                    <p className="mt-1 text-sm text-red-200/80">
                        {error}
                    </p>
                </div>
            )}

            {!error && isLoading && entries.length === 0 && (
                <div className="rounded-lg border border-slate-800 bg-slate-900 p-8 text-sm text-slate-400">
                    Loading action history...
                </div>
            )}

            {!error && !isLoading && entries.length === 0 && (
                <div className="rounded-lg border border-slate-800 bg-slate-900 p-8">
                    <p className="font-semibold text-slate-200">
                        No actions recorded
                    </p>
                    <p className="mt-2 text-sm text-slate-500">
                        Provider actions executed through Atlas Core will
                        appear here.
                    </p>
                </div>
            )}

            {entries.length > 0 && (
                <div className="space-y-3">
                    {entries.map((entry) => (
                        <article
                            key={entry.id}
                            className="rounded-lg border border-slate-800 bg-slate-900 p-5"
                        >
                            <div className="flex flex-col justify-between gap-4 md:flex-row md:items-start">
                                <div>
                                    <div className="flex flex-wrap items-center gap-2">
                                        <h2 className="font-semibold text-slate-100">
                                            {entry.action_label}
                                        </h2>
                                        <span
                                            className={`rounded-full border px-2.5 py-1 text-xs font-medium ${statusClasses(
                                                entry.status,
                                            )}`}
                                        >
                                            {entry.status}
                                        </span>
                                        {entry.confirmed && (
                                            <span className="rounded-full border border-amber-500/30 bg-amber-500/10 px-2.5 py-1 text-xs text-amber-300">
                                                Confirmed
                                            </span>
                                        )}
                                        {entry.destructive && (
                                            <span className="rounded-full border border-red-500/30 bg-red-500/10 px-2.5 py-1 text-xs text-red-300">
                                                Destructive
                                            </span>
                                        )}
                                    </div>
                                    <p className="mt-2 text-sm text-slate-300">
                                        {entry.message}
                                    </p>
                                </div>

                                <time
                                    dateTime={entry.completed_at}
                                    className="text-xs text-slate-500"
                                >
                                    {formatTimestamp(entry.completed_at)}
                                </time>
                            </div>

                            <dl className="mt-4 grid gap-3 border-t border-slate-800 pt-4 text-xs sm:grid-cols-2 lg:grid-cols-4">
                                <div>
                                    <dt className="text-slate-500">
                                        Provider
                                    </dt>
                                    <dd className="mt-1 text-slate-300">
                                        {entry.provider_name}
                                    </dd>
                                </div>
                                <div>
                                    <dt className="text-slate-500">
                                        Duration
                                    </dt>
                                    <dd className="mt-1 text-slate-300">
                                        {entry.duration_ms.toFixed(2)} ms
                                    </dd>
                                </div>
                                <div>
                                    <dt className="text-slate-500">
                                        Parameters
                                    </dt>
                                    <dd className="mt-1 text-slate-300">
                                        {entry.parameter_names.length > 0
                                            ? entry.parameter_names.join(", ")
                                            : "None"}
                                    </dd>
                                </div>
                                <div>
                                    <dt className="text-slate-500">
                                        Request ID
                                    </dt>
                                    <dd className="mt-1 break-all font-mono text-slate-300">
                                        {entry.request_id ?? "Unavailable"}
                                    </dd>
                                </div>
                            </dl>
                        </article>
                    ))}
                </div>
            )}
        </main>
    );
}
