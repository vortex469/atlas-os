import {
    useCallback,
    useEffect,
    useMemo,
    useRef,
    useState,
} from "react";
import { Link } from "react-router-dom";
import { evidenceTimestamp } from "../utils/healthPresentation";

import { AtlasDoctorPanel } from "../components/AtlasDoctorPanel";
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

type HistoryFilter = "all" | ActionHistoryStatus;
const PAGE_SIZE = 25;

function formatTimestamp(timestamp: string): string {
    const parsed = evidenceTimestamp(timestamp);
    return parsed === null || parsed > Date.now() ? "Unknown time" : new Date(parsed).toLocaleString();
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
    const [summary, setSummary] =
        useState<ProviderActionHistorySummary | null>(null);
    const [summaryLoading, setSummaryLoading] = useState(true);
    const [providersUnavailable, setProvidersUnavailable] = useState(false);
    const [readAttempt, setReadAttempt] = useState(0);
    const [operationError, setOperationError] = useState<string | null>(null);
    const [isLoading, setIsLoading] = useState(true);
    const [isExporting, setIsExporting] = useState(false);
    const [isPruning, setIsPruning] = useState(false);
    const [error, setError] = useState<string | null>(null);
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

    const loadHistory = useCallback(async () => {
        const requestId = requestSequence.current + 1;
        requestSequence.current = requestId;
        setIsLoading(true);
        setError(null);
        setEntries([]);
        setSummary(null);
        setSummaryLoading(true);
        setProviders([]);
        setProvidersUnavailable(false);

        // These optional reads must not delay or conceal the action records.
        void getProviderActionHistorySummary().then((value) => {
            if (requestSequence.current === requestId) setSummary(value);
        }).catch(() => {
            // A missing retention policy disables cleanup, not history reads.
        }).finally(() => {
            if (requestSequence.current === requestId) setSummaryLoading(false);
        });
        void getProviderActionHistoryProviders().then((value) => {
            if (requestSequence.current === requestId) setProviders(value);
        }).catch(() => {
            if (requestSequence.current === requestId) setProvidersUnavailable(true);
        });

        try {
            const historyPage = await getProviderActionHistory(historyQuery);
            if (requestSequence.current === requestId) {
                setEntries(historyPage.items);
                setTotal(historyPage.total);
                setHasMore(historyPage.has_more);
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
                anchor.download = `atlas-action-history.${format}`;
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
                setOperationError(
                    getAtlasErrorMessage(
                        requestError,
                        "Mission Control could not export action history.",
                    ),
                );
            } finally {
                setIsExporting(false);
            }
        },
        [historyQuery],
    );

    const pruneHistory = useCallback(async () => {
        if (!summary || isLoading || error) return;
        const retentionDays = summary.retention_days;
        const confirmed = window.confirm(
            `Delete audit entries older than ${retentionDays} days?`,
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
                `${result.deleted_entries} expired audit ${
                    result.deleted_entries === 1
                        ? "entry"
                        : "entries"
                } pruned.`,
            );
            setOffset(0);
            setReadAttempt((attempt) => attempt + 1);
        } catch (requestError) {
            console.error(
                "Unable to prune provider action history:",
                requestError,
            );
            setOperationError(
                getAtlasErrorMessage(
                    requestError,
                    "Mission Control could not prune action history.",
                ),
            );
        } finally {
            setIsPruning(false);
        }
    }, [error, isLoading, summary]);

    useEffect(() => {
        const timeoutId = window.setTimeout(() => {
            void loadHistory();
        }, 0);

        return () => {
            window.clearTimeout(timeoutId);
            requestSequence.current += 1;
        };
    }, [loadHistory, readAttempt]);

    function clearFilters() {
        setFilter("all");
        setProviderId("all");
        setSearchInput("");
        setSearch("");
        setCompletedFrom("");
        setCompletedTo("");
        setOffset(0);
    }
    const hasFilters = filter !== "all" || providerId !== "all" || Boolean(search || completedFrom || completedTo);

    return (
        <main className="mx-auto max-w-7xl space-y-6 p-4 [overflow-wrap:anywhere] sm:p-6">
            <header className="flex flex-col justify-between gap-4 border-b border-slate-800 pb-6 sm:flex-row sm:items-end">
                <div>
                    <p className="text-xs font-semibold uppercase tracking-[0.2em] text-cyan-400">
                        Operations
                    </p>
                    <h1 className="mt-2 text-3xl font-semibold text-slate-100">
                        Action History
                    </h1>
                    <p className="mt-2 max-w-2xl text-sm text-slate-400">
                        Recorded provider actions and their results from Atlas Core.
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
                            onClick={() => {
                                setFilter(value);
                                setOffset(0);
                            }}
                            aria-pressed={filter === value}
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

            <details className="rounded-lg border border-slate-800 bg-slate-900 p-4">
                <summary className="cursor-pointer text-sm font-medium text-slate-200">Search and filters</summary>
                <p className="mt-3 text-sm text-slate-400">Dates use UTC. Results below show the current search.</p>
                {providersUnavailable && <p role="status" className="mt-3 text-sm text-amber-200">Provider choices are unavailable. Existing filters still apply. Refresh history to try again.</p>}
                <section className="mt-4 grid gap-4 sm:grid-cols-2 xl:grid-cols-5">
                <form
                    className="sm:col-span-2 xl:col-span-1"
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
                </form>

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
                        {providerId !== "all" && !providers.some((provider) => provider.id === providerId) && <option value={providerId}>Selected provider ({providerId})</option>}
                        {providers.map((provider) => (
                            <option
                                key={provider.id}
                                value={provider.id}
                            >
                                {provider.name}
                            </option>
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
                        value={completedTo}
                        min={completedFrom || undefined}
                        onChange={(event) => {
                            setCompletedTo(event.target.value);
                            setOffset(0);
                        }}
                        className="mt-2 w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-200 outline-none focus:border-cyan-500"
                    />
                </div>

                <div className="flex items-end">
                    <button
                        type="button"
                        onClick={clearFilters}
                        disabled={
                            filter === "all" &&
                            providerId === "all" &&
                            !search &&
                            !searchInput &&
                            !completedFrom &&
                            !completedTo
                        }
                        className="w-full rounded-lg border border-slate-700 px-3 py-2 text-sm font-medium text-slate-300 transition hover:border-slate-600 hover:bg-slate-800 hover:text-white disabled:cursor-not-allowed disabled:opacity-40"
                    >
                        Clear filters
                    </button>
                </div>
                </section>
            </details>

            {hasFilters && <div className="flex flex-wrap items-center gap-3 text-sm text-slate-300">
                <p role="status">Filters are active.</p>
                <button type="button" onClick={clearFilters} className="rounded-lg border border-slate-700 px-3 py-2 text-sm text-slate-200">Show all actions</button>
            </div>}

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
                        {offset > 0 ? "No actions on this page" : hasFilters ? "No matching actions" : "No actions recorded"}
                    </p>
                    <p className="mt-2 text-sm text-slate-500">
                        {offset > 0 ? "The history may have changed. Go back to an earlier page."
                            : hasFilters ? "Try a different search or clear the filters."
                            : "Provider actions executed through Atlas Core will appear here."}
                    </p>
                    {offset > 0 && <button type="button" onClick={() => setOffset((current) => Math.max(0, current - PAGE_SIZE))} className="mt-3 mr-3 rounded-lg border border-slate-700 px-3 py-2 text-sm text-slate-200">Previous page</button>}
                </div>
            )}

            {!error && !isLoading && entries.length > 0 && (
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
                                            {entry.status}
                                        </span>
                                        {entry.confirmed && (
                                            <span className="rounded-full border border-amber-500/30 bg-amber-500/10 px-2.5 py-1 text-xs text-amber-300">
                                                Request confirmed
                                            </span>
                                        )}
                                        {entry.destructive && (
                                            <span className="rounded-full border border-red-500/30 bg-red-500/10 px-2.5 py-1 text-xs text-red-300">
                                                Destructive
                                            </span>
                                        )}
                                    </div>
                                    <p className="mt-2 text-sm text-slate-400">{entry.provider_name}</p>
                                    <p className="mt-2 text-sm text-slate-300">
                                        {entry.message}
                                    </p>
                                    <Link
                                        to={`/operations/actions/${encodeURIComponent(
                                            entry.id,
                                        )}`}
                                        className="mt-3 inline-flex text-sm font-medium text-blue-400 transition hover:text-blue-300"
                                    >
                                        View audit details
                                    </Link>
                                </div>

                                <time
                                    dateTime={entry.completed_at}
                                    className="text-xs text-slate-500"
                                >
                                    {formatTimestamp(entry.completed_at)}
                                </time>
                            </div>

                            <details className="mt-4 border-t border-slate-800 pt-3">
                                <summary className="cursor-pointer text-sm text-slate-300">Technical details</summary>
                                <dl className="mt-3 grid gap-3 text-xs sm:grid-cols-2 lg:grid-cols-4">
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
                                disabled={offset === 0}
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
                                disabled={!hasMore}
                                className="rounded-lg border border-slate-700 px-3 py-2 text-sm font-medium text-slate-300 transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-40"
                            >
                                Next
                            </button>
                        </div>
                    </nav>
                </>
            )}
            <details className="rounded-lg border border-slate-800 bg-slate-900 p-4">
                <summary className="cursor-pointer text-sm font-medium text-slate-200">Export and cleanup</summary>
                <section className="mt-4">
                <div className="flex flex-col justify-between gap-4 lg:flex-row lg:items-center">
                    <div>
                        <h2 className="font-semibold text-slate-100">
                            History tools
                        </h2>
                        <p className="mt-1 text-sm text-slate-400">
                            {summary
                                ? `${summary.entry_count} of ${summary.max_entries} entries retained for ${summary.retention_days} days.`
                                : summaryLoading ? "Loading retention policy..." : "Retention policy unavailable."}
                        </p>
                    </div>

                    <div className="flex flex-wrap gap-2">
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
                            disabled={isPruning || !summary || isLoading || error !== null}
                            className="rounded-lg border border-amber-500/30 bg-amber-500/10 px-3 py-2 text-sm font-medium text-amber-200 transition hover:bg-amber-500/20 disabled:cursor-not-allowed disabled:opacity-50"
                        >
                            {isPruning
                                ? "Pruning..."
                                : "Prune expired"}
                        </button>
                    </div>
                </div>

                {operationError && <p role="alert" className="mt-4 text-sm text-red-200">{operationError}</p>}
                {operationMessage && (
                    <p
                        role="status"
                        className="mt-4 text-sm text-emerald-300"
                    >
                        {operationMessage}
                    </p>
                )}
                </section>
            </details>

            <details className="rounded-lg border border-slate-800 bg-slate-900 p-4">
                <summary className="cursor-pointer text-sm font-medium text-slate-200">Check Atlas health</summary>
                <div className="mt-4"><AtlasDoctorPanel /></div>
            </details>

        </main>
    );
}
