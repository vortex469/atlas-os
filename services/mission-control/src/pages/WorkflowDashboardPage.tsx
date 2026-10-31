import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { FormEvent } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";

import { getAtlasAgentErrorMessage, listWorkflows } from "../api/atlas-agent";
import { WorkflowMiniRail } from "../components/WorkflowMiniRail";
import type { WorkflowListResponse, WorkflowSummary } from "../types/atlasAgent";
import { safeText } from "../utils/safeText";
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
    workflowOperatorStepState,
} from "../utils/workflowState";
import type { WorkflowOperatorStepState } from "../utils/workflowState";

const PAGE_SIZE = 10;
const WORKFLOW_BATCH_SIZE = 200;

type LoadMode = "initial" | "manual" | "automatic";

interface DashboardFilters {
    state: string;
    source: string;
    candidateId: string;
    workflowId: string;
    operatorStep: "" | WorkflowOperatorStepState;
}

const EMPTY_FILTERS: DashboardFilters = {
    state: "",
    source: "",
    candidateId: "",
    workflowId: "",
    operatorStep: "",
};

const DASHBOARD_FILTER_QUERY_KEYS = [
    "status",
    "source",
    "candidate",
    "workflow",
    "step",
    "draftStatus",
    "draftSource",
    "draftCandidate",
    "draftWorkflow",
    "draftStep",
    "page",
] as const;

interface DashboardViewState {
    filters: DashboardFilters;
    draftFilters: DashboardFilters;
    pageIndex: number;
}

const SUMMARY_GROUPS = [
    { key: "running", label: "Running" },
    { key: "needs_input", label: "Needs your input" },
    { key: "blocked", label: "Blocked" },
    { key: "rejected", label: "Rejected" },
    { key: "completed", label: "Completed" },
    { key: "unknown", label: "Status unavailable" },
];

export function WorkflowDashboardPage() {
    const location = useLocation();
    const navigate = useNavigate();
    const [initialViewState] = useState(() => workflowDashboardViewState(location.search));
    const [workflowResponse, setWorkflowResponse] = useState<WorkflowListResponse | null>(null);
    const [draftFilters, setDraftFilters] = useState<DashboardFilters>(initialViewState.draftFilters);
    const [filters, setFilters] = useState<DashboardFilters>(initialViewState.filters);
    const [pageIndex, setPageIndex] = useState(initialViewState.pageIndex);
    const [isLoading, setIsLoading] = useState(true);
    const [refreshMode, setRefreshMode] = useState<Exclude<LoadMode, "initial"> | null>(null);
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
        if (mode !== "initial") setRefreshMode(mode);
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
            if (mode !== "initial") setRefreshMode(null);
        }
    }, []);

    useEffect(() => {
        void Promise.resolve().then(() => loadDashboard());
    }, [loadDashboard]);

    const workflows = useMemo(() => workflowResponse?.items ?? [], [workflowResponse]);
    const hasActiveWorkflow = workflows.some((workflow) => isActiveWorkflowState(workflow.workflow_state));
    const hasMoreWorkflows = workflowResponse !== null && workflows.length > 0 && nextWorkflowOffset < workflowResponse.total;
    const autoRefreshEnabled = hasActiveWorkflow && workflows.length <= WORKFLOW_BATCH_SIZE;

    useEffect(() => {
        if (!autoRefreshEnabled) return undefined;
        const interval = window.setInterval(() => {
            void loadDashboard("automatic");
        }, 5_000);
        return () => window.clearInterval(interval);
    }, [autoRefreshEnabled, loadDashboard]);

    const hasAppliedMoreFilters = Boolean(filters.source || filters.candidateId || filters.workflowId);
    const hasUnappliedFilters = !dashboardFiltersEqual(draftFilters, filters);

    const filteredWorkflows = useMemo(() => {
        return workflows.filter((workflow) => {
            if (filters.state && workflow.workflow_state !== filters.state) return false;
            if (filters.source && workflow.workflow_source !== filters.source) return false;
            if (filters.candidateId && !workflow.candidate_id?.toLowerCase().includes(filters.candidateId.toLowerCase())) return false;
            if (filters.workflowId && !workflow.workflow_id.toLowerCase().includes(filters.workflowId.toLowerCase())) return false;
            if (filters.operatorStep && workflowOperatorStepState(workflow.workflow_state) !== filters.operatorStep) return false;
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
    const visibleSummaryGroups = SUMMARY_GROUPS.filter((group) => (summaryCounts.get(group.key) ?? 0) > 0);

    const totalPages = Math.max(1, Math.ceil(filteredWorkflows.length / PAGE_SIZE));
    const currentPage = Math.min(pageIndex, totalPages - 1);
    const dashboardSearch = serializeWorkflowDashboardViewState(
        location.search,
        draftFilters,
        filters,
        currentPage,
    );
    const visibleWorkflows = filteredWorkflows.slice(currentPage * PAGE_SIZE, (currentPage + 1) * PAGE_SIZE);
    const firstVisibleWorkflow = filteredWorkflows.length === 0 ? 0 : currentPage * PAGE_SIZE + 1;
    const lastVisibleWorkflow = currentPage * PAGE_SIZE + visibleWorkflows.length;

    useEffect(() => {
        if (isLoading || loadError || dashboardSearch === location.search) return;
        navigate({ pathname: location.pathname, search: dashboardSearch }, { replace: true });
    }, [dashboardSearch, isLoading, loadError, location.pathname, location.search, navigate]);

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
        if (pendingLoad.current || refreshMode !== null) return;
        setPageIndex(0);
        void loadDashboard("manual");
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
                    <p className="mt-2 text-sm text-red-100">Atlas couldn&apos;t load your workflows. Try again to get the latest list.</p>
                    <button type="button" onClick={() => void loadDashboard()} className="mt-4 rounded-lg border border-slate-600 px-4 py-2 text-sm font-semibold text-slate-100 focus:outline-none focus:ring-2 focus:ring-blue-300">
                        Try again
                    </button>
                    <details className="mt-3">
                        <summary className="mc-focusable cursor-pointer text-sm font-medium text-slate-300">Technical details</summary>
                        <p className="mt-2 break-words text-sm text-slate-400">{safeText(loadError) || "No additional details were returned."}</p>
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
                <div className="flex flex-col items-end gap-1">
                    <button
                        type="button"
                        onClick={refresh}
                        disabled={refreshMode !== null || isLoadingMore}
                        aria-describedby={autoRefreshEnabled ? "workflow-auto-refresh-note" : undefined}
                        className="rounded-lg border border-slate-700 px-4 py-2 text-sm font-semibold text-slate-100 transition hover:bg-slate-800 focus:outline-none focus:ring-2 focus:ring-blue-300 disabled:cursor-not-allowed disabled:opacity-60"
                    >
                        Refresh
                    </button>
                    {autoRefreshEnabled && <p id="workflow-auto-refresh-note" className="max-w-64 text-right text-xs text-slate-400">The list checks for updates every 5 seconds while a workflow is running.</p>}
                </div>
            </header>

            {refreshMode === "manual" && <p role="status" aria-live="polite" className="text-sm text-blue-200">Refreshing workflows...</p>}
            {hasMoreWorkflows && <p role="status" className="rounded-lg border border-blue-500/30 bg-blue-500/10 px-4 py-3 text-sm text-blue-100">Loaded {workflows.length} of {workflowResponse?.total ?? 0} workflows. Counts and filters use only the workflows already loaded.</p>}
            {workflows.length > WORKFLOW_BATCH_SIZE && <p role="status" className="rounded-lg border border-slate-700 bg-slate-900/70 px-4 py-3 text-sm text-slate-300">Auto-refresh pauses when you load more than {WORKFLOW_BATCH_SIZE} workflows. Select Refresh to return to the newest {WORKFLOW_BATCH_SIZE}; running workflows there update automatically.</p>}
            {refreshError && (
                <div role="alert" className="rounded-lg border border-amber-500/30 bg-amber-500/10 p-4">
                    <p className="font-semibold text-amber-100">Could not refresh workflows</p>
                    <p className="mt-1 text-sm text-amber-100/80">The list and counts below show the last successfully loaded state. Use Refresh to check again before reviewing a workflow.</p>
                    <details className="mt-3">
                        <summary className="mc-focusable cursor-pointer text-sm font-medium text-slate-300">Technical details</summary>
                        <p className="mt-2 break-words text-sm text-slate-400">{safeText(refreshError) || "No additional details were returned."}</p>
                    </details>
                </div>
            )}

            {visibleSummaryGroups.length > 0 && (
                <section aria-labelledby="workflow-counts-heading" className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
                    <h2 id="workflow-counts-heading" className="sr-only">Workflow summary counts</h2>
                    {visibleSummaryGroups.map((group) => (
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
                                <option value="">Any next step</option>
                                <option value="needed">Needs your input</option>
                                <option value="not_needed">No action needed right now</option>
                                <option value="unknown">Status unavailable</option>
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
                                    <option value="">Any source</option>
                                    <option value="roadmap">Roadmap</option>
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
                    <p role="status" className="rounded-xl border border-slate-800 bg-slate-900/70 p-5 text-sm text-slate-300">
                        {workflowResponse?.total
                            ? "Atlas reports workflows but returned no entries. Select Refresh to try again."
                            : dashboardFiltersEqual(filters, EMPTY_FILTERS)
                                ? "No workflows yet."
                                : "No workflows match the current filters."}
                    </p>
                ) : visibleWorkflows.length === 0 ? (
                    <p className="rounded-xl border border-slate-800 bg-slate-900/70 p-5 text-sm text-slate-300">
                        {hasMoreWorkflows
                            ? "No loaded workflows match these filters. Load more workflows to check older results."
                            : "No workflows match the current filters."}
                    </p>
                ) : (
                    <div className="space-y-4">
                        {visibleWorkflows.map((workflow) => <WorkflowCard key={workflow.workflow_id} workflow={workflow} search={dashboardSearch} />)}
                    </div>
                )}

                {filteredWorkflows.length > PAGE_SIZE && (
                    <nav aria-label="Workflow pagination" className="flex items-center gap-3">
                        <button type="button" onClick={() => setPageIndex(Math.max(0, currentPage - 1))} disabled={hasUnappliedFilters || currentPage === 0} className="rounded-lg border border-slate-700 px-3 py-2 text-sm text-slate-100 disabled:cursor-not-allowed disabled:opacity-50">Previous</button>
                        <span className="text-sm text-slate-400">Page {currentPage + 1} of {totalPages}</span>
                        <button type="button" onClick={() => setPageIndex(Math.min(totalPages - 1, currentPage + 1))} disabled={hasUnappliedFilters || currentPage >= totalPages - 1} className="rounded-lg border border-slate-700 px-3 py-2 text-sm text-slate-100 disabled:cursor-not-allowed disabled:opacity-50">Next</button>
                    </nav>
                )}
                {loadMoreError && <p role="alert" className="rounded-lg border border-red-500/30 bg-red-500/10 p-4 text-sm text-red-100">{loadMoreError}</p>}
                {hasMoreWorkflows && <button type="button" onClick={() => void loadMoreWorkflows()} disabled={isLoadingMore || refreshMode !== null} className="rounded-lg border border-slate-700 px-4 py-2 text-sm font-semibold text-slate-100 disabled:cursor-not-allowed disabled:opacity-60">{isLoadingMore ? "Loading more workflows…" : "Load more workflows"}</button>}
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

function workflowDashboardViewState(search: string): DashboardViewState {
    const params = new URLSearchParams(search);
    const filters = readDashboardFilters(params);
    const draftFilters = readDashboardFilters(params, "draft", filters);
    const rawPage = Number(params.get("page"));
    return {
        filters,
        draftFilters,
        pageIndex: Number.isSafeInteger(rawPage) && rawPage >= 1 ? rawPage - 1 : 0,
    };
}

function readDashboardFilters(
    params: URLSearchParams,
    prefix = "",
    fallback = EMPTY_FILTERS,
): DashboardFilters {
    const key = (name: string) => prefix ? `${prefix}${name[0].toUpperCase()}${name.slice(1)}` : name;
    const state = params.has(key("status")) ? params.get(key("status")) ?? "" : fallback.state;
    const source = params.has(key("source")) ? params.get(key("source")) ?? "" : fallback.source;
    const operatorStep = params.has(key("step")) ? params.get(key("step")) ?? "" : fallback.operatorStep;
    return {
        state: WORKFLOW_STATES.includes(state as typeof WORKFLOW_STATES[number]) ? state : fallback.state,
        source: source === "roadmap" || source === "candidate" || source === "manual" ? source : fallback.source,
        candidateId: (params.has(key("candidate")) ? params.get(key("candidate")) ?? "" : fallback.candidateId).slice(0, 200),
        workflowId: (params.has(key("workflow")) ? params.get(key("workflow")) ?? "" : fallback.workflowId).slice(0, 200),
        operatorStep: operatorStep === "needed" || operatorStep === "not_needed" || operatorStep === "unknown"
            ? operatorStep
            : operatorStep === "" ? "" : fallback.operatorStep,
    };
}

function serializeWorkflowDashboardViewState(
    currentSearch: string,
    draftFilters: DashboardFilters,
    filters: DashboardFilters,
    pageIndex: number,
): string {
    const params = new URLSearchParams(currentSearch);
    for (const key of DASHBOARD_FILTER_QUERY_KEYS) params.delete(key);

    const appliedValues: Array<[keyof DashboardFilters, string]> = [
        ["state", filters.state],
        ["source", filters.source],
        ["candidateId", filters.candidateId],
        ["workflowId", filters.workflowId],
        ["operatorStep", filters.operatorStep],
    ];
    const queryNames: Record<keyof DashboardFilters, string> = {
        state: "status",
        source: "source",
        candidateId: "candidate",
        workflowId: "workflow",
        operatorStep: "step",
    };

    for (const [name, value] of appliedValues) {
        if (value) params.set(queryNames[name], value);
        const draftValue = draftFilters[name];
        if (draftValue !== value) params.set(`draft${queryNames[name][0].toUpperCase()}${queryNames[name].slice(1)}`, draftValue);
    }
    if (pageIndex > 0) params.set("page", String(pageIndex + 1));

    const serialized = params.toString();
    return serialized ? `?${serialized}` : "";
}

function workflowDetailSearch(search: string): string {
    const params = new URLSearchParams(search);
    params.set("returnTo", "/workflows");
    return `?${params.toString()}`;
}

function workflowDashboardSummaryGroup(state: string): string {
    switch (state) {
        case "planned":
        case "awaiting_approval":
        case "awaiting_implementation_approval":
        case "awaiting_execution":
        case "awaiting_verification_approval":
        case "awaiting_commit_approval":
            return "needs_input";
        default:
            return workflowStatusGroup(state);
    }
}

function WorkflowCard({ workflow, search }: { workflow: WorkflowSummary; search: string }) {
    const nextStep = workflowNextStepLabel(workflow.workflow_state, workflow.effect_kind);
    const workflowStatusUnavailable = workflowStatusGroup(workflow.workflow_state) === "unknown";
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
                    <p className="mt-1 text-sm text-slate-400">Stage: {workflowStatusUnavailable ? "Status unavailable" : workflowStageLabel(workflow.workflow_state, workflow.effect_kind)}</p>
                </div>
                <Link to={{ pathname: `/workflows/${encodeURIComponent(workflow.workflow_id)}`, search: workflowDetailSearch(search) }} state={{ returnTo: "/workflows" }} className="rounded-lg border border-blue-400/60 px-3 py-2 text-sm font-semibold text-blue-100 transition hover:bg-blue-500/10 focus:outline-none focus:ring-2 focus:ring-blue-300">
                    {workflow.effect_kind === "operational_action" ? "Review maintenance request" : "Open workflow"}
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
                    {workflowStatusUnavailable && <Detail label="Reported workflow status" value={workflow.workflow_state} />}
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
