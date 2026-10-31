import { useCallback, useEffect, useState, type ReactNode } from "react";
import { Link, useLocation, useParams } from "react-router-dom";

import {
    getAtlasErrorMessage,
    getProviderActionHistoryEntry,
} from "../api/atlas";
import type {
    ActionHistoryStatus,
    ProviderActionAuditEntry,
} from "../types/actionHistory";
import { evidenceTimestamp } from "../utils/healthPresentation";
import { safeText } from "../utils/safeText";

function formatTimestamp(timestamp: string): ReactNode {
    const parsed = evidenceTimestamp(timestamp);
    return parsed === null
        ? "Time unavailable"
        : <time dateTime={timestamp}>{new Date(parsed).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" })}</time>;
}

function statusClasses(status: ActionHistoryStatus): string {
    return status === "succeeded"
        ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-300"
        : "border-red-500/30 bg-red-500/10 text-red-300";
}

function statusLabel(status: ActionHistoryStatus): string {
    return status === "succeeded" ? "Succeeded" : "Failed";
}

export function ActionHistoryDetailPage() {
    const { auditId = "" } = useParams();
    return <ActionHistoryDetail key={auditId} auditId={auditId} />;
}

function ActionHistoryDetail({ auditId }: { auditId: string }) {
    const location = useLocation();
    const [entry, setEntry] =
        useState<ProviderActionAuditEntry | null>(null);
    const [isLoading, setIsLoading] = useState(Boolean(auditId));
    const [error, setError] = useState<string | null>(null);
    const [errorDetails, setErrorDetails] = useState<string | null>(null);
    const [isReadFailure, setIsReadFailure] = useState(false);
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
                            setError("This action history record does not match this link.");
                            setErrorDetails(null);
                            setIsReadFailure(false);
                            return;
                        }
                        setEntry(result);
                    }
                })
                .catch((requestError: unknown) => {
                    if (active) {
                        const fallback = "Action history read failed without additional details.";
                        const details = getAtlasErrorMessage(requestError, fallback);
                        setError("Mission Control could not load this action history entry.");
                        setErrorDetails(details === fallback ? null : details);
                        setIsReadFailure(true);
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
            setCopyMessage("Action history link copied.");
        } catch {
            setCopyMessage(
                "Unable to copy the action history link. Copy it from the address bar.",
            );
        }
    }, []);
    const displayedError = auditId
        ? error
        : "This action history link is missing its record ID.";
    const resultMessage = entry ? safeText(entry.message) : "";

    return (
        <main className="mx-auto max-w-6xl space-y-6 p-4 [overflow-wrap:anywhere] sm:p-6">
            <header className="flex flex-col justify-between gap-4 sm:flex-row sm:items-start">
                <div>
                    <Link
                        to={{ pathname: "/operations", search: location.search }}
                        className="text-sm font-medium text-blue-400 transition hover:text-blue-300"
                    >
                        ← Back to action history
                    </Link>
                    <h1 className="mt-3 text-2xl font-bold text-slate-100">
                        Action details
                    </h1>
                    <p className="mt-1 text-sm text-slate-400">
                        Recorded result of an action. Older results may no longer be available.
                    </p>
                    <p className="mt-1 text-sm text-slate-500">
                        Times below use your browser’s local time.
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
                <div role="status" aria-live="polite" className="rounded-lg border border-slate-800 bg-slate-900 p-4 text-sm text-slate-400 sm:p-8">
                    Loading action details…
                </div>
            )}

            {displayedError && (
                <div
                    role="alert"
                    className="rounded-lg border border-red-500/30 bg-red-500/10 p-5"
                >
                    <p className="font-semibold text-red-300">
                        Action record unavailable
                    </p>
                    <p className="mt-1 text-sm text-red-200/80">
                        {auditId && isReadFailure
                            ? "Atlas couldn’t load these action details. Try again to reload them; this won’t repeat the action."
                            : displayedError}
                    </p>
                    {errorDetails && <details className="mt-3"><summary className="mc-focusable cursor-pointer text-sm font-medium text-slate-300">Technical details</summary><p className="mt-2 break-words text-sm text-slate-400">{safeText(errorDetails) || "No additional details were returned."}</p></details>}
                    {auditId && <button type="button" onClick={() => {
                        setEntry(null); setError(null); setErrorDetails(null); setIsReadFailure(false); setIsLoading(true); setReadAttempt((attempt) => attempt + 1);
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
                                    {statusLabel(entry.status)}
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
                            {entry.status === "failed" ? resultMessage
                                ? <details className="mt-3"><summary className="mc-focusable cursor-pointer text-sm font-medium text-slate-300">Failure details</summary><p className="mt-2 break-words text-sm text-slate-400">{resultMessage}</p></details>
                                : <p className="mt-3 text-sm text-slate-400">No failure message was recorded.</p>
                                : <p className="mt-3 text-sm text-slate-300">{resultMessage || "No result message was recorded."}</p>}
                        </div>
                        <div className="text-xs text-slate-500">
                            Completed {formatTimestamp(entry.completed_at)}
                        </div>
                    </div>

                    <dl className="mt-6 grid gap-5 border-t border-slate-800 pt-6 text-sm sm:grid-cols-2">
                        <div>
                            <dt className="text-slate-500">Provider</dt>
                            <dd className="mt-1 text-slate-200">
                                {entry.provider_name}
                            </dd>
                        </div>
                        <div>
                            <dt className="text-slate-500">Started</dt>
                            <dd className="mt-1 text-slate-200">
                                {formatTimestamp(entry.started_at)}
                            </dd>
                        </div>
                    </dl>

                    <details className="mt-6 border-t border-slate-800 pt-4">
                        <summary className="cursor-pointer text-sm font-medium text-blue-200">
                            Technical details
                        </summary>
                        <dl className="mt-4 grid gap-5 text-sm sm:grid-cols-2">
                            <div>
                                <dt className="text-slate-500">Action record ID</dt>
                                <dd className="mt-1 break-all font-mono text-slate-200">
                                    {entry.id}
                                </dd>
                            </div>
                            <div>
                                <dt className="text-slate-500">Request ID</dt>
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
                                <dd className="mt-1 break-all font-mono text-slate-200">
                                    {entry.action_id}
                                </dd>
                            </div>
                            <div>
                                <dt className="text-slate-500">Duration</dt>
                                <dd className="mt-1 text-slate-200">
                                    {entry.duration_ms.toFixed(2)} ms
                                </dd>
                            </div>
                            <div>
                                <dt className="text-slate-500">Parameter names</dt>
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
