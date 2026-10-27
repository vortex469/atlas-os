import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { FormEvent } from "react";
import { Link } from "react-router-dom";

import { getAtlasAgentErrorMessage, listWorkflows } from "../api/atlas-agent";
import { WorkflowMiniRail } from "../components/WorkflowMiniRail";
import type { WorkflowListQuery, WorkflowListResponse, WorkflowSummary } from "../types/atlasAgent";
import {
    WORKFLOW_STATES,
    formatWorkflowLabel,
    isActiveWorkflowState,
    workflowActionRequired,
    workflowRailStages,
    workflowStageLabel,
    workflowStatusGroup,
} from "../utils/workflowState";

const PAGE_SIZE = 10;

type LoadMode = "initial" | "refresh";

interface DashboardFilters {
    state: string;
    source: string;
    candidateId: string;
    workflowId: string;
    actionRequired: string;
}

const EMPTY_FILTERS: DashboardFilters = {
    state: "",
    source: "",
    candidateId: "",
    workflowId: "",
    actionRequired: "",
};

const SUMMARY_GROUPS = [
    { key: "running", label: "Running" },
    { key: "waiting_approval", label: "Waiting for approval" },
    { key: "waiting_implementation_approval", label: "Waiting for implementation approval" },
    { key: "waiting_verification_approval", label: "Waiting for verification approval" },
    { key: "waiting_commit_approval", label: "Waiting for commit approval" },
    { key: "blocked", label: "Blocked" },
    { key: "completed", label: "Completed" },
];

type DirectorySelection = { filters: DashboardFilters; offset: number };
const INITIAL_SELECTION: DirectorySelection = { filters: EMPTY_FILTERS, offset: 0 };

export function WorkflowDashboardPage() {
    const [workflowResponse, setWorkflowResponse] = useState<WorkflowListResponse | null>(null);
    const [draftFilters, setDraftFilters] = useState<DashboardFilters>(EMPTY_FILTERS);
    const [selection, setSelection] = useState<DirectorySelection>(INITIAL_SELECTION);
    const [isLoading, setIsLoading] = useState(true);
    const [isRefreshing, setIsRefreshing] = useState(false);
    const [loadError, setLoadError] = useState<string | null>(null);
    const [refreshError, setRefreshError] = useState<string | null>(null);
    const generation = useRef(0);
    const pendingLoad = useRef<string | null>(null);
    const currentSelection = useRef<DirectorySelection>(INITIAL_SELECTION);
    const hasLoadedResponse = useRef(false);

    const loadDashboard = useCallback(async (next = currentSelection.current, mode: LoadMode = "initial") => {
        const key = JSON.stringify(next);
        if (pendingLoad.current === key) return;
        const requestGeneration = ++generation.current;
        pendingLoad.current = key;
        currentSelection.current = next;
        setSelection(next);
        setIsLoading(mode === "initial");
        setIsRefreshing(mode === "refresh");
        if (mode === "initial") setLoadError(null);
        setRefreshError(null);

        try {
            let requested = next;
            // A deletion can empty the requested page. Correct the offset once;
            // repeated churn produces a recoverable error rather than a loop.
            for (let attempt = 0; attempt < 2; attempt += 1) {
                const response = await listWorkflows(directoryQuery(requested));
                if (requestGeneration !== generation.current) return;
                validateDirectoryPage(response, requested);
                if (requested.offset > 0 && requested.offset >= response.total) {
                    if (attempt > 0) throw new Error("The workflow list changed while loading. Try again.");
                    requested = { ...requested, offset: Math.max(0, Math.ceil(response.total / PAGE_SIZE) - 1) * PAGE_SIZE };
                    currentSelection.current = requested;
                    setSelection(requested);
                    pendingLoad.current = JSON.stringify(requested);
                    continue;
                }
                setWorkflowResponse(response);
                hasLoadedResponse.current = true;
                break;
            }
        } catch (error) {
            if (requestGeneration !== generation.current) return;
            const message = getAtlasAgentErrorMessage(error, "Atlas Agent unavailable.");
            if (mode === "initial" || !hasLoadedResponse.current) setLoadError(message);
            else setRefreshError(message);
        } finally {
            if (requestGeneration === generation.current) {
                pendingLoad.current = null;
                setIsLoading(false);
                setIsRefreshing(false);
            }
        }
    }, []);

    useEffect(() => {
        let active = true;
        void Promise.resolve().then(() => { if (active) void loadDashboard(); });
        return () => { active = false; generation.current += 1; pendingLoad.current = null; };
    }, [loadDashboard]);

    const workflows = useMemo(() => workflowResponse?.items ?? [], [workflowResponse]);
    const stateCounts = workflowResponse?.state_counts;
    const hasActiveWorkflow = stateCounts === undefined
        ? workflows.some((workflow) => isActiveWorkflowState(workflow.workflow_state))
        : Object.entries(stateCounts).some(([state, count]) => isActiveWorkflowState(state) && count > 0);

    useEffect(() => {
        if (!hasActiveWorkflow || isLoading || loadError) return undefined;
        const interval = window.setInterval(() => { void loadDashboard(currentSelection.current, "refresh"); }, 5_000);
        return () => window.clearInterval(interval);
    }, [hasActiveWorkflow, isLoading, loadError, loadDashboard]);

    const summaryCounts = useMemo(() => {
        if (stateCounts === undefined) return null;
        const counts = new Map<string, number>();
        for (const [state, count] of Object.entries(stateCounts)) {
            const group = workflowStatusGroup(state);
            counts.set(group, (counts.get(group) ?? 0) + count);
        }
        return counts;
    }, [stateCounts]);
    const matchingCount = workflowResponse?.total ?? 0;
    const totalPages = Math.max(1, Math.ceil(matchingCount / PAGE_SIZE));
    const currentPage = Math.floor((workflowResponse?.offset ?? 0) / PAGE_SIZE);
    const hasFilters = Object.values(selection.filters).some(Boolean);
    const retainedResults = isRefreshing || refreshError !== null;
    const normalizedDraftFilters = normalizeDirectoryFilters(draftFilters);
    const hasUnappliedFilters = (Object.keys(EMPTY_FILTERS) as Array<keyof DashboardFilters>)
        .some(key => normalizedDraftFilters[key] !== selection.filters[key]);
    const appliedFilters = [
        selection.filters.state && `State: ${formatWorkflowLabel(selection.filters.state)}`,
        selection.filters.source && `Source: ${formatWorkflowLabel(selection.filters.source)}`,
        selection.filters.candidateId && `Candidate ID: ${selection.filters.candidateId}`,
        selection.filters.workflowId && `Workflow ID: ${selection.filters.workflowId}`,
        selection.filters.actionRequired === "yes" ? "Approval: Waiting for approval"
            : selection.filters.actionRequired === "no" ? "Approval: Not waiting for approval" : "",
    ].filter(Boolean);


    function updateDraftFilter(name: keyof DashboardFilters, value: string) {
        setDraftFilters((current) => ({ ...current, [name]: value }));
    }
    function applyFilters(event: FormEvent<HTMLFormElement>) {
        event.preventDefault();
        void loadDashboard({ filters: normalizedDraftFilters, offset: 0 });
    }
    function clearFilters() {
        setDraftFilters(EMPTY_FILTERS);
        void loadDashboard(INITIAL_SELECTION);
    }
    function refresh() { void loadDashboard(currentSelection.current, "refresh"); }

    if (isLoading && workflowResponse === null) {
        return (
            <main className="mx-auto max-w-7xl p-8">
                <p role="status" aria-live="polite" className="text-slate-300">Loading workflows...</p>
            </main>
        );
    }

    if (loadError) {
        return (
            <main className="mx-auto max-w-7xl p-8">
                <section role="alert" className="rounded-xl border border-red-500/30 bg-red-500/10 p-5">
                    <h1 className="text-lg font-semibold text-red-100">Workflows unavailable</h1>
                    <p className="mt-2 text-sm text-red-100">{loadError}</p>
                    <p className="mt-2 text-sm text-slate-300">Try loading your workflows again.</p>
                    <button type="button" onClick={() => void loadDashboard(currentSelection.current)} className="mt-4 rounded-lg border border-slate-600 px-4 py-2 text-sm font-semibold text-slate-100 focus:outline-none focus:ring-2 focus:ring-blue-300">
                        Try again
                    </button>
                    {hasFilters && <button type="button" onClick={clearFilters} className="ml-3 rounded-lg border border-slate-600 px-4 py-2 text-sm text-slate-100">Clear filters</button>}
                </section>
            </main>
        );
    }

    return (
        <main className="mx-auto max-w-7xl space-y-8 p-8">
            <header className="flex flex-wrap items-start justify-between gap-4">
                <div>
                    <p className="text-xs uppercase tracking-[0.3em] text-blue-300">Workflow Dashboard</p>
                    <h1 className="mt-3 text-3xl font-bold text-white">Workflows</h1>
                    <p className="mt-3 max-w-3xl text-sm leading-6 text-slate-400">
                        See what is running, what needs your review, and what has finished. Open a workflow to see its details.
                    </p>
                </div>
                <button
                    type="button"
                    onClick={refresh}
                    disabled={isRefreshing || isLoading}
                    className="rounded-lg border border-slate-700 px-4 py-2 text-sm font-semibold text-slate-100 transition hover:bg-slate-800 focus:outline-none focus:ring-2 focus:ring-blue-300 disabled:cursor-not-allowed disabled:opacity-60"
                >
                    Refresh
                </button>
            </header>

            {isRefreshing && <p role="status" aria-live="polite" className="text-sm text-blue-200">Refreshing workflows...</p>}
            {retainedResults && <p role="status" className="text-sm text-amber-200">Showing the last loaded results. Current workflow states and totals are unconfirmed.</p>}
            {refreshError && <p role="alert" className="rounded-lg border border-red-500/30 bg-red-500/10 p-3 text-sm text-red-100">Refresh failed: {refreshError}</p>}

            <section aria-labelledby="workflow-counts-heading" className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
                <h2 id="workflow-counts-heading" className="text-sm font-semibold text-slate-300 md:col-span-2 xl:col-span-3">{retainedResults ? "Last loaded totals for this search" : "Totals for this search"}</h2>
                {isLoading && <p role="status" className="text-sm text-slate-300">Loading matching workflow totals…</p>}
                {!isLoading && SUMMARY_GROUPS.map((group) => (
                    <article key={group.key} className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1 rounded-xl border border-slate-800 bg-slate-900/70 px-4 py-3">
                        <p className="min-w-0 flex-1 text-sm text-slate-400">{group.label}</p>
                        <p className="max-w-full break-all text-xl font-bold text-white">{summaryCounts === null ? "Unavailable" : summaryCounts.get(group.key) ?? 0}</p>
                    </article>
                ))}
                {!isLoading && (summaryCounts?.get("unknown") ?? 0) > 0 && <article className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1 rounded-xl border border-slate-800 bg-slate-900/70 px-4 py-3"><p className="min-w-0 flex-1 text-sm text-slate-400">Other states</p><p className="max-w-full break-all text-xl font-bold text-white">{summaryCounts?.get("unknown")}</p></article>}
            </section>

            {!isLoading && summaryCounts === null && <p role="status" className="text-sm text-slate-400">This Agent does not provide workflow totals. Paging and search are available; approval-state filtering requires an updated Agent.</p>}

            <section aria-labelledby="workflow-filters-heading" className="rounded-xl border border-slate-800 bg-slate-900/70 p-5">
                <h2 id="workflow-filters-heading" className="text-lg font-semibold text-white">Filters</h2>
                <form onSubmit={applyFilters} className="mt-4 grid gap-4 md:grid-cols-2 xl:grid-cols-3">
                    <label className="text-sm text-slate-300">
                        State
                        <select value={draftFilters.state} onChange={(event) => updateDraftFilter("state", event.target.value)} className="mt-1 w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-slate-100">
                            <option value="">Any state</option>
                            {WORKFLOW_STATES.map((state) => <option key={state} value={state}>{formatWorkflowLabel(state)}</option>)}
                        </select>
                    </label>
                    <label className="text-sm text-slate-300">
                        Workflow ID search
                        <input value={draftFilters.workflowId} onChange={(event) => updateDraftFilter("workflowId", event.target.value)} className="mt-1 w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-slate-100" />
                    </label>
                    <label className="text-sm text-slate-300">
                        Waiting for approval
                        <select aria-label="Waiting for approval" value={draftFilters.actionRequired} onChange={(event) => updateDraftFilter("actionRequired", event.target.value)} className="mt-1 w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-slate-100">
                            <option value="">Any</option>
                            <option value="yes">Waiting for approval</option>
                            <option value="no">Not waiting for approval</option>
                        </select>
                    </label>
                    <details className="md:col-span-2 xl:col-span-3">
                        <summary className="cursor-pointer text-sm text-blue-300 focus-visible:outline-2">More filters</summary>
                        <div className="mt-4 grid gap-4 md:grid-cols-2">
                            <label className="text-sm text-slate-300">
                                Source
                                <select aria-label="Source" value={draftFilters.source} onChange={(event) => updateDraftFilter("source", event.target.value)} className="mt-1 w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-slate-100">
                                    <option value="">Any source</option>
                                    <option value="candidate">Candidate</option>
                                    <option value="manual">Manual</option>
                                    <option value="roadmap">Roadmap</option>
                                </select>
                            </label>
                            <label className="text-sm text-slate-300">
                                Candidate ID
                                <input aria-label="Candidate ID" value={draftFilters.candidateId} onChange={(event) => updateDraftFilter("candidateId", event.target.value)} className="mt-1 w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-slate-100" />
                            </label>
                        </div>
                    </details>
                    <div className="flex items-end gap-3 md:col-span-2 xl:col-span-3">
                        <button type="submit" className="rounded-lg bg-blue-500 px-4 py-2 text-sm font-semibold text-blue-950 transition hover:bg-blue-400 focus:outline-none focus:ring-2 focus:ring-blue-300">Apply filters</button>
                        <button type="button" onClick={clearFilters} className="rounded-lg border border-slate-700 px-4 py-2 text-sm font-semibold text-slate-100 transition hover:bg-slate-800 focus:outline-none focus:ring-2 focus:ring-blue-300">Clear filters</button>
                    </div>
                </form>
                {hasUnappliedFilters && <p role="status" className="mt-3 text-sm text-amber-200">Changes are not applied yet. Choose Apply filters to update results.</p>}
                <div role="region" aria-label="Applied workflow filters" className="mt-4 text-sm text-slate-400 [overflow-wrap:anywhere]">
                    <p><strong>{isLoading ? "Searching with" : "Applied filters"}:</strong> {appliedFilters.length ? appliedFilters.join(" · ") : "All workflows"}</p>
                </div>
            </section>

            <section aria-labelledby="workflow-list-heading" className="space-y-4">
                <div className="flex flex-wrap items-center justify-between gap-3">
                    <h2 id="workflow-list-heading" className="text-xl font-semibold text-white">Workflow list</h2>
                    <p className="text-sm text-slate-400">{isLoading ? "Loading matching workflows…" : `${retainedResults ? "Last loaded: " : "Showing "}${workflows.length} of ${matchingCount} matching workflows`}</p>
                </div>

                {isLoading ? (
                    <p role="status" className="rounded-xl border border-slate-800 bg-slate-900/70 p-5 text-sm text-slate-300">Loading workflow results…</p>
                ) : workflows.length === 0 ? (
                    <div className="space-y-3 rounded-xl border border-slate-800 bg-slate-900/70 p-5 text-sm text-slate-300">
                        <p>{retainedResults ? (hasFilters ? "The last loaded search had no matches." : "The last loaded list was empty.") : (hasFilters ? "No workflows match the current filters." : "No workflows yet.")}</p>
                        <p>{retainedResults ? "Use Refresh to check the current list." : hasFilters ? "Try a broader search or clear the filters above." : "Review a change proposal or choose maintenance to prepare a workflow."}</p>
                        {!hasFilters && !retainedResults && <div className="flex flex-wrap gap-4">
                            <Link to="/execution-candidates" className="text-blue-300 underline underline-offset-4 focus-visible:outline-2">Review change proposals</Link>
                            <Link to="/operations/request" className="text-blue-300 underline underline-offset-4 focus-visible:outline-2">Choose maintenance</Link>
                        </div>}
                    </div>
                ) : (
                    <div className="space-y-4">
                        {workflows.map((workflow) => <WorkflowCard key={workflow.workflow_id} workflow={workflow} retained={retainedResults} />)}
                    </div>
                )}

                {!isLoading && matchingCount > PAGE_SIZE && (
                    <nav aria-label="Workflow pagination" className="flex items-center gap-3">
                        <button type="button" onClick={() => void loadDashboard({ filters: selection.filters, offset: Math.max(0, selection.offset - PAGE_SIZE) })} disabled={isRefreshing || currentPage === 0} className="rounded-lg border border-slate-700 px-3 py-2 text-sm text-slate-100 disabled:cursor-not-allowed disabled:opacity-50">Previous</button>
                        <span className="text-sm text-slate-400">Page {currentPage + 1} of {totalPages}</span>
                        <button type="button" onClick={() => void loadDashboard({ filters: selection.filters, offset: selection.offset + PAGE_SIZE })} disabled={isRefreshing || currentPage >= totalPages - 1} className="rounded-lg border border-slate-700 px-3 py-2 text-sm text-slate-100 disabled:cursor-not-allowed disabled:opacity-50">Next</button>
                    </nav>
                )}
            </section>
        </main>
    );
}

function WorkflowCard({ workflow, retained }: { workflow: WorkflowSummary; retained: boolean }) {
    const actionRequired = workflowActionRequired(workflow.workflow_state);
    const approvalLabel = WORKFLOW_STATES.some(state => state === workflow.workflow_state)
        ? actionRequired ? "Waiting for approval" : "Not waiting for approval"
        : "Unknown — open workflow to review";
    const railId = `workflow-rail-${workflow.workflow_id}`;
    return (
        <article className="rounded-xl border border-slate-800 bg-slate-900/70 p-5">
            <div className="flex flex-wrap items-start justify-between gap-4">
                <div>
                    <h3 className="break-all text-lg font-semibold text-white">{workflow.workflow_id}</h3>
                    <p className="mt-1 text-sm text-slate-400">{retained ? "Last loaded stage" : "Current stage"}: {workflowStageLabel(workflow.workflow_state)}</p>
                </div>
                <Link to={`/workflows/${encodeURIComponent(workflow.workflow_id)}`} className="rounded-lg border border-blue-400/60 px-3 py-2 text-sm font-semibold text-blue-100 transition hover:bg-blue-500/10 focus:outline-none focus:ring-2 focus:ring-blue-300">
                    Open Workflow
                </Link>
            </div>
            <dl className="mt-4 grid gap-3 text-sm md:grid-cols-2 xl:grid-cols-4">
                <Detail label={retained ? "Last loaded state" : "Current State"} value={formatWorkflowLabel(workflow.workflow_state)} />
                <Detail label="Repository or Target" value={workflow.repository ?? workflow.target_id ?? "Not exposed"} />
                <Detail label="Last Known Result" value={workflow.last_result_summary} />
                <Detail label={retained ? "Last loaded approval state" : "Approval state"} value={approvalLabel} />
            </dl>
            <details className="mt-4 rounded-lg border border-slate-800 p-3">
                <summary className="cursor-pointer text-sm text-blue-300 focus-visible:outline-2">Workflow details</summary>
                <dl className="mt-3 grid gap-3 text-sm md:grid-cols-3">
                    <Detail label="Workflow Source" value={formatWorkflowLabel(workflow.workflow_source)} />
                    <Detail label="Candidate ID" value={workflow.candidate_id ?? "Not exposed"} />
                    <Detail label="Planning Session ID" value={workflow.planning_session_id ?? "Not exposed"} />
                </dl>
            </details>
            <details open={workflow.workflow_state === "blocked"} className="mt-3 rounded-lg border border-slate-800 p-3">
                <summary className="cursor-pointer focus-visible:outline-2"><h4 id={railId} className="inline text-sm font-semibold text-slate-200">Workflow progress</h4></summary>
                <div className="mt-3"><WorkflowMiniRail labelledBy={railId} stages={workflowRailStages(workflow)} /></div>
            </details>
        </article>
    );
}

function Detail({ label, value }: { label: string; value: string }) {
    return (
        <div>
            <dt className="text-xs uppercase tracking-wide text-slate-500">{label}</dt>
            <dd className="mt-1 break-all text-slate-200">{value}</dd>
        </div>
    );
}


function normalizeDirectoryFilters(filters: DashboardFilters): DashboardFilters {
    return { ...filters, candidateId: filters.candidateId.trim(), workflowId: filters.workflowId.trim() };
}

function directoryQuery(selection: DirectorySelection): WorkflowListQuery {
    const filters = selection.filters;
    return {
        state: filters.state || undefined, source: filters.source || undefined,
        candidate_id: filters.candidateId || undefined, workflow_id: filters.workflowId || undefined,
        waiting_for_approval: filters.actionRequired === "yes" ? true : filters.actionRequired === "no" ? false : undefined,
        limit: PAGE_SIZE, offset: selection.offset,
    };
}

// Validate only fields this read-only directory displays; nullable/omitted
// metadata and future string states remain readable without granting authority.
function isReadableDirectoryRecord(item: WorkflowSummary): boolean {
    if (!item || typeof item !== "object" || Array.isArray(item)
        || typeof item.workflow_id !== "string" || !item.workflow_id.trim()
        || item.workflow_id === "." || item.workflow_id === ".."
        || typeof item.workflow_state !== "string"
        || typeof item.last_result_summary !== "string") return false;
    try {
        encodeURIComponent(item.workflow_id);
    } catch {
        return false;
    }
    const metadata = [item.workflow_source, item.candidate_id, item.planning_session_id, item.repository, item.target_id];
    return metadata.every(value => value === null || value === undefined || typeof value === "string")
        && Array.isArray(item.timeline) && item.timeline.every(stage => stage !== null
            && typeof stage === "object" && !Array.isArray(stage)
            && typeof stage.name === "string" && typeof stage.status === "string");
}

function validateDirectoryPage(page: WorkflowListResponse, selection: DirectorySelection): void {
    if (!page || !Array.isArray(page.items) || !Number.isSafeInteger(page.total) || page.total < 0
        || page.limit !== PAGE_SIZE || page.offset !== selection.offset || page.items.length > PAGE_SIZE
        || page.items.some((item) => !isReadableDirectoryRecord(item))
        || new Set(page.items.map((item) => item.workflow_id)).size !== page.items.length
        || (page.offset < page.total && page.items.length !== Math.min(PAGE_SIZE, page.total - page.offset))
        || (page.offset >= page.total && page.items.length !== 0)) {
        throw new Error("The Agent returned an inconsistent workflow page. Try again.");
    }
    if (page.state_counts === undefined) {
        if (selection.filters.actionRequired) throw new Error("Approval-state filtering requires an updated Atlas Agent. Clear this filter or update the Agent.");
        return;
    }
    if (page.state_counts === null || typeof page.state_counts !== "object" || Array.isArray(page.state_counts)
        || Object.values(page.state_counts).some((count) => !Number.isSafeInteger(count) || count < 0)
        || Object.values(page.state_counts).reduce((sum, count) => sum + count, 0) !== page.total) {
        throw new Error("The Agent returned inconsistent workflow totals. Try again.");
    }
    const returnedCounts = new Map<string, number>();
    for (const item of page.items) returnedCounts.set(item.workflow_state, (returnedCounts.get(item.workflow_state) ?? 0) + 1);
    if ([...returnedCounts].some(([state, count]) => (page.state_counts?.[state] ?? 0) < count)) {
        throw new Error("The Agent returned inconsistent workflow totals. Try again.");
    }
}
