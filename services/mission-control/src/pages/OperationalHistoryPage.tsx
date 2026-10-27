import { useCallback, useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";

import {
    getWorkflowOperationalLifecycle,
    getWorkflowRecoveryDiagnostic,
    listWorkflows,
} from "../api/atlas-agent";
import { OperationalRecoverySummary } from "../components/OperationalRecoverySummary";
import { recoveryPresentation } from "../utils/recoveryDiagnostic";
import { evidenceTimestamp } from "../utils/healthPresentation";
import type {
    WorkflowOperationalLifecycle,
    WorkflowRecoveryDiagnostic,
    WorkflowSummary,
    WorkflowListResponse,
} from "../types/atlasAgent";

const PAGE_SIZE = 10;

interface HistoryItem {
    workflow: WorkflowSummary;
    lifecycle: WorkflowOperationalLifecycle | null;
    diagnostic: WorkflowRecoveryDiagnostic | null;
    diagnosticUnavailable: boolean;
}

function formatTimestamp(value: string | null): string {
    if (!value) return "Not reported";
    const parsed = evidenceTimestamp(value);
    return parsed === null || parsed > Date.now() ? "Unknown time" : new Date(parsed).toLocaleString();
}

function isReadableHistoryRecord(workflow: WorkflowSummary): boolean {
    if (!workflow || typeof workflow !== "object" || Array.isArray(workflow)
        || typeof workflow.workflow_id !== "string" || !workflow.workflow_id.trim()
        || workflow.workflow_id === "." || workflow.workflow_id === ".."
        || typeof workflow.workflow_state !== "string"
        || workflow.effect_kind !== "operational_action") return false;
    try {
        encodeURIComponent(workflow.workflow_id);
    } catch {
        return false;
    }
    return [workflow.execution_intent, workflow.target_id]
        .every(value => value === null || value === undefined || typeof value === "string");
}

function validateHistoryPage(page: WorkflowListResponse, offset: number): void {
    if (!page || typeof page !== "object" || Array.isArray(page) || !Array.isArray(page.items)
        || !Number.isSafeInteger(page.total) || page.total < 0 || page.limit !== PAGE_SIZE || page.offset !== offset
        || page.items.length > PAGE_SIZE || page.items.some(item => !isReadableHistoryRecord(item))
        || new Set(page.items.map(item => item.workflow_id)).size !== page.items.length
        || (offset < page.total && page.items.length !== Math.min(PAGE_SIZE, page.total - offset))
        || (offset >= page.total && page.items.length !== 0)) {
        throw new Error("Maintenance history page is unreadable or inconsistent.");
    }
}

function isReadableLifecycle(lifecycle: WorkflowOperationalLifecycle | null, workflowId: string): boolean {
    return lifecycle !== null && typeof lifecycle === "object" && !Array.isArray(lifecycle)
        && lifecycle.workflow_id === workflowId
        && [lifecycle.target_label, lifecycle.verification_status]
            .every(value => value === null || value === undefined || typeof value === "string");
}

export function OperationalHistoryPage() {
    const [snapshot, setSnapshot] = useState<{ items: HistoryItem[]; total: number; offset: number } | null>(null);
    const [offset, setOffset] = useState(0);

    const [isLoading, setIsLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [diagnosticFilter, setDiagnosticFilter] = useState("all");
    const [terminalFilter, setTerminalFilter] = useState("all");
    const [intentFilter, setIntentFilter] = useState("all");
    const [providerFilter, setProviderFilter] = useState("all");
    const [resourceTypeFilter, setResourceTypeFilter] = useState("all");

    const items = snapshot?.items ?? [];
    const total = snapshot?.total ?? 0;
    const displayOffset = snapshot?.offset ?? offset;
    const retained = snapshot !== null && (isLoading || error !== null);

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
            validateHistoryPage(page, offset);
            const evidence = await Promise.all(
                page.items.map(async (workflow) => {
                    const [lifecycle, diagnostic] = await Promise.all([
                        getWorkflowOperationalLifecycle(workflow.workflow_id).catch(() => null),
                        getWorkflowRecoveryDiagnostic(workflow.workflow_id)
                            .then((value) => ({ value, unavailable: false }))
                            .catch(() => ({ value: null, unavailable: true })),
                    ]);
                    const matchingLifecycle = isReadableLifecycle(lifecycle, workflow.workflow_id) ? lifecycle : null;
                    const matchingDiagnostic = diagnostic.value?.correlation?.workflow_id === workflow.workflow_id ? diagnostic.value : null;
                    return { lifecycle: matchingLifecycle, diagnostic: matchingDiagnostic,
                        diagnosticUnavailable: diagnostic.unavailable || (diagnostic.value !== null && matchingDiagnostic === null) };
                }),
            );
            if (generation !== requestGeneration.current) return;
            setSnapshot({ items: page.items.map((workflow, index) => ({ workflow, ...evidence[index] })), total: page.total, offset });
        } catch {
            if (generation === requestGeneration.current) setError("Could not load maintenance history. Refresh to try again.");
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
            || (diagnosticFilter === "unavailable" && (diagnosticUnavailable || diagnostic === null)))
        && (terminalFilter === "all" || (typeof lifecycle?.terminal === "boolean" && (terminalFilter === "terminal") === lifecycle.terminal))
        && (intentFilter === "all" || workflow.execution_intent === intentFilter)
        && (providerFilter === "all" || lifecycle?.provider_id === providerFilter)
        && (resourceTypeFilter === "all" || lifecycle?.resource_type === resourceTypeFilter));

    function goToPage(nextOffset: number) {
        if (isLoading) return;
        if (nextOffset === offset) void load();
        else setOffset(nextOffset);
    }

    function clearFilters() {
        setDiagnosticFilter("all");
        setTerminalFilter("all");
        setIntentFilter("all");
        setProviderFilter("all");
        setResourceTypeFilter("all");
    }

    return (
        <main className="mx-auto max-w-7xl space-y-6 p-8">
            <header className="flex flex-wrap items-start justify-between gap-4 border-b border-slate-800 pb-6">
                <div><p className="text-xs font-semibold uppercase tracking-[0.2em] text-cyan-400">Maintenance</p><h1 className="mt-2 text-3xl font-semibold text-white">Maintenance history</h1><p className="mt-2 max-w-3xl text-sm text-slate-400">See past maintenance requests and their latest results.</p></div>
                <div className="flex gap-3"><Link to="/operations/request" className="rounded-lg border border-cyan-400/60 px-3 py-2 text-sm font-semibold text-cyan-100">Request maintenance</Link><button type="button" onClick={() => void load()} disabled={isLoading} className="rounded-lg border border-slate-700 px-3 py-2 text-sm font-semibold text-slate-100 disabled:opacity-50">Refresh history</button></div>
            </header>
            {isLoading && <p role="status" className="text-slate-300">{snapshot === null ? "Loading operational history..." : "Checking maintenance history…"}</p>}
            {retained && <p role="status" className="rounded-lg border border-amber-500/30 bg-amber-500/10 p-4 text-amber-200">Showing the last loaded maintenance history. Current results have not been confirmed.</p>}
            {error && <p role="alert" className="rounded-lg border border-red-500/30 bg-red-500/10 p-4 text-red-100">{error} A loading problem does not tell us whether maintenance failed.</p>}
            {snapshot !== null && items.length === 0 && <p className="rounded-xl border border-slate-800 bg-slate-900/70 p-5 text-slate-300">{retained ? "No requests in the last loaded page. Current results have not been confirmed." : displayOffset === 0 ? "No maintenance requests yet." : "No requests on this page. Go back to an earlier page."}</p>}
            {snapshot !== null && items.length > 0 && <section aria-label="Operational history filters" className="grid gap-3 rounded-xl border border-slate-800 bg-slate-900/70 p-4 sm:grid-cols-2 xl:grid-cols-5"><Filter label="Status" value={diagnosticFilter} onChange={setDiagnosticFilter} options={["all", "healthy", "pending", "recovery_in_progress", "attention_required", "outcome_uncertain", "unavailable"]} /><Filter label="Completion" value={terminalFilter} onChange={setTerminalFilter} options={["all", "terminal", "non_terminal"]} /><Filter label="Action" value={intentFilter} onChange={setIntentFilter} options={["all", "restart-service"]} /><Filter label="Provider" value={providerFilter} onChange={setProviderFilter} options={["all", "proxmox"]} /><Filter label="Resource type" value={resourceTypeFilter} onChange={setResourceTypeFilter} options={["all", "qemu"]} /></section>}
            {snapshot !== null && items.length > 0 && visibleItems.length === 0 && <section className="rounded-xl border border-slate-800 bg-slate-900/70 p-5 text-slate-300"><p>{retained ? "No requests in the last loaded page match your filters." : "No requests on this page match your filters."}</p><button type="button" onClick={clearFilters} className="mt-3 rounded-lg border border-slate-600 px-3 py-2 text-sm font-semibold">Clear filters</button></section>}
            {snapshot !== null && <section aria-label="Maintenance history" className="space-y-4">{visibleItems.map((item) => <OperationalHistoryCard key={item.workflow.workflow_id} {...item} retained={retained} />)}</section>}
            {snapshot !== null && (displayOffset > 0 || total > PAGE_SIZE) && <nav aria-label="Operational history pagination" className="flex items-center gap-3"><button type="button" onClick={() => goToPage(Math.max(0, displayOffset - PAGE_SIZE))} disabled={isLoading || displayOffset === 0} className="rounded-lg border border-slate-700 px-3 py-2 text-sm text-slate-100 disabled:opacity-50">Previous</button><span className="text-sm text-slate-400">{retained && "Last loaded: "}{items.length > 0 ? `Showing ${displayOffset + 1}–${Math.min(displayOffset + items.length, total)} of ${total}` : `${total} request${total === 1 ? "" : "s"} total`}</span><button type="button" onClick={() => goToPage(displayOffset + PAGE_SIZE)} disabled={isLoading || displayOffset + PAGE_SIZE >= total} className="rounded-lg border border-slate-700 px-3 py-2 text-sm text-slate-100 disabled:opacity-50">Next</button></nav>}
        </main>
    );
}

function OperationalHistoryCard({ workflow, lifecycle, diagnostic, diagnosticUnavailable, retained = false }: HistoryItem & { retained?: boolean }) {
    const outcome = diagnostic ? recoveryPresentation(diagnostic) : null;
    const resultTimestamp = lifecycle?.verification_completed_at ?? lifecycle?.dispatch_completed_at ?? null;
    const action = workflow.execution_intent === "restart-service" ? "Restart service" : workflow.execution_intent ?? "Maintenance request";
    return (
        <article className="space-y-4 rounded-xl border border-slate-800 bg-slate-900/70 p-5">
            <div className="flex flex-wrap items-start justify-between gap-4">
                <div>
                    <h2 className="break-all text-lg font-semibold text-white">{lifecycle?.target_label ?? workflow.target_id ?? "Maintenance target"}</h2>
                    <p className="mt-1 text-sm text-slate-400">{retained && "Last loaded result: "}{action} · {outcome?.title ?? "Status unavailable"}</p>
                    <p className="mt-1 text-sm text-slate-400">Requested: {formatTimestamp(lifecycle?.request_created_at ?? null)}</p>
                </div>
                <Link to={`/workflows/${encodeURIComponent(workflow.workflow_id)}`} className="rounded-lg border border-blue-400/60 px-3 py-2 text-sm font-semibold text-blue-100">Open workflow</Link>
            </div>
            <OperationalRecoverySummary diagnostic={diagnostic} error={diagnosticUnavailable ? "Could not load the latest status for this request." : null} supportEvidenceAvailable={diagnostic !== null} compact retained={retained} />
            <details className="rounded-lg border border-slate-800 p-3">
                <summary className="cursor-pointer text-sm font-medium text-slate-200">{retained ? "Last loaded workflow details" : "Workflow details"}</summary>
                <dl className="mt-3 grid gap-3 text-sm md:grid-cols-2 xl:grid-cols-3">
                    <HistoryDetail label="Workflow State" value={workflow.workflow_state} />
                    <HistoryDetail label="Consistency" value={diagnostic?.consistency ?? "unavailable"} />
                    <HistoryDetail label="Verification" value={lifecycle?.verification_status ?? "Not reported"} />
                    <HistoryDetail label="Support Evidence" value={diagnostic ? "Available" : "Unavailable"} />
                    <HistoryDetail label="Result recorded" value={formatTimestamp(resultTimestamp)} />
                </dl>
            </details>
        </article>
    );
}

function HistoryDetail({ label, value }: { label: string; value: string }) {
    return <div><dt className="text-xs uppercase tracking-wide text-slate-500">{label}</dt><dd className="mt-1 break-all text-slate-200">{value.replaceAll("_", " ")}</dd></div>;
}

const FILTER_LABELS: Record<string, string> = {
    all: "All", healthy: "Healthy", pending: "Pending", recovery_in_progress: "Recovering",
    attention_required: "Needs attention", outcome_uncertain: "Result unknown", unavailable: "Unavailable",
    terminal: "Finished", non_terminal: "In progress", "restart-service": "Restart service",
    proxmox: "Proxmox", qemu: "Virtual machine",
};

function Filter({ label, value, onChange, options }: { label: string; value: string; onChange: (value: string) => void; options: string[] }) {
    return <label className="text-sm text-slate-300">{label}<select aria-label={label} value={value} onChange={(event) => onChange(event.target.value)} className="mt-1 block w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-slate-100">{options.map((option) => <option key={option} value={option}>{FILTER_LABELS[option] ?? option.replaceAll("_", " ")}</option>)}</select></label>;
}
