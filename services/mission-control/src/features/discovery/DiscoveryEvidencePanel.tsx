import type {
    DiscoveryConflictState,
    DiscoveryItemEvidence,
    DiscoverySourceHealth,
} from "../../types/discovery";

type Props = {
    evidence: DiscoveryItemEvidence | null;
    isLoading: boolean;
    error: string | null;
};

const conflictCopy: Record<DiscoveryConflictState, { title: string; detail: string }> = {
    none: {
        title: "No conflict",
        detail: "No conflicting dynamic release claims are present.",
    },
    agreement: {
        title: "Sources agree",
        detail: "The supplemental release evidence agrees with the curated release claim.",
    },
    dynamic_conflict: {
        title: "Dynamic source conflict",
        detail: "Supplemental sources report different values. No dynamic value is selected as authoritative.",
    },
    curated_conflict: {
        title: "Curated evidence conflict",
        detail: "Supplemental evidence differs from the curated release claim. Curated data remains authoritative.",
    },
};

const healthStyles: Record<DiscoverySourceHealth | "unknown", string> = {
    healthy: "border-emerald-500/30 bg-emerald-500/10 text-emerald-200",
    degraded: "border-amber-500/30 bg-amber-500/10 text-amber-200",
    unavailable: "border-red-500/30 bg-red-500/10 text-red-200",
    unknown: "border-slate-600 bg-slate-800 text-slate-300",
};

export function DiscoveryEvidencePanel({ evidence, isLoading, error }: Props) {
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
                    Loading source evidence…
                </p>
            )}

            {!isLoading && error && (
                <div role="alert" className="mt-4 rounded-lg border border-amber-500/30 bg-amber-500/10 p-4">
                    <p className="font-semibold text-amber-200">Dynamic evidence unavailable</p>
                    <p className="mt-1 text-sm text-amber-200/90">{error}</p>
                    <p className="mt-2 text-sm text-slate-300">
                        Showing the curated catalog only. No authoritative Discovery data was lost or changed.
                    </p>
                </div>
            )}

            {!isLoading && !error && evidence && (
                <div className="mt-5 space-y-5">
                    <ConflictNotice state={evidence.conflict_state} />
                    <SourceSummary evidence={evidence} />
                    {evidence.dynamic_claims.length === 0 ? (
                        <div className="rounded-lg border border-slate-700 bg-slate-950 p-4">
                            <p className="font-medium text-slate-200">Curated catalog only</p>
                            <p className="mt-1 text-sm text-slate-400">
                                No usable dynamic claims are available. Curated data remains available and authoritative.
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
                                            {claim.freshness === "fresh" ? "Fresh" : "Stale"}
                                        </span>
                                    </div>
                                    {claim.freshness === "stale" && (
                                        <p className="mt-2 text-sm font-medium text-amber-200">
                                            Stale evidence may not describe the current upstream release.
                                        </p>
                                    )}
                                    <dl className="mt-3 grid gap-2 text-sm sm:grid-cols-2">
                                        <Fact label="Source" value={claim.provenance.source_id} />
                                        <Fact label="Source type" value="GitHub latest release" />
                                        <Fact label="Repository" value={claim.provenance.repository} />
                                        <Fact label="Trust" value="Supplemental" />
                                        <Fact label="Published" value={formatTimestamp(claim.published_at)} />
                                        <Fact label="Retrieved" value={`${formatTimestamp(claim.provenance.retrieved_at)} (${formatAge(claim.provenance.retrieved_at)})`} />
                                        <Fact label="Freshness expires" value={formatTimestamp(claim.provenance.expires_at)} />
                                        <Fact label="Upstream release ID" value={String(claim.provenance.upstream_release_id)} />
                                    </dl>
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

function SourceSummary({ evidence }: { evidence: DiscoveryItemEvidence }) {
    if (evidence.source_states.length === 0) {
        return <p className="text-sm text-slate-400">No dynamic sources are mapped to this catalog item.</p>;
    }
    return (
        <ul aria-label="Discovery source health" className="grid gap-3 sm:grid-cols-2">
            {evidence.source_states.map((source) => {
                const health = source.health ?? "unknown";
                return (
                    <li key={source.source_id} className="rounded-lg border border-slate-700 bg-slate-950 p-4">
                        <p className="break-all text-sm font-medium text-slate-200">{source.source_id}</p>
                        <div className="mt-2 flex flex-wrap gap-2">
                            <span className={`rounded-full border px-2.5 py-1 text-xs font-medium ${healthStyles[health]}`}>
                                Health: {label(health)}
                            </span>
                            <span className="rounded-full border border-slate-600 bg-slate-800 px-2.5 py-1 text-xs text-slate-300">
                                Cache: {label(source.cache_state)}
                            </span>
                        </div>
                        {source.cache_state === "corrupt" && <p className="mt-2 text-sm text-amber-200">Corrupt cached evidence was excluded.</p>}
                        {source.cache_state === "absent" && <p className="mt-2 text-sm text-slate-400">No cached evidence is available.</p>}
                    </li>
                );
            })}
        </ul>
    );
}

function Fact({ label: factLabel, value }: { label: string; value: string }) {
    return <div><dt className="text-xs uppercase tracking-wider text-slate-500">{factLabel}</dt><dd className="mt-1 break-words text-slate-300">{value}</dd></div>;
}

function label(value: string): string {
    return value.charAt(0).toUpperCase() + value.slice(1).replaceAll("_", " ");
}

function formatTimestamp(value: string): string {
    const parsed = new Date(value);
    return Number.isNaN(parsed.getTime()) ? "Unknown" : parsed.toLocaleString();
}

function formatAge(value: string): string {
    const time = new Date(value).getTime();
    if (Number.isNaN(time)) return "age unknown";
    const elapsed = Math.max(0, Date.now() - time);
    const hours = Math.floor(elapsed / 3_600_000);
    if (hours < 1) return "less than 1 hour ago";
    if (hours < 24) return `${hours} hour${hours === 1 ? "" : "s"} ago`;
    const days = Math.floor(hours / 24);
    return `${days} day${days === 1 ? "" : "s"} ago`;
}
