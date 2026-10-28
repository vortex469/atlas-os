import { useCallback, useEffect, useRef, useState } from "react";
import type { FormEvent } from "react";
import { Link } from "react-router-dom";
import { PlanningProgress } from "../components/PlanningProgress";

import { getAtlasErrorMessage } from "../api/atlas";
import { listExecutionCandidates } from "../api/executionCandidates";
import type {
    ExecutionCandidate,
    ExecutionCandidateListQuery,
} from "../types/executionCandidates";
import { compatibilityStatusLabel } from "../utils/operatorLanguage";

const PAGE_SIZE = 25;

const statusOptions = [
    { label: "Eligible", value: "eligible" },
    { label: "Not eligible", value: "not_eligible" },
    { label: "Expired", value: "expired" },
];

const categoryOptions = [
    { label: "Update", value: "update" },
    { label: "Restart", value: "restart" },
];

const intentOptions = [
    { label: "Update compose stack", value: "update-compose-stack" },
    { label: "Restart service", value: "restart-service" },
    { label: "Update container image", value: "update-container-image" },
];

type FilterState = {
    status: string;
    category: string;
    intent: string;
    sourceSubsystem: string;
    targetId: string;
};

const emptyFilters: FilterState = {
    status: "",
    category: "",
    intent: "",
    sourceSubsystem: "",
    targetId: "",
};

type CandidateResult = {
    candidates: ExecutionCandidate[];
    total: number;
    offset: number;
    hasMore: boolean;
};

type CandidateRequest = {
    filters: FilterState;
    offset: number;
};

export function ExecutionCandidatesPage() {
    const [filters, setFilters] = useState<FilterState>(emptyFilters);
    const [submittedFilters, setSubmittedFilters] = useState<FilterState>(emptyFilters);
    const [result, setResult] = useState<CandidateResult>({
        candidates: [],
        total: 0,
        offset: 0,
        hasMore: false,
    });
    const [isLoading, setIsLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [errorDetails, setErrorDetails] = useState<string | null>(null);

    const requestGeneration = useRef(0);
    const lastRequestedQuery = useRef<CandidateRequest>({ filters: emptyFilters, offset: 0 });

    const loadCandidates = useCallback(async (nextFilters: FilterState, offset: number) => {
        const generation = ++requestGeneration.current;
        lastRequestedQuery.current = { filters: normalizeFilters(nextFilters), offset };
        setIsLoading(true);
        setError(null);
        setErrorDetails(null);

        try {
            const page = await listExecutionCandidates(toCandidateQuery(nextFilters, offset));
            if (generation !== requestGeneration.current) return;
            setResult({
                candidates: page.candidates,
                total: page.total,
                offset: page.offset,
                hasMore: page.has_more,
            });
        } catch (requestError) {
            if (generation !== requestGeneration.current) return;
            console.error("Unable to load change proposals:", requestError);
            setError("Mission Control could not load the latest proposal results.");
            setErrorDetails(getAtlasErrorMessage(
                requestError,
                "Proposal list request failed without additional details.",
            ));
        } finally {
            if (generation === requestGeneration.current) setIsLoading(false);
        }
    }, []);

    useEffect(() => {
        let active = true;
        void Promise.resolve().then(() => { if (active) void loadCandidates(emptyFilters, 0); });
        return () => { active = false; requestGeneration.current += 1; };
    }, [loadCandidates]);

    function submitFilters(event: FormEvent<HTMLFormElement>) {
        event.preventDefault();
        const normalized = normalizeFilters(filters);
        setSubmittedFilters(normalized);
        void loadCandidates(normalized, 0);
    }

    function clearFilters() {
        setFilters(emptyFilters);
        setSubmittedFilters(emptyFilters);
        void loadCandidates(emptyFilters, 0);
    }

    function goToPreviousPage() {
        void loadCandidates(submittedFilters, Math.max(0, result.offset - PAGE_SIZE));
    }

    function goToNextPage() {
        void loadCandidates(submittedFilters, result.offset + PAGE_SIZE);
    }

    function retryLastSearch() {
        void loadCandidates(lastRequestedQuery.current.filters, lastRequestedQuery.current.offset);
    }

    const hasActiveFilters = Object.values(submittedFilters).some((value) => value.length > 0);
    const hasAdvancedFilters = submittedFilters.category.length > 0 || submittedFilters.sourceSubsystem.length > 0;

    return (
        <main className="mx-auto max-w-7xl space-y-8 p-8">
            <header className="space-y-4">
                <div>
                    <h1 className="mt-3 text-3xl font-bold text-white">
                        Change proposals
                    </h1>
                    <p className="mt-3 max-w-3xl text-sm leading-6 text-slate-400">
                        Find a proposal and open it to review or start planning. Planning
                        and approval are separate steps.
                    </p>
                </div>
                <PlanningProgress current="Execution Candidate" />
            </header>

            {error && (
                <div role="alert" className="rounded-xl border border-red-500/30 bg-red-500/10 p-5">
                    <p className="font-semibold text-red-300">Change proposals unavailable</p>
                    <p className="mt-1 text-sm text-red-200/80">{error}</p>
                    {errorDetails && <details className="mt-3"><summary className="cursor-pointer text-sm font-medium text-slate-300 focus:outline-none focus:ring-2 focus:ring-blue-300">Technical details</summary><p className="mt-2 break-words text-sm text-slate-400">{errorDetails}</p></details>}
                    <button type="button" onClick={retryLastSearch} disabled={isLoading} className="mt-4 rounded-lg border border-red-300/40 px-3 py-2 text-sm font-semibold text-red-100 transition hover:bg-red-500/10 focus:outline-none focus:ring-2 focus:ring-red-200 disabled:cursor-not-allowed disabled:opacity-50">
                        Retry search
                    </button>
                </div>
            )}

            <section className="rounded-xl border border-slate-800 bg-slate-900/70 p-5">
                <form
                    aria-label="Filter change proposals"
                    className="space-y-4"
                    onSubmit={submitFilters}
                >
                    <div className="grid gap-4 lg:grid-cols-[repeat(3,minmax(0,1fr))_auto]">
                        <SelectFilter label="Eligibility" value={filters.status} options={statusOptions} onChange={(value) => setFilters((current) => ({ ...current, status: value }))} />
                        <SelectFilter label="Change" value={filters.intent} options={intentOptions} onChange={(value) => setFilters((current) => ({ ...current, intent: value }))} />
                        <TextFilter label="Target ID" value={filters.targetId} onChange={(value) => setFilters((current) => ({ ...current, targetId: value }))} />
                        <div className="flex items-end gap-2">
                            <button type="submit" className="rounded-lg bg-blue-500 px-4 py-2 text-sm font-semibold text-white transition hover:bg-blue-400 focus:outline-none focus:ring-2 focus:ring-blue-300">
                                Search proposals
                            </button>
                            <button type="button" onClick={clearFilters} className="rounded-lg border border-slate-700 px-4 py-2 text-sm font-semibold text-slate-300 transition hover:border-slate-500 hover:text-white focus:outline-none focus:ring-2 focus:ring-blue-300">
                                Reset filters
                            </button>
                        </div>
                    </div>
                    <details className="rounded-lg border border-slate-800 px-4 py-3">
                        <summary className="cursor-pointer text-sm font-medium text-slate-300 focus:outline-none focus:ring-2 focus:ring-blue-300">
                            More filters{hasAdvancedFilters ? " · active" : ""}
                        </summary>
                        <div className="mt-4 grid gap-4 sm:grid-cols-2">
                            <SelectFilter label="Category" value={filters.category} options={categoryOptions} onChange={(value) => setFilters((current) => ({ ...current, category: value }))} />
                            <TextFilter label="Source" value={filters.sourceSubsystem} onChange={(value) => setFilters((current) => ({ ...current, sourceSubsystem: value }))} />
                        </div>
                    </details>
                </form>
            </section>

            <section aria-label="Change proposal results" className="space-y-4">
                <div className="flex items-center justify-between gap-4 text-sm text-slate-400">
                    {!error && <p>{isLoading ? "Loading change proposals…" : `${result.total} proposal${result.total === 1 ? "" : "s"}`}</p>}
                    <div className="flex gap-2">
                        <button type="button" aria-label="Previous change proposals page" onClick={goToPreviousPage} disabled={isLoading || Boolean(error) || result.offset === 0} className="rounded-lg border border-slate-700 px-3 py-2 text-sm text-slate-300 disabled:cursor-not-allowed disabled:opacity-50">
                            Previous
                        </button>
                        <button type="button" aria-label="Next change proposals page" onClick={goToNextPage} disabled={isLoading || Boolean(error) || !result.hasMore} className="rounded-lg border border-slate-700 px-3 py-2 text-sm text-slate-300 disabled:cursor-not-allowed disabled:opacity-50">
                            Next
                        </button>
                    </div>
                </div>

                {!isLoading && !error && result.candidates.length === 0 && (
                    <div className="rounded-xl border border-slate-800 bg-slate-900/70 p-6 text-sm text-slate-400">
                        {hasActiveFilters
                            ? "No change proposals match these filters."
                            : "No current change proposals."}
                    </div>
                )}

                <div className="grid gap-4">
                    {!isLoading && !error && result.candidates.map((candidate) => (
                        <CandidateCard key={candidate.id} candidate={candidate} />
                    ))}
                </div>
            </section>
        </main>
    );
}

function CandidateCard({ candidate }: { candidate: ExecutionCandidate }) {
    return (
        <article className="rounded-xl border border-slate-800 bg-slate-900/70 p-5">
            <div className="flex flex-wrap items-start justify-between gap-4">
                <div>
                    <Link to={`/execution-candidates/${encodeURIComponent(candidate.id)}`} className="text-lg font-semibold text-blue-300 transition hover:text-blue-200 focus:outline-none focus:ring-2 focus:ring-blue-300">
                        Review {formatLabel(candidate.execution_intent)} proposal
                    </Link>
                    <p className="mt-1 text-sm text-slate-400">
                        Target: <span className="text-slate-200">{candidate.target_id}</span> ({formatLabel(candidate.target_type)})
                    </p>
                </div>
                <StatusBadge status={candidate.status} />
            </div>
            <dl className="mt-4 grid gap-3 text-sm sm:grid-cols-2">
                <Field label="Compatibility" value={candidate.compatibility_status ? compatibilityStatusLabel(candidate.compatibility_status) : "Not reported"} />
                <Field label="Expires" value={candidate.expires_at ? formatTimestamp(candidate.expires_at) : "No expiry"} />
            </dl>
            <details className="mt-4 border-t border-slate-800 pt-3">
                <summary className="cursor-pointer text-sm font-medium text-slate-300 focus:outline-none focus:ring-2 focus:ring-blue-300">More proposal details</summary>
                <dl className="mt-4 grid gap-3 text-sm sm:grid-cols-2 xl:grid-cols-3">
                    <Field label="Candidate ID" value={candidate.id} />
                    <Field label="Category" value={formatLabel(candidate.execution_category)} />
                    <Field label="Required approval level" value={formatLabel(candidate.required_approval_level)} />
                    <Field label="Source" value={candidate.source_subsystem} />
                    <Field label="Evidence" value={`${candidate.evidence_ids.length} reference${candidate.evidence_ids.length === 1 ? "" : "s"}`} />
                    <Field label="Created" value={formatTimestamp(candidate.created_at)} />
                </dl>
            </details>
        </article>
    );
}

function SelectFilter({ label, value, options, onChange }: { label: string; value: string; options: { label: string; value: string }[]; onChange: (value: string) => void }) {
    return (
        <label className="space-y-2 text-sm text-slate-300">
            <span>{label}</span>
            <select value={value} onChange={(event) => onChange(event.target.value)} className="w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-100 outline-none transition focus:border-blue-400 focus:ring-2 focus:ring-blue-500/30">
                <option value="">Any</option>
                {options.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
            </select>
        </label>
    );
}

function TextFilter({ label, value, onChange }: { label: string; value: string; onChange: (value: string) => void }) {
    return (
        <label className="space-y-2 text-sm text-slate-300">
            <span>{label}</span>
            <input value={value} onChange={(event) => onChange(event.target.value)} className="w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-100 outline-none transition focus:border-blue-400 focus:ring-2 focus:ring-blue-500/30" />
        </label>
    );
}

function StatusBadge({ status }: { status: string }) {
    return <span className="rounded-full border border-slate-700 px-3 py-1 text-sm text-slate-200">{statusText(status)}</span>;
}

function Field({ label, value }: { label: string; value: string }) {
    return (
        <div>
            <dt className="text-xs uppercase tracking-wider text-slate-500">{label}</dt>
            <dd className="mt-1 break-words text-slate-200">{value}</dd>
        </div>
    );
}

function toCandidateQuery(filters: FilterState, offset: number): ExecutionCandidateListQuery {
    const normalized = normalizeFilters(filters);
    return {
        status: normalized.status || undefined,
        category: normalized.category || undefined,
        intent: normalized.intent || undefined,
        sourceSubsystem: normalized.sourceSubsystem || undefined,
        targetId: normalized.targetId || undefined,
        limit: PAGE_SIZE,
        offset,
    };
}

function normalizeFilters(filters: FilterState): FilterState {
    return {
        status: filters.status,
        category: filters.category,
        intent: filters.intent,
        sourceSubsystem: filters.sourceSubsystem.trim(),
        targetId: filters.targetId.trim(),
    };
}

function statusText(status: string): string {
    if (status === "eligible") return "Eligible for planning consideration";
    if (status === "not_eligible") return "Not eligible for planning";
    if (status === "expired") return "Expired";
    return formatLabel(status);
}

function formatLabel(value: string): string {
    return value.replaceAll("_", " ").replaceAll("-", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function formatTimestamp(value: string): string {
    const date = new Date(value);
    return Number.isNaN(date.getTime()) ? value : date.toLocaleString();
}
