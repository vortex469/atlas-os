import { useEffect, useState } from "react";
import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import { HealthStatusBadge } from "../../components/health/HealthStatusPrimitive";
import { workflowActionRequired } from "../../utils/workflowState";
import { detailPath, record, rows, safeText, status, timestamp } from "./overviewEvidence";
import { useOverviewEvidence } from "./useOverviewEvidence";
import type { Evidence, OverviewEvidence } from "./useOverviewEvidence";

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
    return <HealthStatusBadge state={stale ? "unknown" : status(value)} reason={safeText(reason)} />;
}

function attentionKey(finding: Record<string, unknown>, providers: Record<string, unknown>[], services: [string, unknown][]) {
    if (typeof finding.source === "string" && typeof finding.message === "string" && finding.message.length > 0) {
        const providerMatch = providers.some(p => p.id === finding.source && record(p.health).message === finding.message);
        const serviceMatch = services.some(([, raw]) => record(raw).provider_id === finding.source && record(raw).message === finding.message);
        if (providerMatch || serviceMatch) return `subsystem:${finding.source}`;
    }
    return `finding:${safeText(finding.id) || safeText(finding.title)}`;
}

export function Overview({ evidence }: { evidence: OverviewEvidence }) {
    const [now, setNow] = useState(() => Date.now());
    useEffect(() => {
        const timer = window.setInterval(() => setNow(Date.now()), 30_000);
        return () => window.clearInterval(timer);
    }, []);
    const health = record(evidence.health?.data);
    const services = Object.entries(record(health.services)).sort((a, b) =>
        Number(status(record(a[1]).status) === "healthy") - Number(status(record(b[1]).status) === "healthy"));
    const providers = rows(evidence.providers?.data);
    const workflows = rows(record(evidence.workflows?.data).items);
    const validWorkflows = workflows.filter(w => typeof w.workflow_id === "string" && typeof w.workflow_state === "string");
    const workflowKnown = Array.isArray(record(evidence.workflows?.data).items) && workflows.length === validWorkflows.length;
    const ai = record(evidence.ai?.data);
    const runningModels = rows(record(ai.models).running).map(model => safeText(model.name ?? model.model)).filter(Boolean);
    const agent = record(evidence.agent?.data);
    const findings = rows(record(evidence.summary?.data).findings);
    // One row per authoritative source condition. Do not synthesize alerts from counts.
    const attention = [
        ...services.filter(([, raw]) => ["degraded", "unavailable", "blocked"].includes(status(record(raw).status))).map(([name, raw]) => ({
            key: `subsystem:${String(record(raw).provider_id || name)}`, label: safeText(name), reason: safeText(record(raw).message), state: record(raw).status, to: detailPath("/providers", record(raw).provider_id) ?? "/operations", stale: evidence.health?.stale,
        })),
        ...providers.filter(p => ["degraded", "unavailable", "blocked"].includes(status(record(p.health).status))).map(p => ({
            key: `subsystem:${String(p.id)}`, label: safeText(p.name), reason: safeText(record(p.health).message), state: record(p.health).status, to: detailPath("/providers", p.id) ?? "/operations", stale: evidence.providers?.stale,
        })),
        ...findings.filter(f => ["warning", "critical", "blocked"].includes(String(f.severity))).map(f => ({
            key: attentionKey(f, providers, services), label: safeText(f.title), reason: safeText(f.message), state: f.severity, to: "/operations", stale: evidence.summary?.stale,
        })),
        ...validWorkflows.filter(w => w.workflow_state === "blocked" || workflowActionRequired(String(w.workflow_state))).map(w => ({
            key: `workflow:${String(w.workflow_id)}`, label: safeText(w.workflow_id), reason: `${safeText(w.workflow_state)} · ${safeText(w.last_result_summary)}`, state: "blocked", to: detailPath("/workflows", w.workflow_id) ?? "/workflows", stale: evidence.workflows?.stale,
        })),
    ];
    const deduplicated = new Map<string, typeof attention[number]>();
    for (const item of attention) {
        const previous = deduplicated.get(item.key);
        if (!previous || (previous.stale && !item.stale)) deduplicated.set(item.key, item);
    }
    const uniqueAttention = [...deduplicated.values()]
        .sort((a, b) => (status(a.state) === "blocked" ? 0 : status(a.state) === "unavailable" ? 1 : 2) - (status(b.state) === "blocked" ? 0 : status(b.state) === "unavailable" ? 1 : 2));
    const activity = rows(record(evidence.activity?.data).items).filter(event => typeof event.id === "string" && typeof event.action_label === "string").sort((a, b) => (timestamp(b.completed_at)?.getTime() ?? 0) - (timestamp(a.completed_at)?.getTime() ?? 0));
    return <>
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3" data-testid="overview-grid">
            <Card title="Atlas overall state" evidence={evidence.health}>
                <ObservedStatus value={health.atlas} stale={evidence.health?.stale} />
                <p>Atlas-reported state from Core health.</p>
                <p>Evidence update time is not supplied.</p>
                <Link to="/operations">Open operations →</Link>
            </Card>
            <Card title="Core health" evidence={evidence.health}>
                {services.length === 0 && <ObservedStatus value={null} reason="No subsystem evidence reported." />}
                {services.slice(0, 4).map(([name, raw]) => <div key={name}><p>{safeText(name)}</p><ObservedStatus value={record(raw).status} reason={record(raw).message} stale={evidence.health?.stale} /></div>)}
                <p>{services.length > 4 ? `Showing 4 of ${services.length} reported services. ` : ""}Core process health is not separately reported.</p>
                <Link to="/operations">Inspect operations →</Link>
            </Card>
            <Card title="Worker / Execution" evidence={evidence.workflows}>
                <ObservedStatus value={null} reason="Worker availability and queue depth are not exposed by this evidence." />
                {workflowKnown ? <>
                    <p>Returned workflows: {validWorkflows.length}. Active: {validWorkflows.filter(w => w.workflow_state === "executing").length}. Blocked: {validWorkflows.filter(w => w.workflow_state === "blocked").length}.</p>
                    <p>Completed outcomes: {validWorkflows.filter(w => w.workflow_state === "completed").length}. First page only, up to 200 workflows.</p>
                </> : <p>Execution observations unknown.</p>}
                <p>Workflow observations do not establish worker idleness, admission, or permission to execute.</p>
                <Link to="/workflows">Inspect executions →</Link>
            </Card>
            <Card title="Agent state" evidence={evidence.agent}>
                <ObservedStatus value={null} reason="Agent health is not supplied by the information API." />
                <p>{safeText(agent.app_name) || "Agent identity unknown"}{safeText(agent.version) && ` · ${safeText(agent.version)}`}</p>
                <Link to="/forge">Open agent details →</Link>
            </Card>
            <Card title="Local AI / Runtime" evidence={evidence.ai}>
                <ObservedStatus value={record(ai.health).status} reason={record(ai.health).message} stale={evidence.ai?.stale} />
                <p>Configured AI provider: {safeText(record(ai.provider).name) || "Unknown"}</p>
                <p>Locality and dedicated Local AI Runtime capabilities are not exposed. This is configured AI provider health only.</p>
                <p>Configured model identity: Unknown.</p>
                {runningModels.length > 0 && !record(ai.errors).running_models && <p>Reported running models: {runningModels.slice(0, 3).join(", ")}</p>}
                {detailPath("/providers", record(ai.provider).id) && <Link to={detailPath("/providers", record(ai.provider).id)!}>Inspect runtime provider →</Link>}
            </Card>
            <Card title="Providers" evidence={evidence.providers}>
                {providers.length === 0 && <p>{Array.isArray(evidence.providers?.data) ? "No providers configured." : "Provider configuration unknown."}</p>}
                {providers.slice(0, 4).map((provider, index) => <div key={index}>
                    <p>{safeText(provider.name) || "Unknown provider"} · {detailPath("/providers", provider.id) ? "Configured" : "Configuration unknown"}</p>
                    <ObservedStatus value={detailPath("/providers", provider.id) ? record(provider.health).status : null} reason={record(provider.health).message} stale={evidence.providers?.stale} />
                    {detailPath("/providers", provider.id) && <Link to={detailPath("/providers", provider.id)!}>Inspect {safeText(provider.name) || "provider"} →</Link>}
                </div>)}
                {providers.length > 4 && <details><summary>{providers.length - 4} more configured providers</summary>{providers.slice(4).map((p, i) => <div key={i}>{detailPath("/providers", p.id) ? <Link to={detailPath("/providers", p.id)!}>{safeText(p.name) || "Provider details"}</Link> : "Unknown provider"}<ObservedStatus value={record(p.health).status} stale={evidence.providers?.stale} /></div>)}</details>}
            </Card>
        </div>
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            <Card title="Operator Attention" evidence={evidence.summary}>
                <SourceNote evidence={evidence.workflows} /><SourceNote evidence={evidence.health} /><SourceNote evidence={evidence.providers} />
                {uniqueAttention.length === 0 && <p>No attention items in the returned evidence. Missing sources do not establish an all-clear.</p>}
                {uniqueAttention.slice(0, 5).map(item => <div key={item.key}><Link to={item.to}>{item.label || "Inspect condition"}</Link><ObservedStatus value={item.state} reason={item.reason} stale={item.stale} />{item.stale && <p>Last-known condition; current state unknown.</p>}</div>)}
                <Link to="/operations">Review operational conditions →</Link>
                <Link to="/workflows">Review workflow attention →</Link>
            </Card>
            <Card title="Recent Activity" evidence={evidence.activity}>
                <p>Recent provider action outcomes. Historical results do not establish current subsystem health.</p>
                {activity.length === 0 && <p>{Array.isArray(record(evidence.activity?.data).items) ? (rows(record(evidence.activity?.data).items).length === 0 ? "No recent actions recorded." : "Activity evidence malformed or incomplete.") : "Activity evidence unknown."}</p>}
                {activity.length > 0 && activity.length < rows(record(evidence.activity?.data).items).length && <p>Some activity records are malformed or incomplete.</p>}
                {activity.slice(0, 5).map((event, index) => {
                    const date = timestamp(event.completed_at);
                    return <div key={index}><p>{event.status === "failed" ? "Error" : event.status === "succeeded" ? "Informational" : "Unknown outcome"} · {safeText(event.action_label)}</p><p>{safeText(event.message)}</p>{detailPath("/operations/actions", event.id) && <Link to={detailPath("/operations/actions", event.id)!}>Inspect action →</Link>}{date ? <time dateTime={date.toISOString()}>{date.toISOString()}</time> : <p>Completion time unknown.</p>}<p>{date && now - date.getTime() > 300_000 ? "Historical evidence (older than 5 minutes)." : "Action history does not establish current health."}</p></div>;
                })}
                <Link to="/operations/history">Open operational history →</Link>
            </Card>
        </div>
    </>;
}
export function MissionControl() {
    const { evidence, loading, refresh } = useOverviewEvidence();
    return <main aria-label="Mission Control command center" className="mx-auto max-w-7xl space-y-6 p-4 sm:p-6 [&_a]:text-mc-primary [&_a]:underline [&_a]:underline-offset-4 [&_a:focus-visible]:outline-2">
        <header className="flex flex-wrap items-start justify-between gap-3"><div><h1 className="text-2xl font-semibold">Mission Control command center</h1><p className="text-sm text-mc-text-secondary">System overview · authoritative observations</p></div><button className="rounded-lg border border-mc-border-subtle px-4 py-2" disabled={loading} onClick={() => void refresh()}>{loading ? "Refreshing…" : "Refresh"}</button></header>
        <Overview evidence={evidence} />
    </main>;
}
