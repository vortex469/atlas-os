import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { evidenceTimestamp } from "../utils/healthPresentation";

import {
    getAtlasErrorMessage,
    getProviderActionHistoryEntry,
} from "../api/atlas";
import type {
    ActionHistoryStatus,
    ProviderActionAuditEntry,
} from "../types/actionHistory";

function formatTimestamp(timestamp: string): string {
    const parsed = evidenceTimestamp(timestamp);
    return parsed === null || parsed > Date.now() ? "Unknown time" : new Date(parsed).toLocaleString();
}

function statusClasses(status: ActionHistoryStatus): string {
    return status === "succeeded"
        ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-300"
        : "border-red-500/30 bg-red-500/10 text-red-300";
}

export function ActionHistoryDetailPage() {
    const { auditId = "" } = useParams();
    return <ActionHistoryDetail key={auditId} auditId={auditId} />;
}

function ActionHistoryDetail({ auditId }: { auditId: string }) {
    const [entry, setEntry] =
        useState<ProviderActionAuditEntry | null>(null);
    const [isLoading, setIsLoading] = useState(Boolean(auditId));
    const [error, setError] = useState<string | null>(null);
    const [readAttempt, setReadAttempt] = useState(0);
    const [copyMessage, setCopyMessage] = useState<string | null>(
        null,
    );

    useEffect(() => {
        let active = true;

        if (!auditId) {
            return () => {
                active = false;
            };
        }

        void Promise.resolve().then(() => {
            if (!active) return;
            return getProviderActionHistoryEntry(auditId)
                .then((result) => {
                    if (active) {
                        if (result.id !== auditId) {
                            setError("The returned record does not match this audit link. Try again.");
                            return;
                        }
                        setEntry(result);
                    }
                })
                .catch((requestError: unknown) => {
                    if (active) {
                        setError(
                            getAtlasErrorMessage(
                                requestError,
                                "Mission Control could not load this audit entry.",
                            ),
                        );
                    }
                })
                .finally(() => {
                    if (active) {
                        setIsLoading(false);
                    }
                });
        });

        return () => {
            active = false;
        };
    }, [auditId, readAttempt]);

    const copyLink = useCallback(async () => {
        try {
            await navigator.clipboard.writeText(
                window.location.href,
            );
            setCopyMessage("Audit link copied.");
        } catch {
            setCopyMessage(
                "Unable to copy the link. Copy it from the address bar.",
            );
        }
    }, []);
    const displayedError = auditId
        ? error
        : "The audit entry ID is missing from this URL.";

    return (
        <main className="mx-auto max-w-6xl space-y-6 p-4 [overflow-wrap:anywhere] sm:p-6">
            <header className="flex flex-col justify-between gap-4 sm:flex-row sm:items-start">
                <div>
                    <Link
                        to="/operations"
                        className="text-sm font-medium text-blue-400 transition hover:text-blue-300"
                    >
                        ← Back to action history
                    </Link>
                    <h1 className="mt-3 text-2xl font-bold text-slate-100">
                        Audit details
                    </h1>
                    <p className="mt-1 text-sm text-slate-400">
                        Recorded result of a provider action. Older records may expire under the history retention policy.
                    </p>
                </div>
                <button
                    type="button"
                    onClick={() => void copyLink()}
                    className="rounded-lg border border-slate-700 px-3 py-2 text-sm font-medium text-slate-300 transition hover:border-slate-600 hover:bg-slate-800 hover:text-white"
                >
                    Copy link
                </button>
            </header>

            {copyMessage && (
                <p role="status" className="text-sm text-slate-300">
                    {copyMessage}
                </p>
            )}

            {isLoading && (
                <div className="rounded-lg border border-slate-800 bg-slate-900 p-8 text-sm text-slate-400">
                    Loading audit details...
                </div>
            )}

            {displayedError && (
                <div
                    role="alert"
                    className="rounded-lg border border-red-500/30 bg-red-500/10 p-5"
                >
                    <p className="font-semibold text-red-300">
                        Audit entry unavailable
                    </p>
                    <p className="mt-1 text-sm text-red-200/80">
                        {displayedError}
                    </p>
                    {auditId && <button type="button" onClick={() => {
                        setEntry(null); setError(null); setIsLoading(true); setReadAttempt((attempt) => attempt + 1);
                    }} className="mc-control mc-focusable mt-4 px-4 py-2 text-sm font-semibold">Try again</button>}
                </div>
            )}

            {entry && !isLoading && !displayedError && (
                <article className="rounded-lg border border-slate-800 bg-slate-900 p-6">
                    <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-start">
                        <div>
                            <div className="flex flex-wrap items-center gap-2">
                                <h2 className="text-xl font-semibold text-slate-100">
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
                            <p className="mt-3 text-sm text-slate-400">{entry.provider_name}</p>
                            <p className="mt-3 text-sm text-slate-300">
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

                    <details className="mt-6 border-t border-slate-800 pt-4">
                        <summary className="cursor-pointer text-sm font-medium text-slate-300">Technical details</summary>
                        <dl className="mt-4 grid gap-5 text-sm sm:grid-cols-2">
                            <div>
                                <dt className="text-slate-500">Audit ID</dt>
                                <dd className="mt-1 break-all font-mono text-slate-200">
                                    {entry.id}
                                </dd>
                            </div>
                            <div>
                                <dt className="text-slate-500">
                                    Request ID
                                </dt>
                                <dd className="mt-1 break-all font-mono text-slate-200">
                                    {entry.request_id ?? "Unavailable"}
                                </dd>
                            </div>
                            <div>
                                <dt className="text-slate-500">Provider ID</dt>
                                <dd className="mt-1 break-all font-mono text-slate-200">
                                    {entry.provider_id}
                                </dd>
                            </div>
                            <div>
                                <dt className="text-slate-500">Action ID</dt>
                                <dd className="mt-1 font-mono text-slate-200">
                                    {entry.action_id}
                                </dd>
                            </div>
                            <div>
                                <dt className="text-slate-500">Started</dt>
                                <dd className="mt-1 text-slate-200">
                                    {formatTimestamp(entry.started_at)}
                                </dd>
                            </div>
                            <div>
                                <dt className="text-slate-500">Completed</dt>
                                <dd className="mt-1 text-slate-200">
                                    {formatTimestamp(entry.completed_at)}
                                </dd>
                            </div>
                            <div>
                                <dt className="text-slate-500">Duration</dt>
                                <dd className="mt-1 text-slate-200">
                                    {entry.duration_ms.toFixed(2)} ms
                                </dd>
                            </div>
                            <div>
                                <dt className="text-slate-500">
                                    Parameter names
                                </dt>
                                <dd className="mt-1 text-slate-200">
                                    {entry.parameter_names.length > 0
                                        ? entry.parameter_names.join(", ")
                                        : "None"}
                                </dd>
                            </div>
                        </dl>
                    </details>
                </article>
            )}
        </main>
    );
}
