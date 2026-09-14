import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import { HealthEvidence } from "../../components/HealthEvidence";
import { SystemHealthSummary } from "./SystemHealthSummary";
import { WORKFLOW_STATES, workflowActionRequired } from "../../utils/workflowState";
import { conditionKey, detailPath, record, rows, safeText, status } from "./overviewEvidence";
import { useOverviewEvidence } from "./useOverviewEvidence";
import type { Evidence, OverviewEvidence } from "./useOverviewEvidence";

import { AgentOverviewContent, ProviderOverviewContent } from "./AgentProviderContent";
import { LocalAiContent } from "./LocalAiContent";
import { providerDetailPath } from "./agentProviderEvidence";
import { RecentActivity } from "./RecentActivity";
import { WorkerExecutionSection } from "./WorkerExecutionSection";
import { isCompleteWorkflowEvidence } from "./workerExecutionEvidence";

function SourceNote({ evidence }: { evidence?: Evidence }) {
    if (evidence?.stale) return <p role="status">Stale evidence — refresh failed. Last-known observations only.</p>;
    if (evidence?.unavailable) return <p>Evidence unavailable.</p>;
    if (evidence?.data === undefined) return <p>Evidence unknown.</p>;
    return null;
}
function Card({ title, children, evidence }: { title: string; children: ReactNode; evidence?: Evidence }) {
    return <section aria-label={title} className="min-w-0 rounded-xl border border-mc-border-subtle bg-mc-surface p-4 [overflow-wrap:anywhere]">
        <h2 className="mb-3 text-lg font-semibold text-mc-text-primary">{title}</h2>
        <div className="space-y-3 text-sm text-mc-text-secondary"><SourceNote evidence={evidence} />{children}</div>
    </section>;
}
function ObservedStatus({ value, reason, stale }: { value: unknown; reason?: unknown; stale?: boolean }) {
    return <HealthEvidence status={safeText(value)} stale={stale} reason={safeText(reason)} />;
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
    // One row per authoritative source condition. Do not synthesize alerts from counts.
    const attention = [
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
            actionRequired: workflowActionRequired(String(w.workflow_state)), key: `workflow:${String(w.workflow_id)}`, label: safeText(w.workflow_id), reason: `${safeText(w.workflow_state)} · ${safeText(w.last_result_summary)}`, state: w.workflow_state === "blocked" ? "blocked" : "warning", to: detailPath("/workflows", w.workflow_id) ?? "/workflows", stale: evidence.workflows?.stale,
        })),
    ];
    const deduplicated = new Map<string, typeof attention[number]>();
    for (const item of attention) {
        const previous = deduplicated.get(item.key);
        if (!previous || (previous.stale && !item.stale) || (Boolean(previous.stale) === Boolean(item.stale) && attentionPriority(item.state) < attentionPriority(previous.state))) deduplicated.set(item.key, item);
    }
    const uniqueAttention = [...deduplicated.values()]
        .sort((a, b) => attentionPriority(a.state) - attentionPriority(b.state));
    return <>
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3" data-testid="overview-grid">
            <Card title="Atlas overall state" evidence={evidence.health}>
                <SystemHealthSummary evidence={evidence} />
                <p>Atlas-reported state from Core health.</p>
                <p>Core aggregate update time is not supplied.</p>
                <Link to="/operations">Open operations →</Link>
            </Card>
            <Card title="Core health" evidence={evidence.health}>
                {services.length === 0 && <ObservedStatus value={null} reason="No subsystem evidence reported." />}
                {services.slice(0, 4).map(([name, raw]) => <div key={name}><p>{safeText(name)}</p><ObservedStatus value={record(raw).status} reason={record(raw).message} stale={evidence.health?.stale} /></div>)}
                <p>{services.length > 4 ? `Showing 4 of ${services.length} reported services. ` : ""}Core process health is not separately reported.</p>
                <Link to="/operations">Inspect operations →</Link>
            </Card>
            <WorkerExecutionSection evidence={evidence.workflows} loading={loading} />
            <Card title="Agent state" evidence={evidence.agent}>
                <AgentOverviewContent evidence={evidence.agent} />
            </Card>
            <Card title="Local AI / Runtime" evidence={evidence.ai}>
                <LocalAiContent evidence={evidence.ai} />
            </Card>
            <Card title="Providers" evidence={evidence.providers}>
                <ProviderOverviewContent evidence={evidence.providers} />
            </Card>
        </div>
        <div aria-label="Attention and activity" className="grid min-w-0 grid-cols-1 gap-4 lg:grid-cols-2">
            <Card title="Operator Attention" evidence={evidence.summary}>
                <p>Reported workflow and operational conditions. Overview counts describe these same conditions.</p>
                <SourceNote evidence={evidence.workflows} /><SourceNote evidence={evidence.health} /><SourceNote evidence={evidence.providers} /><SourceNote evidence={evidence.ai} />
                {!workflowKnown && <p>Workflow attention evidence unknown or incomplete.</p>}
                {!findingsKnown && <p>Operational findings unknown or incomplete.</p>}
                {uniqueAttention.length === 0 && <p>No attention items in the returned evidence. Missing sources do not establish an all-clear.</p>}
                <ul className="space-y-3">{uniqueAttention.slice(0, 5).map(item => <li key={item.key}>
                    <Link to={item.to}>{item.label || "Inspect condition"}</Link>
                    {"actionRequired" in item && item.actionRequired === true && <p>{item.stale ? "Last-known human action required; current requirement unknown." : "Human action required"}</p>}
                    <ObservedStatus value={item.state} reason={item.reason} stale={item.stale} />
                    {item.stale && <p>Last-known condition; current state unknown.</p>}
                </li>)}</ul>
                {uniqueAttention.length > 5 && <p>Showing 5 of {uniqueAttention.length} reported conditions. Open the detail views for more.</p>}
                <Link to="/operations">Review operational conditions →</Link>
                <Link to="/workflows">Review workflow attention →</Link>
            </Card>
            <Card title="Recent Activity" evidence={evidence.activity}>
                <RecentActivity evidence={evidence.activity} />
            </Card>
        </div>
    </>;
}
export function MissionControl() {
    const { evidence, loading, refresh } = useOverviewEvidence();
    return <main aria-label="Mission Control command center" className="mx-auto max-w-7xl space-y-6 p-4 sm:p-6 [&_a]:text-mc-primary [&_a]:underline [&_a]:underline-offset-4 [&_a:focus-visible]:outline-2">
        <header className="flex flex-wrap items-start justify-between gap-3"><div><h1 className="text-2xl font-semibold">Mission Control command center</h1><p className="text-sm text-mc-text-secondary">System overview · authoritative observations</p></div><button className="rounded-lg border border-mc-border-subtle px-4 py-2" disabled={loading} onClick={() => void refresh()}>{loading ? "Refreshing…" : "Refresh"}</button></header>
        <Overview evidence={evidence} loading={loading} />
    </main>;
}
