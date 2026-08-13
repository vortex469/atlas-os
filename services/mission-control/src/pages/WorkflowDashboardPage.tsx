import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { FormEvent } from "react";
import { Link } from "react-router-dom";

import { getAtlasAgentErrorMessage, listWorkflows } from "../api/atlas-agent";
import { WorkflowMiniRail } from "../components/WorkflowMiniRail";
import type { WorkflowListResponse, WorkflowSummary } from "../types/atlasAgent";
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
    { key: "waiting_implementation_approval", label: "Waiting for implementation approval" },
    { key: "waiting_verification_approval", label: "Waiting for verification approval" },
    { key: "waiting_commit_approval", label: "Waiting for commit approval" },
    { key: "blocked", label: "Blocked" },
    { key: "completed", label: "Completed" },
];

export function WorkflowDashboardPage() {
    const [workflowResponse, setWorkflowResponse] = useState<WorkflowListResponse | null>(null);
    const [draftFilters, setDraftFilters] = useState<DashboardFilters>(EMPTY_FILTERS);
    const [filters, setFilters] = useState<DashboardFilters>(EMPTY_FILTERS);
    const [pageIndex, setPageIndex] = useState(0);
    const [isLoading, setIsLoading] = useState(true);
    const [isRefreshing, setIsRefreshing] = useState(false);
    const [loadError, setLoadError] = useState<string | null>(null);
    const [refreshError, setRefreshError] = useState<string | null>(null);
    const pendingLoad = useRef(false);
    const hasLoadedResponse = useRef(false);

    const loadDashboard = useCallback(async (mode: LoadMode = "initial") => {
        if (pendingLoad.current) return;
        pendingLoad.current = true;
        if (mode === "initial") setIsLoading(true);
        if (mode === "refresh") setIsRefreshing(true);
        if (mode === "initial") setLoadError(null);
        setRefreshError(null);

        try {
            const response = await listWorkflows({ limit: 200, offset: 0 });
            setWorkflowResponse(response);
            hasLoadedResponse.current = true;
        } catch (error) {
            const message = getAtlasAgentErrorMessage(error, "Atlas Agent unavailable.");
            if (mode === "initial" || !hasLoadedResponse.current) {
                setLoadError(message);
            } else {
                setRefreshError(message);
            }
        } finally {
            pendingLoad.current = false;
            if (mode === "initial") setIsLoading(false);
            if (mode === "refresh") setIsRefreshing(false);
        }
    }, []);

    useEffect(() => {
        void Promise.resolve().then(() => loadDashboard());
    }, [loadDashboard]);

    const workflows = useMemo(() => workflowResponse?.items ?? [], [workflowResponse]);
    const hasActiveWorkflow = workflows.some((workflow) => isActiveWorkflowState(workflow.workflow_state));

    useEffect(() => {
        if (!hasActiveWorkflow) return undefined;
        const interval = window.setInterval(() => {
            void loadDashboard("refresh");
        }, 5_000);
        return () => window.clearInterval(interval);
    }, [hasActiveWorkflow, loadDashboard]);

    const summaryCounts = useMemo(() => {
        const counts = new Map<string, number>();
        for (const workflow of workflows) {
            const group = workflowStatusGroup(workflow.workflow_state);
            counts.set(group, (counts.get(group) ?? 0) + 1);
        }
        return counts;
    }, [workflows]);

    const filteredWorkflows = useMemo(() => {
        return workflows.filter((workflow) => {
            if (filters.state && workflow.workflow_state !== filters.state) return false;
            if (filters.source && workflow.workflow_source !== filters.source) return false;
            if (filters.candidateId && !workflow.candidate_id?.toLowerCase().includes(filters.candidateId.toLowerCase())) return false;
            if (filters.workflowId && !workflow.workflow_id.toLowerCase().includes(filters.workflowId.toLowerCase())) return false;
            if (filters.actionRequired === "yes" && !workflowActionRequired(workflow.workflow_state)) return false;
            if (filters.actionRequired === "no" && workflowActionRequired(workflow.workflow_state)) return false;
            return true;
        });
    }, [filters, workflows]);

    const totalPages = Math.max(1, Math.ceil(filteredWorkflows.length / PAGE_SIZE));
    const currentPage = Math.min(pageIndex, totalPages - 1);
    const visibleWorkflows = filteredWorkflows.slice(currentPage * PAGE_SIZE, (currentPage + 1) * PAGE_SIZE);

    function updateDraftFilter(name: keyof DashboardFilters, value: string) {
        setDraftFilters((current) => ({ ...current, [name]: value }));
    }

    function applyFilters(event: FormEvent<HTMLFormElement>) {
        event.preventDefault();
        setFilters(draftFilters);
        setPageIndex(0);
    }

    function clearFilters() {
        setDraftFilters(EMPTY_FILTERS);
        setFilters(EMPTY_FILTERS);
        setPageIndex(0);
    }

    function refresh() {
        if (pendingLoad.current || isRefreshing) return;
        void loadDashboard("refresh");
    }

    if (isLoading) {
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
                        Find persisted candidate workflows and open their read-only workflow detail. This dashboard never approves, executes, resumes, mutates repositories, or creates workflows.
                    </p>
                </div>
                <button
                    type="button"
                    onClick={refresh}
                    disabled={isRefreshing}
                    className="rounded-lg border border-slate-700 px-4 py-2 text-sm font-semibold text-slate-100 transition hover:bg-slate-800 focus:outline-none focus:ring-2 focus:ring-blue-300 disabled:cursor-not-allowed disabled:opacity-60"
                >
                    Refresh
                </button>
            </header>

            {isRefreshing && <p role="status" aria-live="polite" className="text-sm text-blue-200">Refreshing workflows...</p>}
            {refreshError && <p role="alert" className="rounded-lg border border-red-500/30 bg-red-500/10 p-3 text-sm text-red-100">Refresh failed: {refreshError}</p>}

            <section aria-labelledby="workflow-counts-heading" className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
                <h2 id="workflow-counts-heading" className="sr-only">Workflow summary counts</h2>
                {SUMMARY_GROUPS.map((group) => (
                    <article key={group.key} className="rounded-xl border border-slate-800 bg-slate-900/70 p-4">
                        <p className="text-sm text-slate-400">{group.label}</p>
                        <p className="mt-2 text-2xl font-bold text-white">{summaryCounts.get(group.key) ?? 0}</p>
                    </article>
                ))}
            </section>

            <section aria-labelledby="workflow-filters-heading" className="rounded-xl border border-slate-800 bg-slate-900/70 p-5">
                <h2 id="workflow-filters-heading" className="text-lg font-semibold text-white">Filters</h2>
                <form onSubmit={applyFilters} className="mt-4 grid gap-4 md:grid-cols-2 xl:grid-cols-5">
                    <label className="text-sm text-slate-300">
                        State
                        <select value={draftFilters.state} onChange={(event) => updateDraftFilter("state", event.target.value)} className="mt-1 w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-slate-100">
                            <option value="">Any state</option>
                            {WORKFLOW_STATES.map((state) => <option key={state} value={state}>{formatWorkflowLabel(state)}</option>)}
                        </select>
                    </label>
                    <label className="text-sm text-slate-300">
                        Source
                        <select value={draftFilters.source} onChange={(event) => updateDraftFilter("source", event.target.value)} className="mt-1 w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-slate-100">
                            <option value="">Any source</option>
                            <option value="candidate">Candidate</option>
                            <option value="manual">Manual</option>
                        </select>
                    </label>
                    <label className="text-sm text-slate-300">
                        Candidate ID
                        <input value={draftFilters.candidateId} onChange={(event) => updateDraftFilter("candidateId", event.target.value)} className="mt-1 w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-slate-100" />
                    </label>
                    <label className="text-sm text-slate-300">
                        Workflow ID search
                        <input value={draftFilters.workflowId} onChange={(event) => updateDraftFilter("workflowId", event.target.value)} className="mt-1 w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-slate-100" />
                    </label>
                    <label className="text-sm text-slate-300">
                        Action required
                        <select value={draftFilters.actionRequired} onChange={(event) => updateDraftFilter("actionRequired", event.target.value)} className="mt-1 w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-slate-100">
                            <option value="">Any</option>
                            <option value="yes">Action required</option>
                            <option value="no">No operator action</option>
                        </select>
                    </label>
                    <div className="flex items-end gap-3 xl:col-span-5">
                        <button type="submit" className="rounded-lg bg-blue-500 px-4 py-2 text-sm font-semibold text-blue-950 transition hover:bg-blue-400 focus:outline-none focus:ring-2 focus:ring-blue-300">Apply filters</button>
                        <button type="button" onClick={clearFilters} className="rounded-lg border border-slate-700 px-4 py-2 text-sm font-semibold text-slate-100 transition hover:bg-slate-800 focus:outline-none focus:ring-2 focus:ring-blue-300">Clear filters</button>
                    </div>
                </form>
            </section>

            <section aria-labelledby="workflow-list-heading" className="space-y-4">
                <div className="flex flex-wrap items-center justify-between gap-3">
                    <h2 id="workflow-list-heading" className="text-xl font-semibold text-white">Workflow list</h2>
                    <p className="text-sm text-slate-400">Showing {visibleWorkflows.length} of {filteredWorkflows.length} returned workflows</p>
                </div>

                {workflows.length === 0 ? (
                    <p className="rounded-xl border border-slate-800 bg-slate-900/70 p-5 text-sm text-slate-300">No workflows have been persisted yet.</p>
                ) : visibleWorkflows.length === 0 ? (
                    <p className="rounded-xl border border-slate-800 bg-slate-900/70 p-5 text-sm text-slate-300">No workflows match the current filters.</p>
                ) : (
                    <div className="space-y-4">
                        {visibleWorkflows.map((workflow) => <WorkflowCard key={workflow.workflow_id} workflow={workflow} />)}
                    </div>
                )}

                {filteredWorkflows.length > PAGE_SIZE && (
                    <nav aria-label="Workflow pagination" className="flex items-center gap-3">
                        <button type="button" onClick={() => setPageIndex((page) => Math.max(0, page - 1))} disabled={currentPage === 0} className="rounded-lg border border-slate-700 px-3 py-2 text-sm text-slate-100 disabled:cursor-not-allowed disabled:opacity-50">Previous</button>
                        <span className="text-sm text-slate-400">Page {currentPage + 1} of {totalPages}</span>
                        <button type="button" onClick={() => setPageIndex((page) => Math.min(totalPages - 1, page + 1))} disabled={currentPage >= totalPages - 1} className="rounded-lg border border-slate-700 px-3 py-2 text-sm text-slate-100 disabled:cursor-not-allowed disabled:opacity-50">Next</button>
                    </nav>
                )}
            </section>
        </main>
    );
}

function WorkflowCard({ workflow }: { workflow: WorkflowSummary }) {
    const actionRequired = workflowActionRequired(workflow.workflow_state);
    const railId = `workflow-rail-${workflow.workflow_id}`;
    return (
        <article className="rounded-xl border border-slate-800 bg-slate-900/70 p-5">
            <div className="flex flex-wrap items-start justify-between gap-4">
                <div>
                    <h3 className="break-all text-lg font-semibold text-white">{workflow.workflow_id}</h3>
                    <p className="mt-1 text-sm text-slate-400">Current stage: {workflowStageLabel(workflow.workflow_state)}</p>
                </div>
                <Link to={`/workflows/${encodeURIComponent(workflow.workflow_id)}`} className="rounded-lg border border-blue-400/60 px-3 py-2 text-sm font-semibold text-blue-100 transition hover:bg-blue-500/10 focus:outline-none focus:ring-2 focus:ring-blue-300">
                    Open Workflow
                </Link>
            </div>
            <dl className="mt-4 grid gap-3 text-sm md:grid-cols-2 xl:grid-cols-4">
                <Detail label="Workflow Source" value={formatWorkflowLabel(workflow.workflow_source)} />
                <Detail label="Candidate ID" value={workflow.candidate_id ?? "Not exposed"} />
                <Detail label="Planning Session ID" value={workflow.planning_session_id ?? "Not exposed"} />
                <Detail label="Current State" value={formatWorkflowLabel(workflow.workflow_state)} />
                <Detail label="Repository or Target" value={workflow.repository ?? workflow.target_id ?? "Not exposed"} />
                <Detail label="Last Known Result" value={workflow.last_result_summary} />
                <Detail label="Operator Action" value={actionRequired ? "Action required" : "No operator action required"} />
            </dl>
            <div className="mt-4">
                <h4 id={railId} className="mb-2 text-sm font-semibold text-slate-200">Mini workflow rail</h4>
                <WorkflowMiniRail labelledBy={railId} stages={workflowRailStages(workflow)} />
            </div>
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
