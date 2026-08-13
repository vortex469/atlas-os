import { useCallback, useEffect, useState } from "react";
import type { FormEvent } from "react";
import { Link } from "react-router-dom";

import { getAtlasErrorMessage } from "../api/atlas";
import { listExecutionCandidates } from "../api/executionCandidates";
import type {
    ExecutionCandidate,
    ExecutionCandidateListQuery,
} from "../types/executionCandidates";

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

    const loadCandidates = useCallback(async (nextFilters: FilterState, offset: number) => {
        setIsLoading(true);
        setError(null);

        try {
            const page = await listExecutionCandidates(toCandidateQuery(nextFilters, offset));
            setResult({
                candidates: page.candidates,
                total: page.total,
                offset: page.offset,
                hasMore: page.has_more,
            });
        } catch (requestError) {
            console.error("Unable to load execution candidates:", requestError);
            setError(
                getAtlasErrorMessage(
                    requestError,
                    "Mission Control could not load execution candidates.",
                ),
            );
        } finally {
            setIsLoading(false);
        }
    }, []);

    useEffect(() => {
        let cancelled = false;

        listExecutionCandidates(toCandidateQuery(emptyFilters, 0))
            .then((page) => {
                if (cancelled) {
                    return;
                }
                setResult({
                    candidates: page.candidates,
                    total: page.total,
                    offset: page.offset,
                    hasMore: page.has_more,
                });
            })
            .catch((requestError: unknown) => {
                if (cancelled) {
                    return;
                }
                console.error("Unable to load execution candidates:", requestError);
                setError(
                    getAtlasErrorMessage(
                        requestError,
                        "Mission Control could not load execution candidates.",
                    ),
                );
            })
            .finally(() => {
                if (!cancelled) {
                    setIsLoading(false);
                }
            });

        return () => {
            cancelled = true;
        };
    }, []);

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

    const hasActiveFilters = Object.values(submittedFilters).some((value) => value.length > 0);

    return (
        <main className="mx-auto max-w-7xl space-y-8 p-8">
            <header className="space-y-4">
                <div>
                    <p className="text-xs uppercase tracking-[0.3em] text-blue-300">
                        Execution Candidates
                    </p>
                    <h1 className="mt-3 text-3xl font-bold text-white">
                        Candidate planning intake
                    </h1>
                    <p className="mt-3 max-w-3xl text-sm leading-6 text-slate-400">
                        Browse current execution candidates from Atlas Core. This view is
                        read-only except for asking Atlas Agent to create or reuse a
                        planning-only session. It does not execute, approve, install, or
                        apply changes.
                    </p>
                </div>
                <WorkflowRail activeStep="Execution Candidate" />
            </header>

            {error && (
                <div role="alert" className="rounded-xl border border-red-500/30 bg-red-500/10 p-5">
                    <p className="font-semibold text-red-300">Execution candidates unavailable</p>
                    <p className="mt-1 text-sm text-red-200/80">{error}</p>
                </div>
            )}

            <section className="rounded-xl border border-slate-800 bg-slate-900/70 p-5">
                <form
                    aria-label="Filter execution candidates"
                    className="grid gap-4 lg:grid-cols-[repeat(5,1fr)_auto]"
                    onSubmit={submitFilters}
                >
                    <SelectFilter label="Status" value={filters.status} options={statusOptions} onChange={(value) => setFilters((current) => ({ ...current, status: value }))} />
                    <SelectFilter label="Category" value={filters.category} options={categoryOptions} onChange={(value) => setFilters((current) => ({ ...current, category: value }))} />
                    <SelectFilter label="Intent" value={filters.intent} options={intentOptions} onChange={(value) => setFilters((current) => ({ ...current, intent: value }))} />
                    <TextFilter label="Source subsystem" value={filters.sourceSubsystem} onChange={(value) => setFilters((current) => ({ ...current, sourceSubsystem: value }))} />
                    <TextFilter label="Target ID" value={filters.targetId} onChange={(value) => setFilters((current) => ({ ...current, targetId: value }))} />
                    <div className="flex items-end gap-2">
                        <button type="submit" className="rounded-lg bg-blue-500 px-4 py-2 text-sm font-semibold text-white transition hover:bg-blue-400 focus:outline-none focus:ring-2 focus:ring-blue-300">
                            Search
                        </button>
                        <button type="button" onClick={clearFilters} className="rounded-lg border border-slate-700 px-4 py-2 text-sm font-semibold text-slate-300 transition hover:border-slate-500 hover:text-white focus:outline-none focus:ring-2 focus:ring-blue-300">
                            Clear
                        </button>
                    </div>
                </form>
            </section>

            <section aria-label="Execution candidate results" className="space-y-4">
                <div className="flex items-center justify-between gap-4 text-sm text-slate-400">
                    <p>{isLoading ? "Loading execution candidates…" : `${result.total} candidate${result.total === 1 ? "" : "s"}`}</p>
                    <div className="flex gap-2">
                        <button type="button" aria-label="Previous execution candidates page" onClick={goToPreviousPage} disabled={isLoading || result.offset === 0} className="rounded-lg border border-slate-700 px-3 py-2 text-sm text-slate-300 disabled:cursor-not-allowed disabled:opacity-50">
                            Previous
                        </button>
                        <button type="button" aria-label="Next execution candidates page" onClick={goToNextPage} disabled={isLoading || !result.hasMore} className="rounded-lg border border-slate-700 px-3 py-2 text-sm text-slate-300 disabled:cursor-not-allowed disabled:opacity-50">
                            Next
                        </button>
                    </div>
                </div>

                {!isLoading && !error && result.candidates.length === 0 && (
                    <div className="rounded-xl border border-slate-800 bg-slate-900/70 p-6 text-sm text-slate-400">
                        {hasActiveFilters
                            ? "No execution candidates match these filters."
                            : "No current execution candidates."}
                    </div>
                )}

                <div className="grid gap-4">
                    {result.candidates.map((candidate) => (
                        <CandidateCard key={candidate.id} candidate={candidate} />
                    ))}
                </div>
            </section>
        </main>
    );
}

export function WorkflowRail({ activeStep }: { activeStep: string }) {
    const steps = [
        "Execution Candidate",
        "Planning Session",
        "Candidate Plan",
        "Workflow",
        "Implementation",
        "Verification",
        "Review",
        "Commit",
    ];

    return (
        <section aria-label="Read-only workflow rail" className="rounded-xl border border-slate-800 bg-slate-900/70 p-4">
            <ol className="grid gap-2 text-sm md:grid-cols-4 xl:grid-cols-8">
                {steps.map((step) => (
                    <li key={step} className={[
                        "rounded-lg border px-3 py-2",
                        step === activeStep
                            ? "border-blue-400 bg-blue-500/10 text-blue-200"
                            : "border-slate-800 bg-slate-950/50 text-slate-500",
                    ].join(" ")}
                    >
                        <span className="block font-medium">{step}</span>
                        <span className="text-xs">{step === "Planning Session" ? "Actionable in P4.1" : "Read-only"}</span>
                    </li>
                ))}
            </ol>
        </section>
    );
}

function CandidateCard({ candidate }: { candidate: ExecutionCandidate }) {
    return (
        <article className="rounded-xl border border-slate-800 bg-slate-900/70 p-5">
            <div className="flex flex-wrap items-start justify-between gap-4">
                <div>
                    <Link to={`/execution-candidates/${encodeURIComponent(candidate.id)}`} className="break-all text-lg font-semibold text-blue-300 transition hover:text-blue-200 focus:outline-none focus:ring-2 focus:ring-blue-300">
                        {candidate.id}
                    </Link>
                    <p className="mt-1 text-sm text-slate-400">
                        Target: <span className="text-slate-200">{candidate.target_id}</span> ({candidate.target_type})
                    </p>
                </div>
                <StatusBadge status={candidate.status} />
            </div>
            <dl className="mt-4 grid gap-3 text-sm md:grid-cols-2 xl:grid-cols-4">
                <Field label="Category" value={formatLabel(candidate.execution_category)} />
                <Field label="Intent" value={formatLabel(candidate.execution_intent)} />
                <Field label="Approval level" value={formatLabel(candidate.required_approval_level)} />
                <Field label="Source" value={candidate.source_subsystem} />
                <Field label="Compatibility" value={candidate.compatibility_status ? formatLabel(candidate.compatibility_status) : "Not reported"} />
                <Field label="Evidence" value={`${candidate.evidence_ids.length} reference${candidate.evidence_ids.length === 1 ? "" : "s"}`} />
                <Field label="Created" value={formatTimestamp(candidate.created_at)} />
                <Field label="Expires" value={candidate.expires_at ? formatTimestamp(candidate.expires_at) : "No expiry"} />
            </dl>
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
