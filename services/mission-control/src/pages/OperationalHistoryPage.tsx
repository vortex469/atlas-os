import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";

import {
    getWorkflowOperationalLifecycle,
    getWorkflowRecoveryDiagnostic,
    listWorkflows,
} from "../api/atlas-agent";
import { OperationalRecoverySummary } from "../components/OperationalRecoverySummary";
import { recoveryPresentation } from "../utils/recoveryDiagnostic";
import type {
    WorkflowOperationalLifecycle,
    WorkflowRecoveryDiagnostic,
    WorkflowSummary,
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
    const parsed = new Date(value);
    return Number.isNaN(parsed.getTime()) ? "Unknown time" : parsed.toLocaleString();
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

    const load = useCallback(async () => {
        setIsLoading(true);
        setError(null);
        try {
            const page = await listWorkflows({
                effect_kind: "operational_action",
                limit: PAGE_SIZE,
                offset,
            });
            const evidence = await Promise.all(
                page.items.map(async (workflow) => {
                    const [lifecycle, diagnostic] = await Promise.all([
                        getWorkflowOperationalLifecycle(workflow.workflow_id).catch(() => null),
                        getWorkflowRecoveryDiagnostic(workflow.workflow_id)
                            .then((value) => ({ value, unavailable: false }))
                            .catch(() => ({ value: null, unavailable: true })),
                    ]);
                    return { lifecycle, diagnostic: diagnostic.value, diagnosticUnavailable: diagnostic.unavailable };
                }),
            );
            setItems(page.items.map((workflow, index) => ({ workflow, ...evidence[index] })));
            setTotal(page.total);
        } catch {
            setError("Mission Control could not load operational workflow history.");
        } finally {
            setIsLoading(false);
        }
    }, [offset]);

    useEffect(() => {
        void Promise.resolve().then(load);
    }, [load]);

    const visibleItems = items.filter(({ workflow, lifecycle, diagnostic }) =>
        (diagnosticFilter === "all" || diagnostic?.diagnostic_status === diagnosticFilter)
        && (terminalFilter === "all" || (terminalFilter === "terminal") === lifecycle?.terminal)
        && (intentFilter === "all" || workflow.execution_intent === intentFilter)
        && (providerFilter === "all" || lifecycle?.provider_id === providerFilter)
        && (resourceTypeFilter === "all" || lifecycle?.resource_type === resourceTypeFilter));

    return (
        <main className="mx-auto max-w-7xl space-y-6 p-8">
            <header className="flex flex-wrap items-start justify-between gap-4 border-b border-slate-800 pb-6">
                <div><p className="text-xs font-semibold uppercase tracking-[0.2em] text-cyan-400">Operations</p><h1 className="mt-2 text-3xl font-semibold text-white">Operational workflow history</h1><p className="mt-2 max-w-3xl text-sm text-slate-400">Bounded, read-only lifecycle history from persisted Agent workflows and sanitized Core evidence. Maintenance requests remain a separate workflow.</p></div>
                <div className="flex gap-3"><Link to="/operations/request" className="rounded-lg border border-cyan-400/60 px-3 py-2 text-sm font-semibold text-cyan-100">Request maintenance</Link><button type="button" onClick={() => void load()} disabled={isLoading} className="rounded-lg border border-slate-700 px-3 py-2 text-sm font-semibold text-slate-100 disabled:opacity-50">Refresh history</button></div>
            </header>
            {isLoading && <p role="status" className="text-slate-300">Loading operational history...</p>}
            {error && <p role="alert" className="rounded-lg border border-red-500/30 bg-red-500/10 p-4 text-red-100">{error} A network failure is not an operational failure.</p>}
            {!isLoading && !error && items.length === 0 && <p className="rounded-xl border border-slate-800 bg-slate-900/70 p-5 text-slate-300">No operational workflows are persisted.</p>}
            {!isLoading && !error && items.length > 0 && <section aria-label="Operational history filters" className="grid gap-3 rounded-xl border border-slate-800 bg-slate-900/70 p-4 sm:grid-cols-2 xl:grid-cols-5"><Filter label="Diagnostic" value={diagnosticFilter} onChange={setDiagnosticFilter} options={["all", "healthy", "pending", "recovery_in_progress", "attention_required", "outcome_uncertain", "unavailable"]} /><Filter label="Lifecycle" value={terminalFilter} onChange={setTerminalFilter} options={["all", "terminal", "non_terminal"]} /><Filter label="Intent" value={intentFilter} onChange={setIntentFilter} options={["all", "restart-service"]} /><Filter label="Provider" value={providerFilter} onChange={setProviderFilter} options={["all", "proxmox"]} /><Filter label="Resource type" value={resourceTypeFilter} onChange={setResourceTypeFilter} options={["all", "qemu"]} /></section>}
            {!isLoading && !error && items.length > 0 && visibleItems.length === 0 && <p className="rounded-xl border border-slate-800 bg-slate-900/70 p-5 text-slate-300">No workflows on this bounded page match the selected filters.</p>}
            {!isLoading && !error && <section aria-label="Operational workflow history" className="space-y-4">{visibleItems.map((item) => <OperationalHistoryCard key={item.workflow.workflow_id} {...item} />)}</section>}
            {!isLoading && !error && total > PAGE_SIZE && <nav aria-label="Operational history pagination" className="flex items-center gap-3"><button type="button" onClick={() => setOffset((current) => Math.max(0, current - PAGE_SIZE))} disabled={offset === 0} className="rounded-lg border border-slate-700 px-3 py-2 text-sm text-slate-100 disabled:opacity-50">Previous</button><span className="text-sm text-slate-400">Showing {offset + 1}–{Math.min(offset + PAGE_SIZE, total)} of {total}</span><button type="button" onClick={() => setOffset((current) => current + PAGE_SIZE)} disabled={offset + PAGE_SIZE >= total} className="rounded-lg border border-slate-700 px-3 py-2 text-sm text-slate-100 disabled:opacity-50">Next</button></nav>}
        </main>
    );
}

function OperationalHistoryCard({ workflow, lifecycle, diagnostic, diagnosticUnavailable }: HistoryItem) {
    const outcome = diagnostic ? recoveryPresentation(diagnostic) : null;
    const terminalTimestamp = lifecycle?.verification_completed_at ?? lifecycle?.dispatch_completed_at ?? null;
    return <article className="space-y-4 rounded-xl border border-slate-800 bg-slate-900/70 p-5"><div className="flex flex-wrap items-start justify-between gap-4"><div><h2 className="break-all text-lg font-semibold text-white">{lifecycle?.target_label ?? workflow.target_id ?? "Operational target"}</h2><p className="mt-1 text-sm text-slate-400">{workflow.execution_intent ?? "Operational action"} · {outcome?.title ?? "Diagnostic unavailable"}</p></div><Link to={`/workflows/${encodeURIComponent(workflow.workflow_id)}`} className="rounded-lg border border-blue-400/60 px-3 py-2 text-sm font-semibold text-blue-100">Open lifecycle</Link></div><dl className="grid gap-3 text-sm md:grid-cols-2 xl:grid-cols-4"><HistoryDetail label="Workflow State" value={workflow.workflow_state} /><HistoryDetail label="Consistency" value={diagnostic?.consistency ?? "unavailable"} /><HistoryDetail label="Verification" value={lifecycle?.verification_status ?? "Not reported"} /><HistoryDetail label="Support Evidence" value={diagnostic ? "Available" : "Unavailable"} /><HistoryDetail label="Created" value={formatTimestamp(lifecycle?.request_created_at ?? null)} /><HistoryDetail label="Terminal" value={formatTimestamp(terminalTimestamp)} /></dl><OperationalRecoverySummary diagnostic={diagnostic} error={diagnosticUnavailable ? "Mission Control could not read this workflow diagnostic." : null} supportEvidenceAvailable={diagnostic !== null} compact /></article>;
}

function HistoryDetail({ label, value }: { label: string; value: string }) {
    return <div><dt className="text-xs uppercase tracking-wide text-slate-500">{label}</dt><dd className="mt-1 break-all text-slate-200">{value.replaceAll("_", " ")}</dd></div>;
}

function Filter({ label, value, onChange, options }: { label: string; value: string; onChange: (value: string) => void; options: string[] }) {
    return <label className="text-sm text-slate-300">{label}<select aria-label={label} value={value} onChange={(event) => onChange(event.target.value)} className="mt-1 block w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-slate-100">{options.map((option) => <option key={option} value={option}>{option.replaceAll("_", " ")}</option>)}</select></label>;
}
