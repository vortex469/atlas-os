import { useCallback, useEffect, useRef, useState } from "react";
import type { FormEvent } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { PlanningProgress } from "../components/PlanningProgress";

import { getAtlasErrorMessage } from "../api/atlas";
import { listExecutionCandidates } from "../api/executionCandidates";
import type {
    ExecutionCandidate,
    ExecutionCandidateListQuery,
    ExecutionCandidatePage,
    ExecutionCandidateStatusFilter,
} from "../types/executionCandidates";
import { evidenceTimestamp } from "../utils/healthPresentation";
import { compatibilityStatusLabel, executionCandidateStatusLabel } from "../utils/operatorLanguage";

const PAGE_SIZE = 25;

const statusOptions = [
    { label: "Eligible", value: "eligible" },
    { label: "Not eligible", value: "not_eligible" },
    { label: "Expired", value: "expired" },
] satisfies { label: string; value: ExecutionCandidateStatusFilter }[];

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
    status: "" | ExecutionCandidateStatusFilter;
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

type CandidateListViewState = {
    filters: FilterState;
    submittedFilters: FilterState;
    offset: number;
};

function readCandidateFilters(params: URLSearchParams, prefix = "", fallback = emptyFilters): FilterState {
    const key = (name: string) => prefix ? `${prefix}${name[0].toUpperCase()}${name.slice(1)}` : name;
    const status = params.has(key("eligibility")) ? params.get(key("eligibility")) : fallback.status;
    const category = params.has(key("category")) ? params.get(key("category")) : fallback.category;
    const intent = params.has(key("change")) ? params.get(key("change")) : fallback.intent;
    return {
        status: toStatusFilter(status ?? ""),
        category: categoryOptions.some((option) => option.value === category) ? category! : "",
        intent: intentOptions.some((option) => option.value === intent) ? intent! : "",
        sourceSubsystem: ((params.has(key("source")) ? params.get(key("source")) : fallback.sourceSubsystem) ?? "").slice(0, 200),
        targetId: ((params.has(key("target")) ? params.get(key("target")) : fallback.targetId) ?? "").slice(0, 200),
    };
}

function candidateListViewState(search: string): CandidateListViewState {
    const params = new URLSearchParams(search);
    const submittedFilters = normalizeFilters(readCandidateFilters(params));
    const draftKeys = ["eligibility", "change", "category", "source", "target"];
    const hasDraft = draftKeys.some((key) => params.has(`draft${key[0].toUpperCase()}${key.slice(1)}`));
    const filters = hasDraft
        ? readCandidateFilters(params, "draft", submittedFilters)
        : submittedFilters;
    const rawOffset = Number(params.get("offset"));
    return {
        filters,
        submittedFilters,
        offset: Number.isSafeInteger(rawOffset) && rawOffset >= 0 && rawOffset % PAGE_SIZE === 0
            ? rawOffset
            : 0,
    };
}

function candidateListSearch(currentSearch: string, state: CandidateListViewState): string {
    const params = new URLSearchParams(currentSearch);
    const applied = normalizeFilters(state.submittedFilters);
    const draft = normalizeFilters(state.filters);
    const values: Array<[string, string]> = [
        ["eligibility", applied.status],
        ["change", applied.intent],
        ["category", applied.category],
        ["source", applied.sourceSubsystem],
        ["target", applied.targetId],
        ["offset", state.offset === 0 ? "" : String(state.offset)],
    ];
    const draftValues: Array<[string, string, string]> = [
        ["draftEligibility", draft.status, applied.status],
        ["draftChange", draft.intent, applied.intent],
        ["draftCategory", draft.category, applied.category],
        ["draftSource", draft.sourceSubsystem, applied.sourceSubsystem],
        ["draftTarget", draft.targetId, applied.targetId],
    ];
    for (const [key, value] of values) {
        if (value) params.set(key, value);
        else params.delete(key);
    }
    for (const [key, value, appliedValue] of draftValues) {
        if (value !== appliedValue) params.set(key, value);
        else params.delete(key);
    }
    const serialized = params.toString();
    return serialized ? `?${serialized}` : "";
}

export function ExecutionCandidatesPage() {
    const location = useLocation();
    const navigate = useNavigate();
    const [initialViewState] = useState(() => candidateListViewState(location.search));
    const [filters, setFilters] = useState<FilterState>(initialViewState.filters);
    const [submittedFilters, setSubmittedFilters] = useState<FilterState>(initialViewState.submittedFilters);
    const [result, setResult] = useState<CandidateResult>({
        candidates: [],
        total: 0,
        offset: initialViewState.offset,
        hasMore: false,
    });
    const [isLoading, setIsLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [errorDetails, setErrorDetails] = useState<string | null>(null);
    const [hasLoadedSearch, setHasLoadedSearch] = useState(false);

    const requestGeneration = useRef(0);
    const lastRequestedQuery = useRef<CandidateRequest>({ filters: initialViewState.submittedFilters, offset: initialViewState.offset });
    const returnSearch = candidateListSearch(location.search, {
        filters,
        submittedFilters,
        offset: result.offset,
    });

    const loadCandidates = useCallback(async (nextFilters: FilterState, offset: number) => {
        const generation = ++requestGeneration.current;
        lastRequestedQuery.current = { filters: normalizeFilters(nextFilters), offset };
        setIsLoading(true);
        setError(null);
        setErrorDetails(null);

        try {
            const page = await listExecutionCandidates(toCandidateQuery(nextFilters, offset));
            if (!isDisplayableCandidatePage(page)) {
                throw new Error("The proposal response included data Mission Control could not display.");
            }
            if (generation !== requestGeneration.current) return;
            setResult({
                candidates: page.candidates,
                total: page.total,
                offset: page.offset,
                hasMore: page.has_more,
            });
            setHasLoadedSearch(true);
        } catch (requestError) {
            if (generation !== requestGeneration.current) return;
            console.error("Unable to load change proposals:", requestError);
            setError("Atlas couldn’t load the latest change proposals. Your search filters are still selected.");
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
        void Promise.resolve().then(() => { if (active) void loadCandidates(initialViewState.submittedFilters, initialViewState.offset); });
        return () => { active = false; requestGeneration.current += 1; };
    }, [initialViewState, loadCandidates]);

    useEffect(() => {
        if (returnSearch !== location.search) {
            navigate({ pathname: location.pathname, search: returnSearch }, { replace: true });
        }
    }, [location.pathname, location.search, navigate, returnSearch]);

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
    const hasUnappliedFilters = !filtersEqual(normalizeFilters(filters), submittedFilters);

    return (
        <main className="mx-auto max-w-7xl space-y-8 p-4 sm:p-8">
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
                    {hasLoadedSearch && <p className="mt-1 text-sm text-red-200/80">Previous results are hidden until this search succeeds.</p>}
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
                        <SelectFilter label="Eligibility" value={filters.status} options={statusOptions} onChange={(value) => setFilters((current) => ({ ...current, status: toStatusFilter(value) }))} />
                        <SelectFilter label="Change" value={filters.intent} options={intentOptions} onChange={(value) => setFilters((current) => ({ ...current, intent: value }))} />
                        <TextFilter label="Target" value={filters.targetId} onChange={(value) => setFilters((current) => ({ ...current, targetId: value }))} />
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
                {hasUnappliedFilters && (
                    <p role="status" className="rounded-lg border border-blue-500/30 bg-blue-500/10 px-4 py-3 text-sm text-blue-100">
                        These filter changes haven&apos;t been searched yet. Select Search proposals to update the results.
                    </p>
                )}
                <div className="flex items-center justify-between gap-4 text-sm text-slate-400">
                    {!error && (isLoading || result.candidates.length > 0) && (
                        <p role="status" aria-label="Proposal result range" aria-live="polite">
                            {isLoading ? "Loading change proposals…" : proposalResultSummary(result)}
                        </p>
                    )}
                    <div className="flex gap-2">
                        <button type="button" aria-label="Previous change proposals page" onClick={goToPreviousPage} disabled={isLoading || Boolean(error) || hasUnappliedFilters || result.offset === 0} className="rounded-lg border border-slate-700 px-3 py-2 text-sm text-slate-300 disabled:cursor-not-allowed disabled:opacity-50">
                            Previous
                        </button>
                        <button type="button" aria-label="Next change proposals page" onClick={goToNextPage} disabled={isLoading || Boolean(error) || hasUnappliedFilters || !result.hasMore} className="rounded-lg border border-slate-700 px-3 py-2 text-sm text-slate-300 disabled:cursor-not-allowed disabled:opacity-50">
                            Next
                        </button>
                    </div>
                </div>

                {!isLoading && !error && !hasUnappliedFilters && result.candidates.length === 0 && (
                    <div className="rounded-xl border border-slate-800 bg-slate-900/70 p-6 text-sm text-slate-400">
                        {result.total > 0 && result.offset > 0
                            ? "No proposals are on this page. Try the previous page."
                            : hasActiveFilters
                            ? "No change proposals match these filters."
                            : "No current change proposals."}
                    </div>
                )}

                <div className="grid gap-4">
                    {!isLoading && !error && result.candidates.map((candidate) => (
                        <CandidateCard key={candidate.id} candidate={candidate} returnSearch={returnSearch} />
                    ))}
                </div>
            </section>
        </main>
    );
}

function CandidateCard({ candidate, returnSearch }: { candidate: ExecutionCandidate; returnSearch: string }) {
    return (
        <article className="rounded-xl border border-slate-800 bg-slate-900/70 p-5">
            <div className="flex flex-wrap items-start justify-between gap-4">
                <div>
                    <Link to={{ pathname: `/execution-candidates/${encodeURIComponent(candidate.id)}`, search: returnSearch }} className="text-lg font-semibold text-blue-300 transition hover:text-blue-200 focus:outline-none focus:ring-2 focus:ring-blue-300">
                        Review {formatLabel(candidate.execution_intent)} proposal
                    </Link>
                    <p className="mt-1 text-sm text-slate-400">
                        Target: <span className="text-slate-200">{candidate.target_id}</span> · Type: {formatLabel(candidate.target_type)}
                    </p>
                </div>
                <StatusBadge status={candidate.status} expiresAt={candidate.expires_at} />
            </div>
            <dl className="mt-4 grid gap-3 text-sm sm:grid-cols-2">
                <Field label="Compatibility" value={candidate.compatibility_status ? compatibilityStatusLabel(candidate.compatibility_status) : "Not reported"} />
                {candidate.expires_at
                    ? <TimeField label="Expires" value={candidate.expires_at} />
                    : <Field label="Expires" value="No expiry" />}
            </dl>
            <details className="mt-4 border-t border-slate-800 pt-3">
                <summary className="cursor-pointer text-sm font-medium text-slate-300 focus:outline-none focus:ring-2 focus:ring-blue-300">More proposal details</summary>
                <dl className="mt-4 grid gap-3 text-sm sm:grid-cols-2 xl:grid-cols-3">
                    <Field label="Candidate ID" value={candidate.id} />
                    <Field label="Category" value={formatLabel(candidate.execution_category)} />
                    <Field label="Required approval level" value={formatLabel(candidate.required_approval_level)} />
                    <Field label="Source" value={candidate.source_subsystem} />
                    <Field label="Evidence" value={`${candidate.evidence_ids.length} reference${candidate.evidence_ids.length === 1 ? "" : "s"}`} />
                    <TimeField label="Created" value={candidate.created_at} />
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

function StatusBadge({ status, expiresAt }: { status: string; expiresAt?: string | null }) {
    return <span className="rounded-full border border-slate-700 px-3 py-1 text-sm text-slate-200">{executionCandidateStatusLabel(status, expiresAt)}</span>;
}

function Field({ label, value }: { label: string; value: string }) {
    return (
        <div>
            <dt className="text-xs uppercase tracking-wider text-slate-500">{label}</dt>
            <dd className="mt-1 break-words text-slate-200">{value}</dd>
        </div>
    );
}

function TimeField({ label, value }: { label: string; value: string }) {
    const timestamp = evidenceTimestamp(value);
    return <div>
        <dt className="text-xs uppercase tracking-wider text-slate-500">{label} (local time)</dt>
        <dd className="mt-1 break-words text-slate-200">
            {timestamp === null
                ? "Time unavailable"
                : <time dateTime={value}>{new Date(timestamp).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" })}</time>}
        </dd>
    </div>;
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

function filtersEqual(left: FilterState, right: FilterState): boolean {
    return left.status === right.status
        && left.category === right.category
        && left.intent === right.intent
        && left.sourceSubsystem === right.sourceSubsystem
        && left.targetId === right.targetId;
}

function proposalResultSummary(result: CandidateResult): string {
    const first = result.offset + 1;
    const last = result.offset + result.candidates.length;
    const noun = result.total === 1 ? "proposal" : "proposals";
    return `Showing ${first}–${last} of ${result.total} ${noun}`;
}

function toStatusFilter(value: string): FilterState["status"] {
    return value === "eligible" || value === "not_eligible" || value === "expired" ? value : "";
}

function formatLabel(value: string): string {
    return value.replaceAll("_", " ").replaceAll("-", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function isDisplayableCandidatePage(value: unknown): value is ExecutionCandidatePage {
    if (!isRecord(value) || !Array.isArray(value.candidates)
        || typeof value.total !== "number" || !Number.isSafeInteger(value.total) || value.total < 0
        || typeof value.limit !== "number" || !Number.isSafeInteger(value.limit) || value.limit <= 0
        || typeof value.offset !== "number" || !Number.isSafeInteger(value.offset) || value.offset < 0
        || typeof value.has_more !== "boolean"
        || value.total < value.candidates.length) {
        return false;
    }

    const validCandidates = value.candidates.every((candidate) => isRecord(candidate)
        && isRouteId(candidate.id)
        && (candidate.effect_kind === "repository_change" || candidate.effect_kind === "operational_action")
        && typeof candidate.source_recommendation_id === "string"
        && typeof candidate.source_subsystem === "string"
        && typeof candidate.recommendation_class === "string"
        && isOptionalNullableString(candidate.catalog_item_id)
        && typeof candidate.target_id === "string"
        && typeof candidate.target_type === "string"
        && typeof candidate.execution_category === "string"
        && typeof candidate.execution_intent === "string"
        && typeof candidate.status === "string"
        && typeof candidate.required_approval_level === "string"
        && typeof candidate.rationale === "string"
        && isStringArray(candidate.constraints)
        && isStringArray(candidate.evidence_ids)
        && isOptionalNullableString(candidate.compatibility_assessment_id)
        && isOptionalNullableString(candidate.compatibility_status)
        && isStringArray(candidate.relationship_ids)
        && typeof candidate.created_at === "string"
        && isOptionalNullableString(candidate.expires_at));
    if (!validCandidates) return false;

    return new Set(value.candidates.map((candidate) => (candidate as Record<string, unknown>).id)).size === value.candidates.length;
}

function isRecord(value: unknown): value is Record<string, unknown> {
    return typeof value === "object" && value !== null && !Array.isArray(value);
}

function isRouteId(value: unknown): value is string {
    if (typeof value !== "string" || !value.trim()) return false;
    try {
        encodeURIComponent(value);
        return true;
    } catch {
        return false;
    }
}

function isStringArray(value: unknown): value is string[] {
    return Array.isArray(value) && value.every((item) => typeof item === "string");
}

function isOptionalNullableString(value: unknown): value is string | null | undefined {
    return value === undefined || value === null || typeof value === "string";
}
