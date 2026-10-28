import { useState } from "react";
import { Link } from "react-router-dom";
import type { WorkflowSummary } from "../../types/atlasAgent";
import { formatWorkflowLabel, WORKFLOW_STATES } from "../../utils/workflowState";

import { isCompleteWorkflowEvidence } from "./workerExecutionEvidence";

import type { Evidence } from "./useOverviewEvidence";
import { detailPath, safeText } from "./overviewEvidence";

function executionStage(workflow: WorkflowSummary): string | null {
    const stages = workflow.timeline.filter((stage) => stage.name === "Execution");
    return stages.length === 1 ? stages[0].status : null;
}

function workflowActionLabel(intent: string | null): string {
    const safeIntent = safeText(intent);
    return safeIntent && safeIntent !== "[Sensitive text withheld]"
        ? formatWorkflowLabel(safeIntent)
        : "Workflow";
}

function workflowStatusLabel(workflow: WorkflowSummary, outcomes: boolean): string {
    if (outcomes) {
        return executionStage(workflow) === "completed"
            ? "Execution completed"
            : "Execution failed";
    }
    return workflow.workflow_state === "executing"
        ? "Running"
        : workflow.workflow_state === "blocked"
            ? "Blocked"
            : formatWorkflowLabel(workflow.workflow_state);
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
    return (
        <section aria-labelledby="work-activity-heading" className="min-w-0 rounded-xl border border-mc-border-subtle bg-mc-surface p-4 [overflow-wrap:anywhere]">
            <div className="flex flex-wrap items-center justify-between gap-3">
                <h2 id="work-activity-heading" className="text-lg font-semibold text-mc-text-primary">Work activity</h2>
                <Link to="/workflows" className="text-sm font-semibold text-mc-primary focus-visible:outline-2">Review workflows →</Link>
            </div>
            <p className="mt-2 text-sm text-mc-text-muted">
                Counts and results come from recorded workflows. This page does not start work.
            </p>
            <p className="mt-2 text-sm text-mc-text-secondary">Atlas does not report whether a worker is available.</p>
            {evidence?.stale && <p role="status" className="mt-2 text-sm text-amber-200">Showing last-known workflow information. Current status is unknown.</p>}
            {loading && <p role="status" className="mt-2 text-sm text-mc-text-secondary">Refreshing workflow information; displayed results may be stale.</p>}
            {items && knownStates && (
                <dl className="mt-4 grid gap-4 sm:grid-cols-2">
                    <Metric label="Running workflows" value={String(active.length)} />
                    <Metric label="Blocked workflows" value={String(blocked.length)} />
                </dl>
            )}
            {loading && !items && <p role="status" className="mt-3 text-sm text-mc-text-secondary">Checking workflow status…</p>}
            {items && !knownStates && <p role="status" className="mt-3 text-sm text-amber-200">Some workflow statuses are not recognized, so counts are unavailable.</p>}
            {items && knownStates && active.length === 0 && <p className="mt-3 text-sm text-mc-text-muted">No running workflows are listed.</p>}
            <div className="mt-4 grid gap-4">
                {active.length > 0 && <EvidenceList key="running" title="Running workflows" items={active} available={!!items} empty="Unknown" />}
                {blocked.length > 0 && <EvidenceList key="blocked" title="Blocked workflows" items={blocked} available={!!items} empty="Unknown" />}
            </div>
            <details className="mt-4 text-sm text-mc-text-secondary">
                <summary className="mc-focusable cursor-pointer text-mc-primary">More about execution data</summary>
                <div className="mt-3 space-y-4">
                    <dl className="grid gap-4 sm:grid-cols-2">
                        <Metric label="Queue size" value="Not reported" />
                    </dl>
                    <EvidenceList key="outcomes" title="Recorded execution outcomes" items={outcomes} available={!!items} empty={missingStages ? "Unknown — execution evidence missing or malformed" : "No execution outcomes recorded"} outcomes />
                    <p className="text-xs text-mc-text-muted">Execution times are not available, so outcomes cannot be sorted by recency. A workflow may be blocked before it starts running.</p>
                </div>
            </details>
            {missingStages && outcomes.length > 0 && <p className="mt-2 text-sm text-amber-200">Some execution results are missing or incomplete.</p>}
            {!items && !loading && <p role="status" className="mt-3 text-sm text-amber-200">{unavailable ? "Workflow status could not be loaded." : "Workflow status is unknown or incomplete."}</p>}
        </section>
    );
}

function Metric({ label, value }: { label: string; value: string }) {
    return <div><dt className="text-sm text-mc-text-muted">{label}</dt><dd className="mt-1 text-sm font-semibold text-mc-text-primary">{value}</dd></div>;
}

function EvidenceList({ title, items, available, empty, outcomes = false }: {
    title: string; items: WorkflowSummary[]; available: boolean; empty: string; outcomes?: boolean;
}) {
    const [showAll, setShowAll] = useState(false);
    const ordered = [...items].sort((a, b) => a.workflow_id.localeCompare(b.workflow_id));
    const displayed = showAll ? ordered : ordered.slice(0, 3);
    return <div>
        <h3 className="text-sm font-semibold text-mc-text-primary">{title}</h3>
        {!available || items.length === 0 ? <p className="mt-2 text-sm text-mc-text-muted">{available ? empty : "Unknown"}</p> :
            <ul aria-label={title} className="mt-2 space-y-2 text-sm">
                {displayed.map((item) => <li key={item.workflow_id}>
                    <Link to={detailPath("/workflows", item.workflow_id)!} className="text-mc-primary focus-visible:outline-2">{workflowActionLabel(item.execution_intent)} · {workflowStatusLabel(item, outcomes)}</Link>
                    <details className="mt-1 text-xs text-mc-text-muted">
                        <summary className="mc-focusable cursor-pointer text-mc-primary-strong">Technical details</summary>
                        <p className="mt-1 break-all font-mono">Workflow ID: {safeText(item.workflow_id)}</p>
                    </details>
                </li>)}
            </ul>}
        {available && items.length > 3 && <button
            type="button"
            className="mc-control mc-focusable mt-2 rounded-lg border border-mc-border-subtle px-3 py-2 text-sm font-medium text-mc-primary-strong"
            aria-expanded={showAll}
            onClick={() => setShowAll(current => !current)}
        >{showAll ? `Show fewer ${title.toLowerCase()}` : `Show all ${items.length} ${title.toLowerCase()}`}</button>}
    </div>;
}
