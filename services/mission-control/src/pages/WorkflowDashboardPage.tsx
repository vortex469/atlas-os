import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { FormEvent } from "react";
import { Link } from "react-router-dom";

import { getAtlasAgentErrorMessage, listWorkflows } from "../api/atlas-agent";
import { WorkflowMiniRail } from "../components/WorkflowMiniRail";
import type { WorkflowListResponse, WorkflowSummary } from "../types/atlasAgent";
import {
    WORKFLOW_STATES,
    formatWorkflowLabel,
    formatWorkflowValue,
    isActiveWorkflowState,
    workflowRailStages,
    workflowStageLabel,
    workflowStateFilterLabel,
    workflowStatusGroup,
    formatWorkflowResultSummary,
    workflowNextStepLabel,
} from "../utils/workflowState";

const PAGE_SIZE = 10;
const WORKFLOW_BATCH_SIZE = 200;

type LoadMode = "initial" | "refresh";

interface DashboardFilters {
    state: string;
    source: string;
    candidateId: string;
    workflowId: string;
    operatorStep: string;
}

const EMPTY_FILTERS: DashboardFilters = {
    state: "",
    source: "",
    candidateId: "",
    workflowId: "",
    operatorStep: "",
};

const SUMMARY_GROUPS = [
    { key: "running", label: "Running" },
    { key: "prepare_change", label: "Prepare change for review" },
    { key: "approval_or_action", label: "Approval or action" },
    { key: "blocked", label: "Blocked" },
    { key: "completed", label: "Completed" },
    { key: "unknown", label: "Status unavailable" },
];

export function WorkflowDashboardPage() {
    const [workflowResponse, setWorkflowResponse] = useState<WorkflowListResponse | null>(null);
    const [draftFilters, setDraftFilters] = useState<DashboardFilters>(EMPTY_FILTERS);
    const [filters, setFilters] = useState<DashboardFilters>(EMPTY_FILTERS);
    const [pageIndex, setPageIndex] = useState(0);
    const [isLoading, setIsLoading] = useState(true);
    const [isRefreshing, setIsRefreshing] = useState(false);
    const [isLoadingMore, setIsLoadingMore] = useState(false);
    const [loadError, setLoadError] = useState<string | null>(null);
    const [refreshError, setRefreshError] = useState<string | null>(null);
    const [loadMoreError, setLoadMoreError] = useState<string | null>(null);
    const [nextWorkflowOffset, setNextWorkflowOffset] = useState(0);
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
            const response = await listWorkflows({ limit: WORKFLOW_BATCH_SIZE, offset: 0 });
            setWorkflowResponse(response);
            setNextWorkflowOffset(response.items.length);
            setLoadMoreError(null);
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
    const hasMoreWorkflows = workflowResponse !== null && nextWorkflowOffset < workflowResponse.total;

    useEffect(() => {
        if (!hasActiveWorkflow || workflows.length > WORKFLOW_BATCH_SIZE) return undefined;
        const interval = window.setInterval(() => {
            void loadDashboard("refresh");
        }, 5_000);
        return () => window.clearInterval(interval);
    }, [hasActiveWorkflow, loadDashboard, workflows.length]);

    const hasAppliedMoreFilters = Boolean(filters.source || filters.candidateId || filters.workflowId);
    const hasUnappliedFilters = !dashboardFiltersEqual(draftFilters, filters);

    const filteredWorkflows = useMemo(() => {
        return workflows.filter((workflow) => {
            if (filters.state && workflow.workflow_state !== filters.state) return false;
            if (filters.source && workflow.workflow_source !== filters.source) return false;
            if (filters.candidateId && !workflow.candidate_id?.toLowerCase().includes(filters.candidateId.toLowerCase())) return false;
            if (filters.workflowId && !workflow.workflow_id.toLowerCase().includes(filters.workflowId.toLowerCase())) return false;
            const hasNextStep = workflowNextStepLabel(workflow.workflow_state, workflow.effect_kind) !== null;
            if (filters.operatorStep === "needed" && !hasNextStep) return false;
            if (filters.operatorStep === "not_needed" && hasNextStep) return false;
            return true;
        });
    }, [filters, workflows]);

    const summaryCounts = useMemo(() => {
        const counts = new Map<string, number>();
        for (const workflow of filteredWorkflows) {
            const group = workflowDashboardSummaryGroup(workflow.workflow_state);
            counts.set(group, (counts.get(group) ?? 0) + 1);
        }
        return counts;
    }, [filteredWorkflows]);

    const totalPages = Math.max(1, Math.ceil(filteredWorkflows.length / PAGE_SIZE));
    const currentPage = Math.min(pageIndex, totalPages - 1);
    const visibleWorkflows = filteredWorkflows.slice(currentPage * PAGE_SIZE, (currentPage + 1) * PAGE_SIZE);
    const firstVisibleWorkflow = filteredWorkflows.length === 0 ? 0 : currentPage * PAGE_SIZE + 1;
    const lastVisibleWorkflow = currentPage * PAGE_SIZE + visibleWorkflows.length;

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
        setPageIndex(0);
        void loadDashboard("refresh");
    }

    async function loadMoreWorkflows() {
        if (!workflowResponse || pendingLoad.current || isLoadingMore || nextWorkflowOffset >= workflowResponse.total) return;
        const offset = nextWorkflowOffset;
        pendingLoad.current = true;
        setIsLoadingMore(true);
        setLoadMoreError(null);
        try {
            const response = await listWorkflows({ limit: WORKFLOW_BATCH_SIZE, offset });
            if (response.items.length === 0 && offset < response.total) {
                throw new Error("The workflow list returned no entries for an available page.");
            }
            setWorkflowResponse((current) => {
                if (!current) return response;
                const existingIds = new Set(current.items.map((workflow) => workflow.workflow_id));
                const newItems = response.items.filter((workflow) => !existingIds.has(workflow.workflow_id));
                return { ...response, items: [...current.items, ...newItems], offset: 0 };
            });
            setNextWorkflowOffset(offset + response.items.length);
        } catch (error) {
            console.error("Unable to load more workflows:", error);
            setLoadMoreError("Could not load more workflows. The workflows already shown are unchanged. Try again.");
        } finally {
            pendingLoad.current = false;
            setIsLoadingMore(false);
        }
    }

    if (isLoading) {
        return (
            <main className="mx-auto max-w-7xl p-4 sm:p-8">
                <p role="status" aria-live="polite" className="text-slate-300">Loading workflows...</p>
            </main>
        );
    }

    if (loadError) {
        return (
            <main className="mx-auto max-w-7xl p-4 sm:p-8">
                <section role="alert" className="rounded-xl border border-red-500/30 bg-red-500/10 p-5">
                    <h1 className="text-lg font-semibold text-red-100">Workflows unavailable</h1>
                    <p className="mt-2 text-sm text-red-100">Mission Control could not load the workflow list. Try again to request the latest workflows.</p>
                    <button type="button" onClick={() => void loadDashboard()} className="mt-4 rounded-lg border border-slate-600 px-4 py-2 text-sm font-semibold text-slate-100 focus:outline-none focus:ring-2 focus:ring-blue-300">
                        Try again
                    </button>
                    <details className="mt-3">
                        <summary className="mc-focusable cursor-pointer text-sm font-medium text-slate-300">Technical details</summary>
                        <p className="mt-2 break-words text-sm text-slate-400">{loadError}</p>
                    </details>
                </section>
            </main>
        );
    }

    return (
        <main className="mx-auto max-w-7xl space-y-8 p-4 sm:p-8">
            <header className="flex flex-wrap items-start justify-between gap-4">
                <div>
                    <h1 className="text-3xl font-bold text-white">Workflows</h1>
                    <p className="mt-3 max-w-3xl text-sm leading-6 text-slate-400">
                        See what is running, what needs your review, and what has finished. Open a workflow to see its details.
                    </p>
                </div>
                <button
                    type="button"
                    onClick={refresh}
                    disabled={isRefreshing || isLoadingMore}
                    className="rounded-lg border border-slate-700 px-4 py-2 text-sm font-semibold text-slate-100 transition hover:bg-slate-800 focus:outline-none focus:ring-2 focus:ring-blue-300 disabled:cursor-not-allowed disabled:opacity-60"
                >
                    Refresh
                </button>
            </header>

            {isRefreshing && <p role="status" aria-live="polite" className="text-sm text-blue-200">Refreshing workflows...</p>}
            {hasMoreWorkflows && <p role="status" className="rounded-lg border border-blue-500/30 bg-blue-500/10 px-4 py-3 text-sm text-blue-100">Loaded {workflows.length} of {workflowResponse?.total ?? 0} workflows. Summary counts and filters cover the loaded workflows only.</p>}
            {workflows.length > WORKFLOW_BATCH_SIZE && <p role="status" className="rounded-lg border border-slate-700 bg-slate-900/70 px-4 py-3 text-sm text-slate-300">You loaded more than {WORKFLOW_BATCH_SIZE} workflows. Automatic refresh is paused; select Refresh to return to the first {WORKFLOW_BATCH_SIZE} and turn it back on.</p>}
            {refreshError && (
                <div role="alert" className="rounded-lg border border-amber-500/30 bg-amber-500/10 p-4">
                    <p className="font-semibold text-amber-100">Could not refresh workflows</p>
                    <p className="mt-1 text-sm text-amber-100/80">The list and counts below show the last successfully loaded state. Use Refresh to check again before reviewing a workflow.</p>
                    <details className="mt-3">
                        <summary className="mc-focusable cursor-pointer text-sm font-medium text-slate-300">Technical details</summary>
                        <p className="mt-2 break-words text-sm text-slate-400">{refreshError}</p>
                    </details>
                </div>
            )}

            {filteredWorkflows.length > 0 && (
                <section aria-labelledby="workflow-counts-heading" className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
                    <h2 id="workflow-counts-heading" className="sr-only">Workflow summary counts</h2>
                    {SUMMARY_GROUPS.map((group) => (
                        <article key={group.key} className="rounded-xl border border-slate-800 bg-slate-900/70 p-4">
                            <p className="text-sm text-slate-400">{group.label}</p>
                            <p className="mt-2 text-2xl font-bold text-white">{summaryCounts.get(group.key) ?? 0}</p>
                        </article>
                    ))}
                </section>
            )}

            <section aria-labelledby="workflow-filters-heading" className="rounded-xl border border-slate-800 bg-slate-900/70 p-5">
                <h2 id="workflow-filters-heading" className="text-lg font-semibold text-white">Filters</h2>
                <form onSubmit={applyFilters} className="mt-4">
                    <div className="grid gap-4 md:grid-cols-2">
                        <label className="text-sm text-slate-300">
                            Workflow status
                            <select value={draftFilters.state} onChange={(event) => updateDraftFilter("state", event.target.value)} className="mt-1 w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-slate-100">
                                <option value="">Any status</option>
                                {WORKFLOW_STATES.map((state) => <option key={state} value={state}>{workflowStateFilterLabel(state)}</option>)}
                            </select>
                        </label>
                        <label className="text-sm text-slate-300">
                            Next step
                            <select value={draftFilters.operatorStep} onChange={(event) => updateDraftFilter("operatorStep", event.target.value)} className="mt-1 w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-slate-100">
                                <option value="">Any workflow</option>
                                <option value="needed">Needs an operator step</option>
                                <option value="not_needed">No operator step needed</option>
                            </select>
                        </label>
                    </div>
                    <details className="mt-4 rounded-lg border border-slate-800 px-4 py-3">
                        <summary className="mc-focusable cursor-pointer text-sm font-semibold text-blue-200">
                            More filters
                            {hasAppliedMoreFilters && <span className="ml-2 text-xs font-normal text-amber-200">Additional filters are applied</span>}
                        </summary>
                        <div className="mt-4 grid gap-4 md:grid-cols-2 xl:grid-cols-3">
                            <label className="text-sm text-slate-300">
                                Started from
                                <select value={draftFilters.source} onChange={(event) => updateDraftFilter("source", event.target.value)} className="mt-1 w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-slate-100">
                                    <option value="">Any starting point</option>
                                    <option value="candidate">Candidate</option>
                                    <option value="manual">Manual</option>
                                </select>
                            </label>
                            <label className="text-sm text-slate-300">
                                Candidate ID
                                <input value={draftFilters.candidateId} onChange={(event) => updateDraftFilter("candidateId", event.target.value)} className="mt-1 w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-slate-100" />
                            </label>
                            <label className="text-sm text-slate-300">
                                Workflow ID contains
                                <input value={draftFilters.workflowId} onChange={(event) => updateDraftFilter("workflowId", event.target.value)} className="mt-1 w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-slate-100" />
                            </label>
                        </div>
                    </details>
                    <div className="mt-4 flex flex-wrap items-center gap-3">
                        <button type="submit" className="rounded-lg bg-blue-500 px-4 py-2 text-sm font-semibold text-blue-950 transition hover:bg-blue-400 focus:outline-none focus:ring-2 focus:ring-blue-300">Apply filters</button>
                        <button type="button" onClick={clearFilters} className="rounded-lg border border-slate-700 px-4 py-2 text-sm font-semibold text-slate-100 transition hover:bg-slate-800 focus:outline-none focus:ring-2 focus:ring-blue-300">Clear filters</button>
                    </div>
                </form>
                {hasUnappliedFilters && <p role="status" className="mt-4 rounded-lg border border-blue-500/30 bg-blue-500/10 px-4 py-3 text-sm text-blue-100">These filter changes haven&apos;t been applied yet. Select Apply filters to update the workflow list.</p>}
            </section>

            <section aria-labelledby="workflow-list-heading" className="space-y-4">
                <div className="flex flex-wrap items-center justify-between gap-3">
                    <h2 id="workflow-list-heading" className="text-xl font-semibold text-white">Workflow list</h2>
                    {filteredWorkflows.length > 0 && <p className="text-sm text-slate-400">Showing {firstVisibleWorkflow}–{lastVisibleWorkflow} of {filteredWorkflows.length} loaded workflows</p>}
                </div>

                {workflows.length === 0 ? (
                    <p className="rounded-xl border border-slate-800 bg-slate-900/70 p-5 text-sm text-slate-300">No workflows yet.</p>
                ) : visibleWorkflows.length === 0 ? (
                    <p className="rounded-xl border border-slate-800 bg-slate-900/70 p-5 text-sm text-slate-300">No workflows match the current filters.</p>
                ) : (
                    <div className="space-y-4">
                        {visibleWorkflows.map((workflow) => <WorkflowCard key={workflow.workflow_id} workflow={workflow} />)}
                    </div>
                )}

                {filteredWorkflows.length > PAGE_SIZE && (
                    <nav aria-label="Workflow pagination" className="flex items-center gap-3">
                        <button type="button" onClick={() => setPageIndex((page) => Math.max(0, page - 1))} disabled={hasUnappliedFilters || currentPage === 0} className="rounded-lg border border-slate-700 px-3 py-2 text-sm text-slate-100 disabled:cursor-not-allowed disabled:opacity-50">Previous</button>
                        <span className="text-sm text-slate-400">Page {currentPage + 1} of {totalPages}</span>
                        <button type="button" onClick={() => setPageIndex((page) => Math.min(totalPages - 1, page + 1))} disabled={hasUnappliedFilters || currentPage >= totalPages - 1} className="rounded-lg border border-slate-700 px-3 py-2 text-sm text-slate-100 disabled:cursor-not-allowed disabled:opacity-50">Next</button>
                    </nav>
                )}
                {loadMoreError && <p role="alert" className="rounded-lg border border-red-500/30 bg-red-500/10 p-4 text-sm text-red-100">{loadMoreError}</p>}
                {hasMoreWorkflows && <button type="button" onClick={() => void loadMoreWorkflows()} disabled={isLoadingMore || isRefreshing} className="rounded-lg border border-slate-700 px-4 py-2 text-sm font-semibold text-slate-100 disabled:cursor-not-allowed disabled:opacity-60">{isLoadingMore ? "Loading more workflows…" : "Load more workflows"}</button>}
            </section>
        </main>
    );
}

function dashboardFiltersEqual(left: DashboardFilters, right: DashboardFilters): boolean {
    return left.state === right.state
        && left.source === right.source
        && left.candidateId === right.candidateId
        && left.workflowId === right.workflowId
        && left.operatorStep === right.operatorStep;
}

function workflowDashboardSummaryGroup(state: string): string {
    switch (state) {
        case "awaiting_approval":
            return "prepare_change";
        case "awaiting_implementation_approval":
        case "awaiting_verification_approval":
        case "awaiting_commit_approval":
            return "approval_or_action";
        default:
            return workflowStatusGroup(state);
    }
}

function WorkflowCard({ workflow }: { workflow: WorkflowSummary }) {
    const nextStep = workflowNextStepLabel(workflow.workflow_state, workflow.effect_kind);
    const railId = `workflow-rail-${workflow.workflow_id}`;
    const title = workflow.execution_intent
        ? formatWorkflowLabel(workflow.execution_intent)
        : workflow.effect_kind === "operational_action"
            ? "Maintenance workflow"
            : "Repository change";
    return (
        <article className="rounded-xl border border-slate-800 bg-slate-900/70 p-5">
            <div className="flex flex-wrap items-start justify-between gap-4">
                <div>
                    <h3 className="break-words text-lg font-semibold text-white">{title}</h3>
                    <p className="mt-1 text-sm text-slate-400">Stage: {workflowStageLabel(workflow.workflow_state, workflow.effect_kind)}</p>
                </div>
                <Link to={`/workflows/${encodeURIComponent(workflow.workflow_id)}`} className="rounded-lg border border-blue-400/60 px-3 py-2 text-sm font-semibold text-blue-100 transition hover:bg-blue-500/10 focus:outline-none focus:ring-2 focus:ring-blue-300">
                    Open workflow
                </Link>
            </div>
            <dl className="mt-4 grid gap-3 text-sm md:grid-cols-2">
                <Detail label="Latest result" value={formatWorkflowResultSummary(workflow.last_result_summary)} />
                {nextStep && <Detail label="Next step" value={nextStep} />}
            </dl>
            <details className="mt-4 rounded-lg border border-slate-800 px-4 py-3">
                <summary className="mc-focusable cursor-pointer text-sm font-semibold text-blue-200">Workflow details</summary>
                <dl className="mt-3 grid gap-3 text-sm md:grid-cols-2 xl:grid-cols-4">
                    <Detail label="Workflow ID" value={workflow.workflow_id} />
                    <Detail label="Started from" value={formatWorkflowLabel(workflow.workflow_source)} />
                    <Detail label="Candidate ID" value={formatWorkflowValue(workflow.candidate_id, "Not available")} />
                    <Detail label="Planning session" value={formatWorkflowValue(workflow.planning_session_id, "Not available")} />
                    <Detail label="Repository or target" value={workflow.repository || workflow.target_id || "Not available"} />
                </dl>
            </details>
            <div className="mt-4">
                <h4 id={railId} className="mb-2 text-sm font-semibold text-slate-200">Progress</h4>
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
