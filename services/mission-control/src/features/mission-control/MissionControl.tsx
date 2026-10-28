import { useState, type ReactNode } from "react";
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

type AttentionItem = {
    key: string;
    label: string;
    reason: string;
    state: unknown;
    to: string;
    stale?: boolean;
    actionRequired?: boolean;
    workflowId?: string;
    workflowState?: string;
};

function isWorkflowAttention(item: AttentionItem): item is AttentionItem & { workflowId: string; workflowState: string } {
    return typeof item.workflowId === "string" && typeof item.workflowState === "string";
}

function SourceNote({ evidence, label, loading = false }: { evidence?: Evidence; label?: string; loading?: boolean }) {
    const prefix = label ? `${label}: ` : "";
    if (evidence?.stale) return <p role="status">{prefix}Refresh failed. Showing the last available information.</p>;
    if (evidence?.unavailable) return <p>{prefix}Current information could not be loaded.</p>;
    if (evidence?.data === undefined && !loading) return <p>{prefix}No current information is available.</p>;
    return null;
}
function sourceIsCurrent(evidence?: Evidence): boolean {
    return evidence?.data !== undefined && evidence.unavailable !== true && evidence.stale !== true;
}
function Card({ title, children, evidence, showSourceNote = true, loading = false }: { title: string; children: ReactNode; evidence?: Evidence; showSourceNote?: boolean; loading?: boolean }) {
    return <section aria-label={title} className="min-w-0 rounded-xl border border-mc-border-subtle bg-mc-surface p-4 [overflow-wrap:anywhere]">
        <h2 className="mb-3 text-lg font-semibold text-mc-text-primary">{title}</h2>
        <div className="space-y-3 text-sm text-mc-text-secondary">{showSourceNote && <SourceNote evidence={evidence} loading={loading} />}{children}</div>
    </section>;
}
function ObservedStatus({ value, reason, stale }: { value: unknown; reason?: unknown; stale?: boolean }) {
    return <HealthEvidence compact status={safeText(value)} stale={stale} reason={safeText(reason)} />;
}

function attentionPriority(value: unknown, actionRequired = false) {
    const reported = typeof value === "string" ? value.trim().toLowerCase() : "";
    const state = status(value);
    if (reported === "blocked" || state === "blocked") return 0;
    if (reported === "critical") return 1;
    if (actionRequired) return 2;
    if (state === "unavailable") return 3;
    return 4;
}

function workflowAttentionStage(state: string): string {
    switch (state) {
        case "awaiting_approval": return "Waiting for approval";
        case "awaiting_implementation_approval": return "Waiting for implementation approval";
        case "awaiting_verification_approval": return "Waiting for verification approval";
        case "awaiting_commit_approval": return "Waiting for commit approval";
        default: return formatWorkflowLabel(state);
    }
}

function workflowReasonRepeatsStage(reason: string, state: string): boolean {
    const normalizedReason = reason.trim().replace(/[.!?]+$/, "").toLowerCase();
    return normalizedReason === workflowAttentionStage(state).toLowerCase();
}

function workflowAttentionLabel(intent: unknown, state: string, stale: boolean): string {
    const safeIntent = safeText(intent);
    const action = safeIntent && safeIntent !== "[Sensitive text withheld]"
        ? formatWorkflowLabel(safeIntent)
        : "Workflow";
    return `${stale ? "Last known · " : ""}${action} · ${workflowAttentionStage(state)}`;
}

function attentionKey(finding: Record<string, unknown>, providers: Record<string, unknown>[], services: [string, unknown][]) {
    if (typeof finding.source === "string" && typeof finding.message === "string" && finding.message.length > 0) {
        const providerMatch = providers.some(p => p.id === finding.source && record(p.health).message === finding.message);
        const serviceMatch = services.some(([, raw]) => record(raw).provider_id === finding.source && record(raw).message === finding.message);
        if (providerMatch || serviceMatch) return conditionKey(finding.source, finding.message);
    }
    return conditionKey("finding", finding.id, finding.source, finding.title, finding.message);
}

function AttentionListItem({ item }: { item: AttentionItem }) {
    return <li>
        <Link to={item.to}>{item.label || "Inspect condition"}</Link>
        {item.actionRequired === true && <p>{item.stale ? "Last-known human action required; current requirement unknown." : "Human action required"}</p>}
        {isWorkflowAttention(item) ? <>
            {item.state === "blocked" && item.stale && <p className="text-red-300">Last-known workflow blocked; current state unknown.</p>}
            {item.reason && !workflowReasonRepeatsStage(item.reason, item.workflowState) && <p>{item.reason}</p>}
            <details><summary className="mc-focusable cursor-pointer text-sm text-mc-primary-strong">Technical details</summary>
                <p>Workflow ID: <span className="break-all font-mono">{item.workflowId}</span></p>
                <p className="text-xs text-mc-text-muted">Atlas did not provide a stage update time.</p>
            </details>
        </> : <ObservedStatus value={item.state} reason={item.reason} stale={item.stale} />}
        {item.stale && <p>Last-known condition; current state unknown.</p>}
    </li>;
}

export function Overview({ evidence, loading = false }: { evidence: OverviewEvidence; loading?: boolean }) {
    const [showAllAttention, setShowAllAttention] = useState(false);
    const [showAllServices, setShowAllServices] = useState(false);
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
    const serviceChecksKnown = health.services !== null && typeof health.services === "object" && !Array.isArray(health.services);
    const healthStatusesKnown = typeof health.atlas === "string" && status(health.atlas) !== "unknown"
        && serviceChecksKnown && services.every(([, service]) => status(record(service).status) !== "unknown");
    const providersKnown = Array.isArray(evidence.providers?.data)
        && providers.length === evidence.providers.data.length
        && providers.every(provider => typeof provider.id === "string" && status(record(provider.health).status) !== "unknown");
    const attentionSources = [evidence.summary, evidence.workflows, evidence.health, evidence.providers, evidence.ai];
    const attentionEvidenceComplete = attentionSources.every(sourceIsCurrent)
        && findingsKnown && workflowKnown && healthStatusesKnown && providersKnown
        && status(aiHealth.status) !== "unknown";
    const initialAttentionLoad = loading && !attentionSources.some(source =>
        source?.data !== undefined || source?.unavailable === true);
    // One row per authoritative source condition. Do not synthesize alerts from counts.
    const attention: AttentionItem[] = [
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
        ...validWorkflows.filter(w => w.workflow_state === "blocked" || workflowActionRequired(String(w.workflow_state))).map(w => ({
            actionRequired: workflowActionRequired(String(w.workflow_state)), workflowId: safeText(w.workflow_id), key: `workflow:${String(w.workflow_id)}`, label: workflowAttentionLabel(w.execution_intent, String(w.workflow_state), evidence.workflows?.stale === true), reason: safeText(w.last_result_summary), state: w.workflow_state === "blocked" ? "blocked" : "warning", to: detailPath("/workflows", w.workflow_id) ?? "/workflows", stale: evidence.workflows?.stale,
            workflowState: String(w.workflow_state),
        })),
    ];
    const deduplicated = new Map<string, typeof attention[number]>();
    for (const item of attention) {
        const previous = deduplicated.get(item.key);
        if (!previous || (previous.stale && !item.stale) || (Boolean(previous.stale) === Boolean(item.stale) && attentionPriority(item.state) < attentionPriority(previous.state))) deduplicated.set(item.key, item);
    }
    const uniqueAttention = [...deduplicated.values()]
        .sort((a, b) => attentionPriority(a.state, "actionRequired" in a && a.actionRequired === true)
            - attentionPriority(b.state, "actionRequired" in b && b.actionRequired === true));
    const displayedAttention = showAllAttention ? uniqueAttention : uniqueAttention.slice(0, 5);
    const displayedServices = showAllServices ? services : services.slice(0, 4);
    return <>
        <Card title="Operator Attention" showSourceNote={false}>
            {!initialAttentionLoad && <>
                <SourceNote evidence={evidence.summary} label="System findings" loading={loading} />
                <SourceNote evidence={evidence.workflows} label="Workflows" loading={loading} />
                <SourceNote evidence={evidence.health} label="System health" loading={loading} />
                <SourceNote evidence={evidence.providers} label="Providers" loading={loading} />
                <SourceNote evidence={evidence.ai} label="AI provider" loading={loading} />
                {evidence.workflows?.data !== undefined && !workflowKnown && <p>Workflow results are incomplete.</p>}
                {evidence.summary?.data !== undefined && !findingsKnown && <p>System findings are incomplete.</p>}
            </>}
            {uniqueAttention.length === 0 && loading && <p>Checking current information…</p>}
            {uniqueAttention.length === 0 && !loading && !attentionEvidenceComplete && <p>Some information is missing. Atlas cannot confirm whether attention is needed.</p>}
            {uniqueAttention.length === 0 && !loading && attentionEvidenceComplete && <p>The current reports show no items needing attention.</p>}
            <ul className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">{displayedAttention.map(item => <AttentionListItem key={item.key} item={item} />)}</ul>
            {uniqueAttention.length > 5 && <button
                type="button"
                className="mc-control mc-focusable rounded-lg border border-mc-border-subtle px-3 py-2 text-sm font-medium text-mc-primary-strong"
                aria-expanded={showAllAttention}
                onClick={() => setShowAllAttention(current => !current)}
            >{showAllAttention ? "Show fewer conditions" : `Show all ${uniqueAttention.length} attention items`}</button>}
        </Card>
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3" data-testid="overview-grid">
            <Card title="System health" showSourceNote={false}>
                <SystemHealthSummary evidence={evidence} loading={loading} />
                <Link to="/operations">Open operations →</Link>
            </Card>
            <Card title="Service checks" evidence={evidence.health} loading={loading}>
                {services.length === 0 && loading && evidence.health?.data === undefined && <p>Checking configured services…</p>}
                {services.length === 0 && evidence.health?.data !== undefined && <ObservedStatus value={null} reason={serviceChecksKnown ? "No configured service checks were reported." : "Service check details are unavailable."} stale={evidence.health.stale} />}
                {displayedServices.length > 0 && <ul className="space-y-3">{displayedServices.map(([name, raw]) => <li key={name}><p>{safeText(name)}</p><ObservedStatus value={record(raw).status} reason={record(raw).message} stale={evidence.health?.stale} /></li>)}</ul>}
                {services.length > 4 && <button
                    type="button"
                    className="mc-control mc-focusable rounded-lg border border-mc-border-subtle px-3 py-2 text-sm font-medium text-mc-primary-strong"
                    aria-expanded={showAllServices}
                    onClick={() => setShowAllServices(current => !current)}
                >{showAllServices ? "Show fewer service checks" : `Show all ${services.length} service checks`}</button>}
                <details><summary className="mc-focusable cursor-pointer text-sm text-mc-primary-strong">About service checks</summary>
                    <p>These checks show whether configured service endpoints responded. They do not measure Atlas Core’s own process health.</p>
                </details>
                <Link to="/operations">Inspect operations →</Link>
            </Card>
            <WorkerExecutionSection evidence={evidence.workflows} loading={loading} />
            <Card title="Agent details" showSourceNote={false}>
                <AgentOverviewContent evidence={evidence.agent} loading={loading} />
            </Card>
            <Card title="AI provider" evidence={evidence.ai} showSourceNote={evidence.ai?.data !== undefined} loading={loading}>
                <LocalAiContent evidence={evidence.ai} loading={loading} />
            </Card>
            <Card title="Providers" showSourceNote={false}>
                <ProviderOverviewContent evidence={evidence.providers} loading={loading} />
            </Card>
        </div>
        <Card title="Recent Activity" showSourceNote={false}>
            <RecentActivity evidence={evidence.activity} loading={loading} />
        </Card>
    </>;
}
export function MissionControl() {
    const { evidence, loading, refresh } = useOverviewEvidence();
    return <main aria-label="Mission Control" className="mx-auto max-w-7xl space-y-6 p-4 sm:p-6 [&_a]:text-mc-primary [&_a]:underline [&_a]:underline-offset-4 [&_a:focus-visible]:outline-2">
        <header className="flex flex-wrap items-start justify-between gap-3"><div><h1 className="text-2xl font-semibold">Mission Control</h1><p className="text-sm text-mc-text-secondary">Status, alerts, and recent work.</p></div><button className="rounded-lg border border-mc-border-subtle px-4 py-2" disabled={loading} onClick={() => void refresh()}>{loading ? "Refreshing…" : "Refresh"}</button></header>
        <Overview evidence={evidence} loading={loading} />
    </main>;
}
