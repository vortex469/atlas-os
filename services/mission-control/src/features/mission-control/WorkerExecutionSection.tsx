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
    const fallback = unavailable ? "Unavailable" : "Unknown";

    return (
        <section aria-labelledby="worker-execution-heading" className="min-w-0 rounded-xl border border-mc-border-subtle bg-mc-surface p-4 [overflow-wrap:anywhere]">
            <div className="flex flex-wrap items-center justify-between gap-3">
                <h2 id="worker-execution-heading" className="text-lg font-semibold text-mc-text-primary">Worker / Execution</h2>
                <Link to="/workflows" className="text-sm font-semibold text-mc-primary focus-visible:outline-2">Inspect executions →</Link>
            </div>
            <p className="mt-2 text-sm text-mc-text-muted">
                Read-only observation from persisted Atlas Agent workflows, not execution authority.
                Admission, reservation and controlled dequeue remain in their existing boundaries.
            </p>
            <HealthEvidence status={null} stale={evidence?.stale} reason="Worker availability and queue depth are not exposed by this evidence." />
            {evidence?.stale && <p role="status" className="mt-2 text-sm text-amber-200">Stale evidence — last-known workflow observations; current execution state unknown.</p>}
            {loading && <p role="status" className="mt-2 text-sm text-mc-text-secondary">Refreshing execution evidence; displayed observations may be stale.</p>}
            <dl className="mt-4 grid gap-4 sm:grid-cols-2">
                <Metric label="Worker availability / state" value="Unknown — worker heartbeat not exposed" />
                <Metric label="Active execution" value={items && knownStates ? `${active.length} executing workflows` : fallback} />
                <Metric label="Queued / admitted work" value="Unknown — aggregate queue and admission evidence not exposed" />
                <Metric label="Blocked execution / workflow" value={items && knownStates ? `${blocked.length} blocked workflows` : fallback} />
            </dl>
            {items && knownStates && active.length === 0 && <p className="mt-3 text-sm text-mc-text-muted">No executing workflows observed. Worker idleness is unknown.</p>}
            {items && !knownStates && <p className="mt-3 text-sm text-amber-200">Unrecognized workflow state; activity totals are unknown.</p>}
            <div className="mt-4 grid gap-4">
                <EvidenceList title="Active execution evidence" items={active} available={!!items} empty={knownStates ? "None observed" : "Unknown"} />
                <EvidenceList title="Blocked workflow evidence" items={blocked} available={!!items} empty={knownStates ? "None observed" : "Unknown"} />
                <EvidenceList title="Recorded execution outcomes" items={outcomes} available={!!items} empty={missingStages ? "Unknown — execution evidence missing or malformed" : "No execution outcomes recorded"} outcomes />
            </div>
            <p className="mt-3 text-xs text-mc-text-muted">Up to 3 records per group. Execution timestamps are not exposed: outcome recency is unavailable; records are shown in workflow ID order. Workflow blockers may precede execution.</p>
            {missingStages && outcomes.length > 0 && <p className="mt-2 text-sm text-amber-200">Some execution evidence is missing or malformed; outcomes are incomplete.</p>}
            {!items && <p role="status" className="mt-3 text-sm text-amber-200">Execution evidence {unavailable ? "unavailable" : "unknown or incomplete"}. No idle or healthy state inferred.</p>}
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
