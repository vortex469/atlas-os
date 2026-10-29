import type {
    DiscoveryConflictState,
    DiscoveryItemEvidence,
    DiscoveryReleaseEvaluation,
    DiscoveryReleaseEvaluationStatus,
    DiscoverySourceHealth,
} from "../../types/discovery";
import { evidenceTimestamp } from "../../utils/healthPresentation";

type Props = {
    evidence: DiscoveryItemEvidence | null;
    isLoading: boolean;
    error: string | null;
    onRetry?: () => void;
};

const conflictCopy: Record<DiscoveryConflictState, { title: string; detail: string }> = {
    none: {
        title: "No conflict found",
        detail: "No supplemental release information conflicts with the catalog.",
    },
    agreement: {
        title: "Release information agrees",
        detail: "The supplemental release information matches the catalog.",
    },
    dynamic_conflict: {
        title: "Release sources disagree",
        detail: "Supplemental sources report different releases. Atlas does not choose one as correct.",
    },
    curated_conflict: {
        title: "Release report differs from the catalog",
        detail: "Supplemental information conflicts with the catalog, which remains authoritative.",
    },
};

const healthStyles: Record<DiscoverySourceHealth | "unknown", string> = {
    healthy: "border-emerald-500/30 bg-emerald-500/10 text-emerald-200",
    degraded: "border-amber-500/30 bg-amber-500/10 text-amber-200",
    unavailable: "border-red-500/30 bg-red-500/10 text-red-200",
    unknown: "border-slate-600 bg-slate-800 text-slate-300",
};

type ReleaseEvaluationTone = "positive" | "caution" | "conflict" | "neutral";

const releaseEvaluationCopy: Record<
    DiscoveryReleaseEvaluationStatus,
    { title: string; detail: string; tone: ReleaseEvaluationTone }
> = {
    up_to_date: {
        title: "Versions match",
        detail: "The latest release reported by supplemental sources matches the catalog version. This check does not recommend a change.",
        tone: "positive",
    },
    update_available: {
        title: "Newer release reported",
        detail: "A supplemental source reports a newer release than the catalog. This is information only; no change is proposed or applied.",
        tone: "positive",
    },
    baseline_ahead: {
        title: "Catalog lists a newer version",
        detail: "The catalog version is newer than the release reported by supplemental sources. This check does not recommend a change.",
        tone: "positive",
    },
    conflicted: {
        title: "Release information conflicts",
        detail: "Sources disagree, so Atlas does not choose a latest version. The catalog remains authoritative.",
        tone: "conflict",
    },
    stale_evidence: {
        title: "Release information may be out of date",
        detail: "The latest source result is old, so Atlas cannot compare it with confidence.",
        tone: "caution",
    },
    no_baseline: {
        title: "Catalog version unavailable",
        detail: "The catalog does not provide a version to compare with reported releases.",
        tone: "neutral",
    },
    no_dynamic_evidence: {
        title: "No release reports available",
        detail: "No supplemental source reports a release. Catalog information remains available and authoritative.",
        tone: "neutral",
    },
    insufficient_information: {
        title: "Versions cannot be compared",
        detail: "The available version formats cannot be compared reliably. No update is recommended.",
        tone: "caution",
    },
};

const releaseEvaluationToneStyles: Record<ReleaseEvaluationTone, string> = {
    positive: "rounded-lg border border-emerald-500/30 bg-emerald-500/10 p-4 text-emerald-100",
    caution: "rounded-lg border border-amber-500/30 bg-amber-500/10 p-4 text-amber-100",
    conflict: "rounded-lg border border-red-500/30 bg-red-500/10 p-4 text-red-100",
    neutral: "rounded-lg border border-slate-700 bg-slate-950 p-4 text-slate-100",
};

const releaseEvaluationBadgeStyles: Record<ReleaseEvaluationTone, string> = {
    positive: "rounded-full border border-emerald-500/30 bg-emerald-500/10 px-2.5 py-1 text-xs font-medium text-emerald-200",
    caution: "rounded-full border border-amber-500/30 bg-amber-500/10 px-2.5 py-1 text-xs font-medium text-amber-200",
    conflict: "rounded-full border border-red-500/30 bg-red-500/10 px-2.5 py-1 text-xs font-medium text-red-200",
    neutral: "rounded-full border border-slate-600 bg-slate-800 px-2.5 py-1 text-xs font-medium text-slate-300",
};

export function DiscoveryEvidencePanel({ evidence, isLoading, error, onRetry }: Props) {
    return (
        <section
            aria-labelledby="discovery-evidence-heading"
            className="rounded-xl border border-slate-800 bg-slate-900/70 p-5"
        >
            <h2 id="discovery-evidence-heading" className="text-lg font-semibold text-white">
                Release evidence
            </h2>
            <p className="mt-1 text-sm text-slate-400">
                Supplemental, read-only observations. Curated catalog data remains authoritative.
            </p>

            {isLoading && (
                <p role="status" aria-live="polite" className="mt-4 text-sm text-slate-300">
                    Checking release information…
                </p>
            )}

            {!isLoading && error && (
                <div role="alert" className="mt-4 rounded-lg border border-amber-500/30 bg-amber-500/10 p-4">
                    <p className="font-semibold text-amber-200">Release information unavailable</p>
                    <p className="mt-1 text-sm text-amber-200/90">Atlas could not check release information.</p>
                    <p className="mt-2 text-sm text-slate-300">
                        The catalog information is still available and unchanged.
                    </p>
                    <details className="mt-2">
                        <summary className="mc-focusable cursor-pointer text-xs text-slate-400">Technical details</summary>
                        <p className="mt-2 break-words text-xs text-slate-400">{error}</p>
                    </details>
                    {onRetry && <button type="button" onClick={onRetry} className="mt-3 rounded-lg border border-amber-300/40 px-3 py-2 text-sm font-semibold text-amber-100 focus:outline-none focus:ring-2 focus:ring-amber-200">Retry release check</button>}
                </div>
            )}

            {!isLoading && !error && evidence && (
                <div className="mt-5 space-y-5">
                    <ConflictNotice state={evidence.conflict_state} />
                    {evidence.release_evaluation && (
                        <ReleaseEvaluationNotice
                            evaluation={evidence.release_evaluation}
                        />
                    )}
                    <SourceSummary evidence={evidence} />
                    {evidence.dynamic_claims.length === 0 ? (
                        <div className="rounded-lg border border-slate-700 bg-slate-950 p-4">
                            <p className="font-medium text-slate-200">Only catalog information is available</p>
                            <p className="mt-1 text-sm text-slate-400">
                                No supplemental release reports are available. Catalog information remains available and authoritative.
                            </p>
                        </div>
                    ) : (
                        <ul aria-label="Dynamic release claims" className="space-y-3">
                            {evidence.dynamic_claims.map((claim) => (
                                <li
                                    key={`${claim.provenance.source_id}-${claim.provenance.retrieved_at}-${claim.version}`}
                                    className="rounded-lg border border-slate-700 bg-slate-950 p-4"
                                >
                                    <div className="flex flex-wrap items-center justify-between gap-2">
                                        <p className="font-semibold text-slate-100">Release {claim.version}</p>
                                        <span className={claim.freshness === "fresh"
                                            ? "rounded-full border border-emerald-500/30 bg-emerald-500/10 px-2.5 py-1 text-xs font-medium text-emerald-200"
                                            : "rounded-full border border-amber-500/30 bg-amber-500/10 px-2.5 py-1 text-xs font-medium text-amber-200"}
                                        >
                                            {claim.freshness === "fresh" ? "Current report" : "May be out of date"}
                                        </span>
                                    </div>
                                    {claim.freshness === "stale" && (
                                        <p className="mt-2 text-sm font-medium text-amber-200">
                                            This information may not reflect the latest release.
                                        </p>
                                    )}
                                    <dl className="mt-3 grid gap-2 text-sm sm:grid-cols-2">
                                        <TimeFact label="Released" value={claim.published_at} />
                                        <TimeFact label="Checked by Atlas" value={claim.provenance.retrieved_at} context={formatAge(claim.provenance.retrieved_at)} />
                                    </dl>
                                    <details className="mt-3 border-t border-slate-800 pt-3">
                                        <summary className="mc-focusable cursor-pointer text-sm font-medium text-slate-300">Source details</summary>
                                        <dl className="mt-3 grid gap-2 text-sm sm:grid-cols-2">
                                            <Fact label="Source ID" value={claim.provenance.source_id} />
                                            <Fact label="Source type" value="GitHub release information" />
                                            <Fact label="Repository" value={claim.provenance.repository} />
                                            <Fact label="Source role" value="Additional information; catalog remains authoritative" />
                                            <TimeFact label="Source data valid until" value={claim.provenance.expires_at} />
                                            <Fact label="Release record ID" value={String(claim.provenance.upstream_release_id)} />
                                        </dl>
                                    </details>
                                </li>
                            ))}
                        </ul>
                    )}
                </div>
            )}
        </section>
    );
}

function ConflictNotice({ state }: { state: DiscoveryConflictState }) {
    const copy = conflictCopy[state];
    const isConflict = state === "dynamic_conflict" || state === "curated_conflict";
    return (
        <div
            role={isConflict ? "alert" : "status"}
            className={isConflict
                ? "rounded-lg border border-amber-500/30 bg-amber-500/10 p-4 text-amber-100"
                : "rounded-lg border border-blue-500/30 bg-blue-500/10 p-4 text-blue-100"}
        >
            <p className="font-semibold">{copy.title}</p>
            <p className="mt-1 text-sm opacity-90">{copy.detail}</p>
        </div>
    );
}

function ReleaseEvaluationNotice({
    evaluation,
}: {
    evaluation: DiscoveryReleaseEvaluation;
}) {
    const copy = releaseEvaluationCopy[evaluation.status];
    const baseline = evaluation.baseline ?? null;
    const candidate = evaluation.latest_candidate ?? null;
    const isConflict = evaluation.status === "conflicted";
    return (
        <div
            role={isConflict ? "alert" : "status"}
            className={releaseEvaluationToneStyles[copy.tone]}
        >
            <div className="flex flex-wrap items-center justify-between gap-2">
                <p className="font-semibold">Version comparison</p>
                <span className={releaseEvaluationBadgeStyles[copy.tone]}>
                    {copy.title}
                </span>
            </div>
            <p className="mt-1 text-sm opacity-90">{copy.detail}</p>
            {(baseline !== null || candidate !== null) && (
                <dl className="mt-3 grid gap-2 text-sm sm:grid-cols-2">
                    {baseline !== null && (
                        <Fact
                            label="Catalog version"
                            value={baseline.version}
                        />
                    )}
                    {baseline !== null && (
                        <Fact
                            label="Catalog version source"
                            value={label(baseline.source)}
                        />
                    )}
                    {candidate !== null && (
                        <Fact label="Latest reported release" value={candidate} />
                    )}
                </dl>
            )}
        </div>
    );
}

function SourceSummary({ evidence }: { evidence: DiscoveryItemEvidence }) {
    if (evidence.source_states.length === 0) {
        return <p className="text-sm text-slate-400">No supplemental release sources are available for this item.</p>;
    }
    return (
        <ul aria-label="Discovery source health" className="grid gap-3 sm:grid-cols-2">
            {evidence.source_states.map((source) => {
                const health = source.health ?? "unknown";
                return (
                    <li key={source.source_id} className="rounded-lg border border-slate-700 bg-slate-950 p-4">
                        <p className="text-sm font-medium text-slate-200">{sourceTitle(source.source_id, evidence)}</p>
                        <div className="mt-2 flex flex-wrap gap-2">
                            <span className={`rounded-full border px-2.5 py-1 text-xs font-medium ${healthStyles[health]}`}>
                                Source: {sourceHealthLabel(health)}
                            </span>
                            <span className="rounded-full border border-slate-600 bg-slate-800 px-2.5 py-1 text-xs text-slate-300">
                                Saved evidence: {cacheStateLabel(source.cache_state)}
                            </span>
                        </div>
                        {source.cache_state === "corrupt" && <p className="mt-2 text-sm text-amber-200">Atlas ignored unreadable saved evidence.</p>}
                        <details className="mt-2">
                            <summary className="mc-focusable cursor-pointer text-xs text-slate-400">Technical details</summary>
                            <p className="mt-2 break-all text-xs text-slate-400">Source ID: {source.source_id}</p>
                        </details>
                    </li>
                );
            })}
        </ul>
    );
}

function Fact({ label: factLabel, value }: { label: string; value: string }) {
    return <div><dt className="text-xs uppercase tracking-wider text-slate-500">{factLabel}</dt><dd className="mt-1 break-words text-slate-300">{value}</dd></div>;
}

function TimeFact({ label: factLabel, value, context }: { label: string; value: string; context?: string }) {
    const timestamp = evidenceTimestamp(value);
    return <div>
        <dt className="text-xs uppercase tracking-wider text-slate-500">{factLabel} (local time)</dt>
        <dd className="mt-1 break-words text-slate-300">
            {timestamp === null
                ? "Time unavailable"
                : <><time dateTime={value}>{new Date(timestamp).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" })}</time>{context ? ` (${context})` : null}</>}
        </dd>
    </div>;
}

function label(value: string): string {
    return value.charAt(0).toUpperCase() + value.slice(1).replaceAll("_", " ");
}

function sourceTitle(sourceId: string, evidence: DiscoveryItemEvidence): string {
    const claim = evidence.dynamic_claims.find((item) => item.provenance.source_id === sourceId);
    return claim?.provenance.source_type === "github_latest_release"
        ? "GitHub release information"
        : "Release source";
}

function sourceHealthLabel(health: DiscoverySourceHealth | "unknown"): string {
    const labels: Record<DiscoverySourceHealth | "unknown", string> = {
        healthy: "Available",
        degraded: "Partly available",
        unavailable: "Unavailable",
        unknown: "Status not reported",
    };
    return labels[health];
}

function cacheStateLabel(state: DiscoveryItemEvidence["source_states"][number]["cache_state"]): string {
    const labels = {
        available: "Available",
        absent: "None found",
        corrupt: "Could not be read",
    } as const;
    return labels[state];
}

function formatAge(value: string): string {
    const time = evidenceTimestamp(value);
    if (time === null) return "age unknown";
    const now = Date.now();
    if (time > now) return "reported time is in the future";
    const elapsed = now - time;
    const hours = Math.floor(elapsed / 3_600_000);
    if (hours < 1) return "less than 1 hour ago";
    if (hours < 24) return `${hours} hour${hours === 1 ? "" : "s"} ago`;
    const days = Math.floor(hours / 24);
    return `${days} day${days === 1 ? "" : "s"} ago`;
}
