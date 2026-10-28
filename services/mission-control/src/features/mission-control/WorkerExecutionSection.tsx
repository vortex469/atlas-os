import { Link } from "react-router-dom";
import type { WorkflowSummary } from "../../types/atlasAgent";
import { WORKFLOW_STATES } from "../../utils/workflowState";

import { isCompleteWorkflowEvidence } from "./workerExecutionEvidence";

import type { Evidence } from "./useOverviewEvidence";
import { detailPath, safeText } from "./overviewEvidence";
import { HealthEvidence } from "../../components/HealthEvidence";

function executionStage(workflow: WorkflowSummary): string | null {
    const stages = workflow.timeline.filter((stage) => stage.name === "Execution");
    return stages.length === 1 ? stages[0].status : null;
}

export function WorkerExecutionSection({ evidence, loading = false }: {
    evidence?: Evidence;
    loading?: boolean;
}) {
    const unavailable = evidence?.unavailable;
    const items = isCompleteWorkflowEvidence(evidence?.data) && (!unavailable || evidence?.stale)
        ? evidence.data.items : null;
    const knownStates = items?.every((item) =>
        (WORKFLOW_STATES as readonly string[]).includes(item.workflow_state));
    const active = items?.filter((item) => item.workflow_state === "executing") ?? [];
    const blocked = items?.filter((item) => item.workflow_state === "blocked") ?? [];
    const outcomes = items?.filter((item) => ["completed", "failed"].includes(executionStage(item) ?? "")) ?? [];
    const missingStages = items?.some((item) =>
        !["waiting", "current", "completed", "failed", "blocked"].includes(executionStage(item) ?? ""));
    const fallback = unavailable ? "Unavailable" : "Not confirmed";

    return (
        <section aria-labelledby="worker-execution-heading" className="min-w-0 rounded-xl border border-mc-border-subtle bg-mc-surface p-4 [overflow-wrap:anywhere]">
            <div className="flex flex-wrap items-center justify-between gap-3">
                <h2 id="worker-execution-heading" className="text-lg font-semibold text-mc-text-primary">Worker / Execution</h2>
                <Link to="/workflows" className="text-sm font-semibold text-mc-primary focus-visible:outline-2">Inspect executions →</Link>
            </div>
            <p className="mt-2 text-sm text-mc-text-muted">
                Recorded workflow progress. This view does not start work.
            </p>
            <HealthEvidence status={null} stale={evidence?.stale} reason="Worker availability and queue size are not reported." />
            {evidence?.stale && <p role="status" className="mt-2 text-sm text-amber-200">Refresh failed. Showing previously reported workflow details; current execution state is unknown.</p>}
            {loading && <p role="status" className="mt-2 text-sm text-mc-text-secondary">Refreshing workflow information. Displayed details may be out of date.</p>}
            <dl className="mt-4 grid gap-4 sm:grid-cols-2">
                <Metric label="Active workflows" value={items && knownStates ? `${active.length} executing workflow${active.length === 1 ? "" : "s"}` : fallback} />
                <Metric label="Blocked workflows" value={items && knownStates ? `${blocked.length} blocked workflow${blocked.length === 1 ? "" : "s"}` : fallback} />
            </dl>
            {items && !knownStates && <p className="mt-3 text-sm text-amber-200">A workflow state is not recognized, so activity totals are unavailable.</p>}
            <div className="mt-4 grid gap-4">
                {active.length > 0 && <EvidenceList title="Active execution evidence" items={active} available={!!items} empty="Unknown" />}
                {blocked.length > 0 && <EvidenceList title="Blocked workflow evidence" items={blocked} available={!!items} empty="Unknown" />}
            </div>
            <details className="mt-4 text-sm text-mc-text-secondary">
                <summary className="mc-focusable cursor-pointer text-mc-primary">Execution details</summary>
                <div className="mt-3 space-y-4">
                    {items && knownStates && active.length === 0 && <p className="text-mc-text-muted">No executing workflows are listed. This does not confirm that a worker is idle.</p>}
                    <dl className="grid gap-4 sm:grid-cols-2">
                        <Metric label="Worker availability" value="Not reported" />
                        <Metric label="Queued work" value="Queue total not reported" />
                    </dl>
                    <EvidenceList title="Past execution outcomes" items={outcomes} available={!!items} empty={missingStages ? "Outcome details could not be confirmed" : "No execution outcomes recorded"} outcomes />
                    <p className="text-xs text-mc-text-muted">Showing up to 3 workflows in each list. Times are not available, so outcomes are not sorted by time. A blocked workflow may not have started execution.</p>
                </div>
            </details>
            {missingStages && outcomes.length > 0 && <p className="mt-2 text-sm text-amber-200">Some workflow details are incomplete, so outcomes may be missing.</p>}
            {!items && <p role="status" className="mt-3 text-sm text-amber-200">{unavailable ? "Could not load workflow details." : "Workflow details are missing or incomplete."} Worker availability and queue size are not confirmed.</p>}
        </section>
    );
}

function Metric({ label, value }: { label: string; value: string }) {
    return <div><dt className="text-sm text-mc-text-muted">{label}</dt><dd className="mt-1 text-sm font-semibold text-mc-text-primary">{value}</dd></div>;
}

function EvidenceList({ title, items, available, empty, outcomes = false }: {
    title: string; items: WorkflowSummary[]; available: boolean; empty: string; outcomes?: boolean;
}) {
    return <div>
        <h3 className="text-sm font-semibold text-mc-text-primary">{title}</h3>
        {!available || items.length === 0 ? <p className="mt-2 text-sm text-mc-text-muted">{available ? empty : "Unknown"}</p> :
            <ul className="mt-2 space-y-2 text-sm">
                {[...items].sort((a, b) => a.workflow_id.localeCompare(b.workflow_id)).slice(0, 3).map((item) => <li key={item.workflow_id}>
                    <Link to={detailPath("/workflows", item.workflow_id)!} className="break-all text-mc-primary focus-visible:outline-2">{safeText(item.workflow_id)}</Link>
                    <span className="ml-2 text-mc-text-secondary">{outcomes ? `Execution ${executionStage(item)}` : item.workflow_state}</span>
                </li>)}
            </ul>}
    </div>;
}
