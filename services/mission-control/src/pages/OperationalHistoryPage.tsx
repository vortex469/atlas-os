import { useCallback, useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";

import {
    getWorkflowOperationalLifecycle,
    getWorkflowRecoveryDiagnostic,
    listWorkflows,
} from "../api/atlas-agent";
import { OperationalRecoverySummary } from "../components/OperationalRecoverySummary";
import { recoveryPresentation } from "../utils/recoveryDiagnostic";
import { formatResourceTypeLabel } from "../utils/resourceLabels";
import { formatWorkflowLabel } from "../utils/workflowState";
import type {
    WorkflowOperationalLifecycle,
    WorkflowRecoveryDiagnostic,
    WorkflowSummary,
} from "../types/atlasAgent";

const PAGE_SIZE = 10;

interface HistoryItem {
    workflow: WorkflowSummary;
    lifecycle: WorkflowOperationalLifecycle | null;
    lifecycleUnavailable: boolean;
    diagnostic: WorkflowRecoveryDiagnostic | null;
    diagnosticUnavailable: boolean;
}

function formatTimestamp(value: string | null): string {
    if (!value) return "Not reported";
    const parsed = new Date(value);
    return Number.isNaN(parsed.getTime()) ? "Unknown time" : parsed.toLocaleString();
}

function historyTargetName(workflow: WorkflowSummary, lifecycle: WorkflowOperationalLifecycle | null): string {
    const targetParts = lifecycle?.target_label?.split("/");
    const isStructuredTarget = targetParts?.length === 3
        && targetParts[0] === lifecycle?.provider_id
        && targetParts[1] === lifecycle?.resource_type
        && targetParts[2] === lifecycle?.resource_id;
    if (isStructuredTarget && lifecycle?.resource_id) {
        return `${formatResourceTypeLabel(lifecycle.resource_type)} ${lifecycle.resource_id}`;
    }
    if (lifecycle?.target_label) return lifecycle.target_label;
    if (!workflow.target_id) return "Maintenance target";
    return /^(VM|Virtual machine|Container)\b/i.test(workflow.target_id)
        ? workflow.target_id
        : "Maintenance target " + workflow.target_id;
}

export function OperationalHistoryPage() {
    const [items, setItems] = useState<HistoryItem[]>([]);
    const [offset, setOffset] = useState(0);
    const [total, setTotal] = useState(0);
    const [isLoading, setIsLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [diagnosticFilter, setDiagnosticFilter] = useState("all");
    const [terminalFilter, setTerminalFilter] = useState("all");
    const [intentFilter, setIntentFilter] = useState("all");
    const [providerFilter, setProviderFilter] = useState("all");
    const [resourceTypeFilter, setResourceTypeFilter] = useState("all");

    const requestGeneration = useRef(0);
    const load = useCallback(async () => {
        const generation = ++requestGeneration.current;
        setIsLoading(true);
        setError(null);
        try {
            const page = await listWorkflows({
                effect_kind: "operational_action",
                limit: PAGE_SIZE,
                offset,
            });
            if (generation !== requestGeneration.current) return;
            const evidence = await Promise.all(
                page.items.map(async (workflow) => {
                    const [lifecycle, diagnostic] = await Promise.all([
                        getWorkflowOperationalLifecycle(workflow.workflow_id)
                            .then((value) => ({ value, unavailable: false }))
                            .catch(() => ({ value: null, unavailable: true })),
                        getWorkflowRecoveryDiagnostic(workflow.workflow_id)
                            .then((value) => ({ value, unavailable: false }))
                            .catch(() => ({ value: null, unavailable: true })),
                    ]);
                    const matchingLifecycle = lifecycle.value?.workflow_id === workflow.workflow_id ? lifecycle.value : null;
                    const matchingDiagnostic = diagnostic.value?.correlation?.workflow_id === workflow.workflow_id ? diagnostic.value : null;
                    return { lifecycle: matchingLifecycle,
                        lifecycleUnavailable: lifecycle.unavailable || (lifecycle.value !== null && matchingLifecycle === null),
                        diagnostic: matchingDiagnostic,
                        diagnosticUnavailable: diagnostic.unavailable || (diagnostic.value !== null && matchingDiagnostic === null) };
                }),
            );
            if (generation !== requestGeneration.current) return;
            setItems(page.items.map((workflow, index) => ({ workflow, ...evidence[index] })));
            setTotal(page.total);
        } catch {
            if (generation === requestGeneration.current) setError("Could not load maintenance history.");
        } finally {
            if (generation === requestGeneration.current) setIsLoading(false);
        }
    }, [offset]);

    useEffect(() => {
        let active = true;
        void Promise.resolve().then(() => { if (active) return load(); });
        return () => { active = false; requestGeneration.current += 1; };
    }, [load]);

    const visibleItems = items.filter(({ workflow, lifecycle, diagnostic, diagnosticUnavailable }) =>
        (diagnosticFilter === "all" || diagnostic?.diagnostic_status === diagnosticFilter
            || (diagnosticFilter === "unavailable" && diagnosticUnavailable))
        && (terminalFilter === "all" || (terminalFilter === "terminal") === lifecycle?.terminal)
        && (intentFilter === "all" || workflow.execution_intent === intentFilter)
        && (providerFilter === "all" || lifecycle?.provider_id === providerFilter)
        && (resourceTypeFilter === "all" || lifecycle?.resource_type === resourceTypeFilter));
    const hasActiveMoreFilters = terminalFilter !== "all" || intentFilter !== "all"
        || providerFilter !== "all" || resourceTypeFilter !== "all";
    const hasActiveFilters = diagnosticFilter !== "all" || hasActiveMoreFilters;
    const intentOptions = distinctFilterOptions(items.map(({ workflow }) => workflow.execution_intent), intentFilter);
    const providerOptions = distinctFilterOptions(items.map(({ lifecycle }) => lifecycle?.provider_id ?? null), providerFilter);
    const resourceTypeOptions = distinctFilterOptions(items.map(({ lifecycle }) => lifecycle?.resource_type ?? null), resourceTypeFilter);

    function clearFilters() {
        setDiagnosticFilter("all");
        setTerminalFilter("all");
        setIntentFilter("all");
        setProviderFilter("all");
        setResourceTypeFilter("all");
    }

    return (
        <main className="mx-auto max-w-7xl space-y-6 p-4 sm:p-8">
            <header className="flex flex-wrap items-start justify-between gap-4 border-b border-slate-800 pb-6">
                <div><p className="text-xs font-semibold uppercase tracking-[0.2em] text-cyan-400">Maintenance</p><h1 className="mt-2 text-3xl font-semibold text-white">Maintenance history</h1><p className="mt-2 max-w-3xl text-sm text-slate-400">Review past requests and the latest service status Atlas reported.</p></div>
                <div className="flex gap-3"><Link to="/operations/request" className="rounded-lg border border-cyan-400/60 px-3 py-2 text-sm font-semibold text-cyan-100">Request maintenance</Link><button type="button" onClick={() => void load()} disabled={isLoading} className="rounded-lg border border-slate-700 px-3 py-2 text-sm font-semibold text-slate-100 disabled:opacity-50">Refresh history</button></div>
            </header>
            {isLoading && <p role="status" className="text-slate-300">Loading operational history...</p>}
            {error && <p role="alert" className="rounded-lg border border-red-500/30 bg-red-500/10 p-4 text-red-100">{error} The maintenance outcome is unknown. Use Refresh history to check again.</p>}
            {!isLoading && !error && items.length === 0 && <p className="rounded-xl border border-slate-800 bg-slate-900/70 p-5 text-slate-300">{offset === 0 ? "No maintenance requests yet." : "No requests on this page. Go back to an earlier page."}</p>}
            {!isLoading && !error && items.length > 0 && <section aria-label="Operational history filters" className="space-y-4 rounded-xl border border-slate-800 bg-slate-900/70 p-4">
                <p className="text-sm text-slate-400">Filters only narrow the requests shown on this page. Use Previous and Next to check other pages.</p>
                <div className="grid gap-3 sm:grid-cols-2">
                    <Filter label="Current status" value={diagnosticFilter} onChange={setDiagnosticFilter} options={["all", "healthy", "pending", "recovery_in_progress", "attention_required", "outcome_uncertain", "unavailable"]} />
                </div>
                <details className="rounded-lg border border-slate-800 px-4 py-3">
                    <summary className="cursor-pointer text-sm font-medium text-slate-200">
                        More filters
                        {hasActiveMoreFilters && <span className="ml-2 text-xs font-normal text-amber-200">Additional filters are applied</span>}
                    </summary>
                    <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
                        <Filter label="Completion" value={terminalFilter} onChange={setTerminalFilter} options={["all", "terminal", "non_terminal"]} />
                        {intentOptions && <Filter label="Requested action" value={intentFilter} onChange={setIntentFilter} options={intentOptions} />}
                        {providerOptions && <Filter label="Provider" value={providerFilter} onChange={setProviderFilter} options={providerOptions} />}
                        {resourceTypeOptions && <Filter label="Resource type" value={resourceTypeFilter} onChange={setResourceTypeFilter} options={resourceTypeOptions} />}
                    </div>
                </details>
                {hasActiveFilters && <div className="flex justify-end"><button type="button" onClick={clearFilters} className="rounded-lg border border-slate-600 px-3 py-2 text-sm font-semibold text-slate-100">Clear filters</button></div>}
            </section>}
            {!isLoading && !error && items.length > 0 && visibleItems.length === 0 && <section className="rounded-xl border border-slate-800 bg-slate-900/70 p-5 text-slate-300"><p>No requests on this page match your filters.</p></section>}
            {!isLoading && !error && <section aria-label="Maintenance history" className="space-y-4">{visibleItems.map((item) => <OperationalHistoryCard key={item.workflow.workflow_id} {...item} />)}</section>}
            {!isLoading && !error && (offset > 0 || total > PAGE_SIZE) && <nav aria-label="Operational history pagination" className="flex items-center gap-3"><button type="button" onClick={() => setOffset((current) => Math.max(0, current - PAGE_SIZE))} disabled={offset === 0} className="rounded-lg border border-slate-700 px-3 py-2 text-sm text-slate-100 disabled:opacity-50">Previous</button><span className="text-sm text-slate-400">{items.length > 0 ? `Showing ${offset + 1}–${Math.min(offset + PAGE_SIZE, total)} of ${total}` : `${total} request${total === 1 ? "" : "s"} total`}</span><button type="button" onClick={() => setOffset((current) => current + PAGE_SIZE)} disabled={offset + PAGE_SIZE >= total} className="rounded-lg border border-slate-700 px-3 py-2 text-sm text-slate-100 disabled:opacity-50">Next</button></nav>}
        </main>
    );
}

function OperationalHistoryCard({ workflow, lifecycle, lifecycleUnavailable, diagnostic, diagnosticUnavailable }: HistoryItem) {
    const outcome = diagnostic ? recoveryPresentation(diagnostic) : null;
    const resultTimestamp = lifecycle?.verification_completed_at ?? lifecycle?.dispatch_completed_at ?? null;
    const action = workflow.execution_intent
        ? formatWorkflowLabel(workflow.execution_intent)
        : "Maintenance request";
    return (
        <article className="space-y-4 rounded-xl border border-slate-800 bg-slate-900/70 p-5">
            <div className="flex flex-wrap items-start justify-between gap-4">
                <div>
                    <h2 className="break-all text-lg font-semibold text-white">{historyTargetName(workflow, lifecycle)}</h2>
                    <p className="mt-1 text-sm text-slate-400">Requested action: {action} · Current status: {outcome?.title ?? "Unavailable"}</p>
                    <p className="mt-1 text-sm text-slate-400">Requested (local time): {formatTimestamp(lifecycle?.request_created_at ?? null)}</p>
                </div>
                <Link to={`/workflows/${encodeURIComponent(workflow.workflow_id)}`} className="rounded-lg border border-blue-400/60 px-3 py-2 text-sm font-semibold text-blue-100">Open workflow</Link>
            </div>
            {lifecycleUnavailable && <p className="rounded-lg border border-amber-500/30 bg-amber-500/10 p-3 text-sm text-amber-100">Could not load request details. Target and timing information may be incomplete. Use Refresh history to try again.</p>}
            <OperationalRecoverySummary diagnostic={diagnostic} error={diagnosticUnavailable ? "Could not load the latest status for this request." : null} supportEvidenceAvailable={diagnostic !== null} compact />
            <details className="rounded-lg border border-slate-800 p-3">
                <summary className="cursor-pointer text-sm font-medium text-slate-200">Request details</summary>
                <dl className="mt-3 grid gap-3 text-sm md:grid-cols-2 xl:grid-cols-3">
                    <HistoryDetail label="Request stage" value={maintenanceStageLabel(workflow.workflow_state)} />
                    <HistoryDetail label="Status record check" value={diagnostic ? consistencyLabel(diagnostic.consistency) : "Not available"} />
                    <HistoryDetail label="Verification result" value={verificationLabel(lifecycle?.verification_status ?? null)} />
                    <HistoryDetail label="Support evidence" value={diagnostic ? "Available" : "Unavailable"} />
                    <HistoryDetail label="Result recorded (local time)" value={formatTimestamp(resultTimestamp)} />
                    <HistoryDetail label="Target reference" value={lifecycle?.target_label ?? workflow.target_id ?? "Not reported"} />
                </dl>
            </details>
        </article>
    );
}

function consistencyLabel(value: WorkflowRecoveryDiagnostic["consistency"]): string {
    const labels: Record<WorkflowRecoveryDiagnostic["consistency"], string> = {
        consistent: "Records match",
        agent_only: "Matching service record not found",
        core_unavailable: "Status service unavailable",
        immutable_mismatch: "Request details differ",
        transition_mismatch: "Status history is out of order",
        terminal_mismatch: "Completion status differs",
    };
    return labels[value];
}

function verificationLabel(value: string | null): string {
    if (value === null) return "Not reported";
    const labels: Record<string, string> = {
        failed: "Did not pass",
        not_applicable: "Not applicable",
        not_started: "Not started",
        passed: "Passed",
        pending: "In progress",
        succeeded: "Passed",
    };
    return labels[value] ?? value.replaceAll(/[_-]+/g, " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function HistoryDetail({ label, value }: { label: string; value: string }) {
    return <div><dt className="text-xs uppercase tracking-wide text-slate-500">{label}</dt><dd className="mt-1 break-all text-slate-200">{value.replaceAll("_", " ")}</dd></div>;
}

function maintenanceStageLabel(value: string): string {
    const labels: Record<string, string> = {
        planned: "Ready for review",
        awaiting_approval: "Waiting for review",
        awaiting_implementation_approval: "Waiting for maintenance approval",
        awaiting_execution: "Approved and ready to run",
        executing: "Running",
        awaiting_verification_approval: "Waiting for verification approval",
        verifying: "Checking the result",
        awaiting_commit_approval: "Waiting for commit approval",
        committing: "Recording commit",
        blocked: "Blocked",
        implementation_rejected: "Request rejected",
        completed: "Completed",
    };
    return labels[value] ?? value.replaceAll(/[_-]+/g, " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}

const FILTER_LABELS: Record<string, string> = {
    all: "Any", healthy: "Healthy", pending: "Pending", recovery_in_progress: "Recovering",
    attention_required: "Needs attention", outcome_uncertain: "Result unknown", unavailable: "Unavailable",
    terminal: "Finished", non_terminal: "In progress", "restart-service": "Restart Service",
    proxmox: "Proxmox", qemu: "Virtual machine", lxc: "Container",
};

function Filter({ label, value, onChange, options }: { label: string; value: string; onChange: (value: string) => void; options: string[] }) {
    return <label className="text-sm text-slate-300">{label}<select aria-label={label} value={value} onChange={(event) => onChange(event.target.value)} className="mt-1 block w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-slate-100">{options.map((option) => <option key={option} value={option}>{filterOptionLabel(option)}</option>)}</select></label>;
}

function distinctFilterOptions(values: Array<string | null | undefined>, selected: string): string[] | null {
    const distinct = [...new Set(values.filter((value): value is string => Boolean(value)))].sort();
    if (distinct.length < 2 && selected === "all") return null;
    if (selected !== "all" && !distinct.includes(selected)) distinct.push(selected);
    return ["all", ...distinct.sort()];
}

function filterOptionLabel(value: string): string {
    if (FILTER_LABELS[value]) return FILTER_LABELS[value];
    return value.replaceAll(/[_-]+/g, " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}
