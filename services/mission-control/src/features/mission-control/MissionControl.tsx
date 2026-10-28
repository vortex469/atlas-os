import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import { HealthEvidence } from "../../components/HealthEvidence";
import { SystemHealthSummary } from "./SystemHealthSummary";
import { formatWorkflowLabel, WORKFLOW_STATES, workflowActionRequired } from "../../utils/workflowState";
import { conditionKey, detailPath, record, rows, safeText, status } from "./overviewEvidence";
import { useOverviewEvidence } from "./useOverviewEvidence";
import type { Evidence, OverviewEvidence } from "./useOverviewEvidence";

import { AgentOverviewContent, ProviderOverviewContent } from "./AgentProviderContent";
import { LocalAiContent } from "./LocalAiContent";
import { providerDetailPath } from "./agentProviderEvidence";
import { RecentActivity } from "./RecentActivity";
import { WorkerExecutionSection } from "./WorkerExecutionSection";
import { isCompleteWorkflowEvidence } from "./workerExecutionEvidence";

interface AttentionItem {
    actionRequired?: boolean;
    workflowState?: string;
    workflowId?: string;
    checkedAt?: unknown;
    key: string;
    label: string;
    reason: string;
    state: unknown;
    to: string;
    stale?: boolean;
}

function SourceNote({ evidence, label }: { evidence?: Evidence; label?: string }) {
    const prefix = label ? `${label}: ` : "";
    if (evidence?.stale) return <p role="status">{prefix}Refresh failed. Showing previously reported information only; current status is unknown.</p>;
    if (evidence?.unavailable) return <p>{prefix}Could not load this information.</p>;
    if (evidence?.data === undefined) return <p>{prefix}Information has not been received yet.</p>;
    return null;
}
function Card({ title, children, evidence }: { title: string; children: ReactNode; evidence?: Evidence }) {
    return <section aria-label={title} className="min-w-0 rounded-xl border border-mc-border-subtle bg-mc-surface p-4 [overflow-wrap:anywhere]">
        <h2 className="mb-3 text-lg font-semibold text-mc-text-primary">{title}</h2>
        <div className="space-y-3 text-sm text-mc-text-secondary"><SourceNote evidence={evidence} />{children}</div>
    </section>;
}
function ObservedStatus({ value, reason, stale, checkedAt }: { value: unknown; reason?: unknown; stale?: boolean; checkedAt?: unknown }) {
    return <HealthEvidence status={safeText(value)} stale={stale} reason={safeText(reason)} checkedAt={checkedAt} />;
}

function attentionPriority(value: unknown) {
    const state = status(value);
    return state === "blocked" ? 0 : state === "unavailable" ? 1 : 2;
}

function attentionKey(finding: Record<string, unknown>, providers: Record<string, unknown>[], services: [string, unknown][]) {
    if (typeof finding.source === "string" && typeof finding.message === "string" && finding.message.length > 0) {
        const providerMatch = providers.some(p => p.id === finding.source && record(p.health).message === finding.message);
        const serviceMatch = services.some(([, raw]) => record(raw).provider_id === finding.source && record(raw).message === finding.message);
        if (providerMatch || serviceMatch) return conditionKey(finding.source, finding.message);
    }
    return conditionKey("finding", finding.id, finding.source, finding.title, finding.message);
}

export function Overview({ evidence, loading = false }: { evidence: OverviewEvidence; loading?: boolean }) {
    const health = record(evidence.health?.data);
    const services = Object.entries(record(health.services)).sort((a, b) =>
        Number(status(record(a[1]).status) === "healthy") - Number(status(record(b[1]).status) === "healthy"));
    const providers = rows(evidence.providers?.data).sort((a, b) =>
        Number(status(record(a.health).status) === "healthy") - Number(status(record(b.health).status) === "healthy"));
    const workflows = rows(record(evidence.workflows?.data).items);
    const validWorkflows = workflows.filter(w => typeof w.workflow_id === "string" && w.workflow_id.trim().length > 0 && detailPath("/workflows", w.workflow_id) && WORKFLOW_STATES.some(state => state === w.workflow_state));
    const workflowKnown = isCompleteWorkflowEvidence(evidence.workflows?.data) && workflows.length === validWorkflows.length;
    const ai = record(evidence.ai?.data);
    const findings = rows(record(evidence.summary?.data).findings);
    const findingsKnown = Array.isArray(record(evidence.summary?.data).findings) && findings.every(f =>
        typeof f.severity === "string" && ["info", "warning", "critical", "blocked"].includes(f.severity));
    const aiProvider = record(ai.provider);
    const aiHealth = record(ai.health);
    const assessment = record(evidence.summary?.data);
    const policy = record(evidence.policyHealth?.data);
    const healthConditions = [
        { key: "atlas-health", label: "Atlas health", state: health.atlas, evidence: evidence.health, reason: undefined, checkedAt: undefined },
        { key: "system-assessment", label: "System assessment", state: assessment.status, evidence: evidence.summary, reason: assessment.summary, checkedAt: undefined },
        { key: "policy-status", label: "Policy status", state: policy.status, evidence: evidence.policyHealth, reason: policy.error, checkedAt: policy.checked_at },
    ];
    // One row per authoritative source condition. Do not synthesize alerts from counts.
    const attention: AttentionItem[] = [
        ...healthConditions.filter(source => ["degraded", "unavailable", "blocked"].includes(status(source.state))).map(source => ({
            key: source.key, label: source.label, reason: safeText(source.reason), state: source.state,
            to: `#${source.key}`, stale: source.evidence?.stale, checkedAt: source.checkedAt,
        })),
        ...services.filter(([, raw]) => ["degraded", "unavailable", "blocked"].includes(status(record(raw).status))).map(([name, raw]) => ({
            key: conditionKey(record(raw).provider_id || name, record(raw).message), label: safeText(name), reason: safeText(record(raw).message), state: record(raw).status, to: providerDetailPath(record(raw).provider_id) ?? "/operations", stale: evidence.health?.stale,
        })),
        ...providers.filter(p => ["degraded", "unavailable", "blocked"].includes(status(record(p.health).status))).map(p => ({
            key: conditionKey(p.id, record(p.health).message), label: safeText(p.name), reason: safeText(record(p.health).message), state: record(p.health).status, to: providerDetailPath(p.id) ?? "/operations", stale: evidence.providers?.stale,
        })),
        ...(["degraded", "unavailable", "blocked"].includes(status(aiHealth.status)) ? [{
            key: detailPath("/providers", aiProvider.id) ? conditionKey(aiProvider.id, aiHealth.message) : conditionKey("ai/status", null, aiHealth.message), label: safeText(aiProvider.name) || "Configured AI provider", reason: safeText(aiHealth.message), state: aiHealth.status, to: providerDetailPath(aiProvider.id) ?? "/operations", stale: evidence.ai?.stale,
        }] : []),
        ...findings.filter(f => typeof f.severity === "string" && ["warning", "critical", "blocked"].includes(f.severity)).map(f => ({
            key: attentionKey(f, [...providers, { ...aiProvider, health: aiHealth }], services), label: safeText(f.title), reason: safeText(f.message), state: f.severity, to: "/operations", stale: evidence.summary?.stale,
        })),
        ...validWorkflows.filter(w => w.workflow_state === "blocked" || workflowActionRequired(String(w.workflow_state))).map(w => {
            const intent = safeText(w.execution_intent);
            return {
                actionRequired: workflowActionRequired(String(w.workflow_state)),
                workflowState: String(w.workflow_state),
                workflowId: safeText(w.workflow_id),
                key: `workflow:${String(w.workflow_id)}`,
                label: intent ? formatWorkflowLabel(intent) : "Workflow needs attention",
                reason: safeText(w.last_result_summary),
                state: w.workflow_state === "blocked" ? "blocked" : "warning",
                to: detailPath("/workflows", w.workflow_id) ?? "/workflows",
                stale: evidence.workflows?.stale,
            };
        }),
    ];
    const deduplicated = new Map<string, AttentionItem>();
    for (const item of attention) {
        const previous = deduplicated.get(item.key);
        if (!previous || (previous.stale && !item.stale) || (Boolean(previous.stale) === Boolean(item.stale) && attentionPriority(item.state) < attentionPriority(previous.state))) deduplicated.set(item.key, item);
    }
    const uniqueAttention = [...deduplicated.values()]
        .sort((a, b) => attentionPriority(a.state) - attentionPriority(b.state));
    const renderService = ([name, raw]: [string, unknown]) => <div key={name}><p>{safeText(name)}</p><ObservedStatus value={record(raw).status} reason={record(raw).message} stale={evidence.health?.stale} /></div>;
    const renderAttentionItem = (item: AttentionItem) => (
        <li key={item.key}>
                {item.to.startsWith("#") ? <a href={item.to}>{item.label}</a> : <Link to={item.to}>{item.label || "Inspect condition"}</Link>}
                {"actionRequired" in item && item.actionRequired === true && <p>{item.stale ? "Last-known human action required; current requirement unknown." : "Human action required"}</p>}
                {"workflowState" in item ? <>
                    {item.state === "blocked" && <p className="text-red-300">{item.stale ? "Last-known workflow blocked; current state unknown." : "Workflow blocked"}</p>}
                    {item.reason && <p>{item.reason}</p>}
                    <details><summary className="mc-focusable cursor-pointer text-sm text-mc-primary-strong">Workflow details</summary>
                        <p>Workflow ID: {item.workflowId ?? "Unavailable"}</p>
                        <p>{item.stale ? "Last-known workflow stage" : "Workflow stage"}: {formatWorkflowLabel(safeText(item.workflowState))}</p>
                        <p className="text-xs text-mc-text-muted">Stage update time is not supplied.</p>
                    </details>
                </> : <ObservedStatus value={item.state} reason={item.reason} stale={item.stale} checkedAt={"checkedAt" in item ? item.checkedAt : undefined} />}
                {item.stale && <p>Last-known condition; current state unknown.</p>}
        </li>
    );
    return <>
        <Card title="Operator Attention" evidence={evidence.summary}>
            <p>Review the conditions below and open a workflow when it needs your decision.</p>
            <SourceNote evidence={evidence.workflows} label="Workflows" /><SourceNote evidence={evidence.health} label="System health" /><SourceNote evidence={evidence.providers} label="Providers" /><SourceNote evidence={evidence.ai} label="AI provider" /><SourceNote evidence={evidence.policyHealth} label="Policy status" />
            {!workflowKnown && <p>Workflow status could not be confirmed.</p>}
            {!findingsKnown && <p>Operational findings could not be confirmed.</p>}
            {uniqueAttention.length === 0 && <p>No attention items appear in the information received. Atlas cannot confirm an all-clear while information is missing.</p>}
            <ul className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">{uniqueAttention.slice(0, 5).map(renderAttentionItem)}</ul>
            {uniqueAttention.length > 5 && <details className="rounded-lg border border-mc-border-subtle p-3">
                <summary className="mc-focusable cursor-pointer text-sm text-mc-primary-strong">More conditions ({uniqueAttention.length - 5})</summary>
                <ul className="mt-3 grid gap-3 sm:grid-cols-2 xl:grid-cols-3">{uniqueAttention.slice(5).map(renderAttentionItem)}</ul>
            </details>}
            <div className="flex flex-wrap gap-x-4 gap-y-2">
                <Link to="/operations">Review operational conditions →</Link>
                <Link to="/workflows">Review workflow attention →</Link>
            </div>
        </Card>
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3" data-testid="overview-grid">
            <Card title="System status" evidence={evidence.health}>
                <SystemHealthSummary evidence={evidence} />
                <Link to="/operations">Open operations →</Link>
            </Card>
            <Card title="Service health" evidence={evidence.health}>
                {services.length === 0 && <ObservedStatus value={null} reason="No subsystem evidence reported." />}
                <p>Service statuses reported by Atlas Core.</p>
                {services.slice(0, 4).map(renderService)}
                {services.length > 4 && <details className="rounded-lg border border-mc-border-subtle p-3">
                    <summary className="mc-focusable cursor-pointer text-sm text-mc-primary-strong">More services ({services.length - 4})</summary>
                    <div className="mt-3 space-y-3">{services.slice(4).map(renderService)}</div>
                </details>}
                <p>Core process health is not separately reported.</p>
                <Link to="/operations">Inspect operations →</Link>
            </Card>
            <WorkerExecutionSection evidence={evidence.workflows} loading={loading} />
            <Card title="Agent state" evidence={evidence.agent}>
                <AgentOverviewContent evidence={evidence.agent} />
            </Card>
            <Card title="AI provider" evidence={evidence.ai}>
                <LocalAiContent evidence={evidence.ai} />
            </Card>
            <Card title="Providers" evidence={evidence.providers}>
                <ProviderOverviewContent evidence={evidence.providers} />
            </Card>
        </div>
        <Card title="Recent Activity" evidence={evidence.activity}>
            <RecentActivity evidence={evidence.activity} />
        </Card>
    </>;
}
export function MissionControl() {
    const { evidence, loading, refresh } = useOverviewEvidence();
    return <main aria-label="Mission Control overview" className="mx-auto max-w-7xl space-y-6 p-4 sm:p-6 [&_a]:text-mc-primary [&_a]:underline [&_a]:underline-offset-4 [&_a:focus-visible]:outline-2">
        <header className="flex flex-wrap items-start justify-between gap-3"><div><h1 className="text-2xl font-semibold">Overview</h1><p className="text-sm text-mc-text-secondary">Status, alerts and recent work.</p></div><button className="rounded-lg border border-mc-border-subtle px-4 py-2" disabled={loading} onClick={() => void refresh()}>{loading ? "Refreshing…" : "Refresh"}</button></header>
        <Overview evidence={evidence} loading={loading} />
    </main>;
}
