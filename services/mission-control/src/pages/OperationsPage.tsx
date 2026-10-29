import {
    useCallback,
    useEffect,
    useMemo,
    useRef,
    useState,
} from "react";
import type { ReactNode } from "react";
import { Link } from "react-router-dom";

import {
    exportProviderActionHistory,
    getAtlasErrorMessage,
    getProviderActionHistory,
    getProviderActionHistoryProviders,
    getProviderActionHistorySummary,
    pruneProviderActionHistory,
} from "../api/atlas";
import type {
    ActionHistoryExportFormat,
    ActionHistoryQuery,
    ActionHistoryStatus,
    ProviderActionAuditEntry,
    ProviderActionHistorySummary,
    ProviderActionHistoryProvider,
} from "../types/actionHistory";
import { evidenceTimestamp } from "../utils/healthPresentation";

type HistoryFilter = "all" | ActionHistoryStatus;
type OperationError = {
    kind: "export" | "prune";
    message: string;
    details: string | null;
};
const PAGE_SIZE = 25;

function formatTimestamp(value: string): ReactNode {
    const timestamp = evidenceTimestamp(value);
    return timestamp === null
        ? "Unknown time"
        : <time dateTime={value} className="text-xs text-slate-500">{new Date(timestamp).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" })}</time>;
}

function statusClasses(status: ActionHistoryStatus): string {
    return status === "succeeded"
        ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-300"
        : "border-red-500/30 bg-red-500/10 text-red-300";
}

function startOfUtcDay(date: string): string | undefined {
    return date
        ? `${date}T00:00:00.000Z`
        : undefined;
}

function endOfUtcDay(date: string): string | undefined {
    return date
        ? `${date}T23:59:59.999Z`
        : undefined;
}

export function OperationsPage() {
    const [entries, setEntries] = useState<
        ProviderActionAuditEntry[]
    >([]);
    const [filter, setFilter] = useState<HistoryFilter>("all");
    const [providerId, setProviderId] = useState("all");
    const [searchInput, setSearchInput] = useState("");
    const [search, setSearch] = useState("");
    const [completedFrom, setCompletedFrom] = useState("");
    const [completedTo, setCompletedTo] = useState("");
    const [offset, setOffset] = useState(0);
    const [total, setTotal] = useState(0);
    const [hasMore, setHasMore] = useState(false);
    const [providers, setProviders] = useState<
        ProviderActionHistoryProvider[]
    >([]);
    const [providerOptionsUnavailable, setProviderOptionsUnavailable] = useState(false);
    const [summary, setSummary] =
        useState<ProviderActionHistorySummary | null>(null);
    const [isLoading, setIsLoading] = useState(true);
    const [isExporting, setIsExporting] = useState(false);
    const [isPruning, setIsPruning] = useState(false);
    const [pruneNeedsRefresh, setPruneNeedsRefresh] = useState(false);
    const [historyError, setHistoryError] = useState<string | null>(null);
    const [operationError, setOperationError] = useState<OperationError | null>(null);
    const [operationMessage, setOperationMessage] = useState<
        string | null
    >(null);
    const requestSequence = useRef(0);

    const historyQuery = useMemo<ActionHistoryQuery>(
        () => ({
            limit: PAGE_SIZE,
            offset,
            search: search || undefined,
            status: filter === "all" ? undefined : filter,
            providerId:
                providerId === "all" ? undefined : providerId,
            completedFrom: startOfUtcDay(completedFrom),
            completedTo: endOfUtcDay(completedTo),
        }),
        [
            completedFrom,
            completedTo,
            filter,
            offset,
            providerId,
            search,
        ],
    );
    const hasActiveMoreFilters = providerId !== "all" || Boolean(completedFrom || completedTo);
    const hasUnappliedSearch = searchInput.trim() !== search;
    const hasActiveFilters = filter !== "all" || hasActiveMoreFilters || Boolean(search || searchInput.trim());
    const hasAppliedFilters = filter !== "all" || hasActiveMoreFilters || Boolean(search);

    const loadHistory = useCallback(async () => {
        const requestId = requestSequence.current + 1;
        requestSequence.current = requestId;
        setIsLoading(true);
        setHistoryError(null);
        setEntries([]);
        setSummary(null);
        setProviderOptionsUnavailable(false);

        try {
            const [historyResult, summaryResult, providersResult] = await Promise.allSettled([
                getProviderActionHistory(historyQuery),
                getProviderActionHistorySummary(),
                getProviderActionHistoryProviders(),
            ]);

            if (requestSequence.current !== requestId) return;
            if (summaryResult.status === "fulfilled") {
                setSummary(summaryResult.value);
            } else {
                console.error("Unable to load provider action history retention details:", summaryResult.reason);
            }

            if (summaryResult.status === "fulfilled" && historyResult.status === "fulfilled") {
                setPruneNeedsRefresh(false);
                setOperationError((current) => current?.kind === "prune" ? null : current);
            }

            if (providersResult.status === "fulfilled") {
                setProviders(providersResult.value);
                setProviderOptionsUnavailable(false);
            } else {
                console.error("Unable to load provider action history filters:", providersResult.reason);
                setProviderOptionsUnavailable(true);
            }

            if (historyResult.status === "rejected") {
                console.error("Unable to load provider action history:", historyResult.reason);
                setHistoryError(getAtlasErrorMessage(
                    historyResult.reason,
                    "Mission Control could not load action history.",
                ));
                return;
            }

            setEntries(historyResult.value.items);
            setTotal(historyResult.value.total);
            setHasMore(historyResult.value.has_more);
        } catch (requestError) {
            if (requestSequence.current !== requestId) {
                return;
            }

            console.error(
                "Unable to load provider action history:",
                requestError,
            );
            setHistoryError(
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
    }, [historyQuery]);

    const exportHistory = useCallback(
        async (format: ActionHistoryExportFormat) => {
            setIsExporting(true);
            setOperationError(null);
            setOperationMessage(null);

            try {
                const exportBlob =
                    await exportProviderActionHistory(
                        format,
                        historyQuery,
                    );
                const downloadUrl =
                    URL.createObjectURL(exportBlob);
                const anchor = document.createElement("a");
                anchor.href = downloadUrl;
                anchor.download = `atlas-provider-action-history.${format}`;
                document.body.appendChild(anchor);
                anchor.click();
                anchor.remove();
                URL.revokeObjectURL(downloadUrl);
                setOperationMessage(
                    `Action history exported as ${format.toUpperCase()}.`,
                );
            } catch (requestError) {
                console.error(
                    "Unable to export provider action history:",
                    requestError,
                );
                const fallback = "Mission Control could not export action history.";
                const details = getAtlasErrorMessage(requestError, fallback);
                setOperationError({
                    kind: "export",
                    message: "Action history could not be exported. Try exporting again.",
                    details: details === fallback ? null : details,
                });
            } finally {
                setIsExporting(false);
            }
        },
        [historyQuery],
    );

    const pruneHistory = useCallback(async () => {
        if (!summary || historyError || pruneNeedsRefresh) return;
        const retentionDays = summary.retention_days;
        const confirmed = window.confirm(
            `Delete history records older than ${retentionDays} days? This does not undo provider actions.`,
        );

        if (!confirmed) {
            return;
        }

        setIsPruning(true);
        setOperationError(null);
        setOperationMessage(null);

        try {
            const result = await pruneProviderActionHistory();
            setOperationMessage(
                `${result.deleted_entries} expired history ${
                    result.deleted_entries === 1 ? "entry" : "entries"
                } deleted.`,
            );
            if (offset === 0) {
                await loadHistory();
            } else {
                setOffset(0);
            }
        } catch (requestError) {
            console.error(
                "Unable to prune provider action history:",
                requestError,
            );
            const fallback = "Mission Control could not delete expired history entries.";
            const details = getAtlasErrorMessage(requestError, fallback);
            setPruneNeedsRefresh(true);
            setOperationError({
                kind: "prune",
                message: "Atlas could not confirm whether expired entries were deleted. Refresh history before trying again.",
                details: details === fallback ? null : details,
            });
        } finally {
            setIsPruning(false);
        }
    }, [historyError, loadHistory, offset, pruneNeedsRefresh, summary]);

    useEffect(() => {
        const timeoutId = window.setTimeout(() => {
            void loadHistory();
        }, 0);

        return () => {
            window.clearTimeout(timeoutId);
            requestSequence.current += 1;
        };
    }, [loadHistory]);

    return (
        <main className="mx-auto max-w-7xl space-y-6 p-4 sm:p-8">
            <header className="flex flex-col justify-between gap-4 border-b border-slate-800 pb-6 sm:flex-row sm:items-end">
                <div>
                    <p className="text-xs font-semibold uppercase tracking-[0.2em] text-cyan-400">
                        Operations
                    </p>
                    <h1 className="mt-2 text-3xl font-semibold text-slate-100">
                        Action history
                    </h1>
                    <p className="mt-2 max-w-2xl text-sm text-slate-400">
                        Completed actions and their results. Times use your
                        local time.
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
                    role="group"
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
                            aria-pressed={filter === value}
                            onClick={() => {
                                setFilter(value);
                                setOffset(0);
                            }}
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
            </div>

            <section aria-label="Action history filters" className="space-y-4 rounded-lg border border-slate-800 bg-slate-900 p-5">
                <form
                    className="max-w-2xl"
                    onSubmit={(event) => {
                        event.preventDefault();
                        setSearch(searchInput.trim());
                        setOffset(0);
                    }}
                >
                    <label
                        htmlFor="audit-search"
                        className="text-xs font-medium uppercase tracking-wider text-slate-500"
                    >
                        Action or request ID
                    </label>
                    <div className="mt-2 flex">
                        <input
                            id="audit-search"
                            type="search"
                            value={searchInput}
                            maxLength={200}
                            placeholder="Search history"
                            onChange={(event) =>
                                setSearchInput(event.target.value)
                            }
                            className="min-w-0 flex-1 rounded-l-lg border border-r-0 border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-200 outline-none placeholder:text-slate-600 focus:border-cyan-500"
                        />
                        <button
                            type="submit"
                            className="rounded-r-lg border border-cyan-500/30 bg-cyan-500/10 px-3 py-2 text-sm font-medium text-cyan-200 hover:bg-cyan-500/20"
                        >
                            Search
                        </button>
                    </div>
                    {hasUnappliedSearch && <p role="status" className="mt-2 text-sm text-blue-200">Search text has changed. Select Search to update the results.</p>}
                </form>

                <details className="rounded-lg border border-slate-800 px-4 py-3">
                    <summary className="cursor-pointer text-sm font-medium text-slate-300">
                        More filters
                        {hasActiveMoreFilters && <span className="ml-2 text-xs font-normal text-amber-200">Additional filters are applied</span>}
                    </summary>
                    {providerOptionsUnavailable && <p role="status" className="mt-4 text-sm text-amber-200">{providers.length > 0 ? "Provider options could not be refreshed. Showing the last available list." : "Provider options could not be loaded. Date filters are still available."}</p>}
                    <div className="mt-4 grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
                        <div>
                            <label
                                htmlFor="audit-provider-filter"
                                className="text-xs font-medium uppercase tracking-wider text-slate-500"
                            >
                                Provider
                            </label>
                            <select
                                id="audit-provider-filter"
                                value={providerId}
                                onChange={(event) => {
                                    setProviderId(event.target.value);
                                    setOffset(0);
                                }}
                                className="mt-2 w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-200 outline-none focus:border-cyan-500"
                            >
                                <option value="all">All providers</option>
                                {providers.map((provider) => (
                                    <option key={provider.id} value={provider.id}>{provider.name}</option>
                                ))}
                            </select>
                        </div>
                        <div>
                            <label
                                htmlFor="audit-from-filter"
                                className="text-xs font-medium uppercase tracking-wider text-slate-500"
                            >
                                From date
                            </label>
                            <input
                                id="audit-from-filter"
                                type="date"
                                aria-describedby="audit-date-filter-help"
                                value={completedFrom}
                                max={completedTo || undefined}
                                onChange={(event) => {
                                    setCompletedFrom(event.target.value);
                                    setOffset(0);
                                }}
                                className="mt-2 w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-200 outline-none focus:border-cyan-500"
                            />
                        </div>
                        <div>
                            <label
                                htmlFor="audit-to-filter"
                                className="text-xs font-medium uppercase tracking-wider text-slate-500"
                            >
                                To date
                            </label>
                            <input
                                id="audit-to-filter"
                                type="date"
                                aria-describedby="audit-date-filter-help"
                                value={completedTo}
                                min={completedFrom || undefined}
                                onChange={(event) => {
                                    setCompletedTo(event.target.value);
                                    setOffset(0);
                                }}
                                className="mt-2 w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-200 outline-none focus:border-cyan-500"
                            />
                        </div>
                        <p id="audit-date-filter-help" className="text-xs text-slate-500 sm:col-span-2 xl:col-span-3">
                            Selected dates cover full UTC days.
                        </p>
                    </div>
                </details>
                {hasActiveFilters && (
                    <div className="flex justify-end">
                        <button
                            type="button"
                            onClick={() => {
                                setFilter("all");
                                setProviderId("all");
                                setSearchInput("");
                                setSearch("");
                                setCompletedFrom("");
                                setCompletedTo("");
                                setOffset(0);
                            }}
                            className="rounded-lg border border-slate-700 px-3 py-2 text-sm font-medium text-slate-300 transition hover:border-slate-600 hover:bg-slate-800 hover:text-white"
                        >
                            Clear filters
                        </button>
                    </div>
                )}
            </section>

            <section className="space-y-4 rounded-lg border border-slate-800 bg-slate-900 p-5">
                <div className="flex flex-col justify-between gap-4 lg:flex-row lg:items-center">
                    <div>
                        <h2 className="font-semibold text-slate-100">
                            Manage history
                        </h2>
                        <p className="mt-1 text-sm text-slate-400">
                            {summary
                                ? `Atlas is keeping ${summary.entry_count} of ${summary.max_entries} entries for up to ${summary.retention_days} days.`
                                : isLoading ? "Loading retention details…" : "Retention details are unavailable."}
                        </p>
                    </div>
                </div>
                {historyError && <p role="status" className="text-sm text-amber-200">Expired entries cannot be deleted until action history loads successfully.</p>}
                {operationError && <div role="alert" className="rounded-lg border border-red-500/30 bg-red-500/10 p-3 text-sm text-red-100"><p>{operationError.message}</p>{operationError.details && <details className="mt-2"><summary className="cursor-pointer text-sm font-medium text-slate-300">Technical details</summary><p className="mt-1 break-words text-slate-400">{operationError.details}</p></details>}</div>}
                {pruneNeedsRefresh && <p role="status" className="text-sm text-amber-200">Deleting expired entries is paused until Refresh history confirms the latest records and retention details.</p>}
                <details className="rounded-lg border border-slate-800 px-4 py-3">
                    <summary className="cursor-pointer text-sm font-medium text-slate-300">Export or delete history</summary>
                    <div className="mt-4 flex flex-wrap gap-2">
                        <p className="w-full text-sm text-slate-400">Removing expired records only clears the history. It does not undo provider actions.</p>
                        <button
                            type="button"
                            onClick={() =>
                                void exportHistory("json")
                            }
                            disabled={isExporting}
                            className="rounded-lg border border-slate-700 px-3 py-2 text-sm font-medium text-slate-300 transition hover:border-slate-600 hover:bg-slate-800 hover:text-white disabled:cursor-not-allowed disabled:opacity-50"
                        >
                            Export JSON
                        </button>
                        <button
                            type="button"
                            onClick={() =>
                                void exportHistory("csv")
                            }
                            disabled={isExporting}
                            className="rounded-lg border border-slate-700 px-3 py-2 text-sm font-medium text-slate-300 transition hover:border-slate-600 hover:bg-slate-800 hover:text-white disabled:cursor-not-allowed disabled:opacity-50"
                        >
                            Export CSV
                        </button>
                        <button
                            type="button"
                            onClick={() => void pruneHistory()}
                            disabled={isPruning || !summary || Boolean(historyError) || pruneNeedsRefresh}
                            className="rounded-lg border border-amber-500/30 bg-amber-500/10 px-3 py-2 text-sm font-medium text-amber-200 transition hover:bg-amber-500/20 disabled:cursor-not-allowed disabled:opacity-50"
                        >
                            {isPruning ? "Deleting..." : "Delete expired entries"}
                        </button>
                    </div>
                </details>

                {operationMessage && (
                    <p
                        role="status"
                        className="mt-4 text-sm text-emerald-300"
                    >
                        {operationMessage}
                    </p>
                )}
            </section>

            {historyError && (
                <div
                    role="alert"
                    className="rounded-lg border border-red-500/30 bg-red-500/10 p-5"
                >
                    <p className="font-semibold text-red-300">
                        Action history unavailable
                    </p>
                    <p className="mt-1 text-sm text-red-200/80">
                        Action history could not be loaded. Refresh history to try again. This read did not run an action.
                    </p>
                    <details className="mt-3">
                        <summary className="cursor-pointer text-sm font-medium text-slate-300">Technical details</summary>
                        <p className="mt-2 break-words text-sm text-slate-400">{historyError}</p>
                    </details>
                </div>
            )}

            {!historyError && isLoading && entries.length === 0 && (
                <div className="rounded-lg border border-slate-800 bg-slate-900 p-4 text-sm text-slate-400 sm:p-8">
                    Loading action history...
                </div>
            )}

            {!historyError && !isLoading && entries.length === 0 && (
                <div className="rounded-lg border border-slate-800 bg-slate-900 p-4 sm:p-8">
                    <p className="font-semibold text-slate-200">
                        {hasAppliedFilters ? "No matching actions" : "No actions recorded"}
                    </p>
                    <p className="mt-2 text-sm text-slate-500">
                        {hasAppliedFilters
                            ? "No actions match the filters you applied. Change or clear filters to see other history."
                            : "Atlas has not recorded any actions yet."}
                    </p>
                </div>
            )}

            {!historyError && !isLoading && entries.length > 0 && (
                <>
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
                                            {entry.status === "succeeded" ? "Succeeded" : "Failed"}
                                        </span>
                                        {entry.confirmed && (
                                            <span className="rounded-full border border-amber-500/30 bg-amber-500/10 px-2.5 py-1 text-xs text-amber-300">
                                                Operator confirmed
                                            </span>
                                        )}
                                        {entry.destructive && (
                                            <span className="rounded-full border border-red-500/30 bg-red-500/10 px-2.5 py-1 text-xs text-red-300">
                                                Destructive action
                                            </span>
                                        )}
                                    </div>
                                    <p className="mt-2 text-sm text-slate-300">
                                        {entry.message}
                                    </p>
                                    <p className="mt-1 text-sm text-slate-400">
                                        Provider: {entry.provider_name}
                                    </p>
                                    <Link
                                        to={`/operations/actions/${encodeURIComponent(
                                            entry.id,
                                        )}`}
                                        className="mt-3 inline-flex text-sm font-medium text-blue-400 transition hover:text-blue-300"
                                    >
                                        View action details
                                    </Link>
                                </div>

                                {formatTimestamp(entry.completed_at)}
                            </div>

                            <details className="mt-4 border-t border-slate-800 pt-4">
                                <summary className="cursor-pointer text-sm font-medium text-slate-300">Technical details</summary>
                                <dl className="mt-4 grid gap-3 text-xs sm:grid-cols-2 lg:grid-cols-3">
                                    <div>
                                        <dt className="text-slate-500">Duration</dt>
                                        <dd className="mt-1 text-slate-300">{entry.duration_ms.toFixed(2)} ms</dd>
                                    </div>
                                    <div>
                                        <dt className="text-slate-500">Parameters</dt>
                                        <dd className="mt-1 text-slate-300">
                                            {entry.parameter_names.length > 0
                                                ? entry.parameter_names.join(", ")
                                                : "None"}
                                        </dd>
                                    </div>
                                    <div>
                                        <dt className="text-slate-500">Request ID</dt>
                                        <dd className="mt-1 break-all font-mono text-slate-300">{entry.request_id ?? "Unavailable"}</dd>
                                    </div>
                                </dl>
                            </details>
                            </article>
                        ))}
                    </div>

                    <nav
                        aria-label="Action history pagination"
                        className="flex flex-col items-center justify-between gap-3 rounded-lg border border-slate-800 bg-slate-900 p-4 sm:flex-row"
                    >
                        <p className="text-sm text-slate-400">
                            Showing {offset + 1}–
                            {Math.min(offset + entries.length, total)} of{" "}
                            {total}
                        </p>
                        <div className="flex gap-2">
                            <button
                                type="button"
                                onClick={() =>
                                    setOffset((current) =>
                                        Math.max(
                                            0,
                                            current - PAGE_SIZE,
                                        ),
                                    )
                                }
                                disabled={offset === 0 || hasUnappliedSearch}
                                className="rounded-lg border border-slate-700 px-3 py-2 text-sm font-medium text-slate-300 transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-40"
                            >
                                Previous
                            </button>
                            <button
                                type="button"
                                onClick={() =>
                                    setOffset(
                                        (current) =>
                                            current + PAGE_SIZE,
                                    )
                                }
                                disabled={!hasMore || hasUnappliedSearch}
                                className="rounded-lg border border-slate-700 px-3 py-2 text-sm font-medium text-slate-300 transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-40"
                            >
                                Next
                            </button>
                        </div>
                    </nav>
                </>
            )}
        </main>
    );
}
