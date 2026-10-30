import { useState, type ReactNode } from "react";
import { Link } from "react-router-dom";
import { AtlasDoctorPanel } from "../../components/AtlasDoctorPanel";
import { HealthEvidence } from "../../components/HealthEvidence";
import { healthNextCheck } from "../../utils/healthPresentation";
import { serviceContainerCheckCommand, serviceReachabilityCommand } from "../../utils/serviceReachabilityCommand";
import { SystemHealthSummary } from "./SystemHealthSummary";
import { formatWorkflowLabel, WORKFLOW_STATES, workflowActionRequired, workflowNextStepLabel } from "../../utils/workflowState";
import { conditionKey, detailPath, healthPriority, record, rows, safeText, status } from "./overviewEvidence";
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
    unavailableLabel?: string;
    actionRequired?: boolean;
    workflowId?: string;
    workflowState?: string;
    workflowEffectKind?: string;
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
function sourceIssue(evidence: Evidence | undefined, label: string, loading: boolean, incomplete?: string): string | null {
    if (evidence?.stale) return `${label}: refresh failed; showing the last available information.`;
    if (evidence?.unavailable) return `${label}: current information could not be loaded.`;
    if (evidence?.data === undefined) return loading ? null : `${label}: no current information is available.`;
    return incomplete ? `${label}: ${incomplete}` : null;
}
function Card({ title, children, evidence, showSourceNote = true, loading = false, id }: { title: string; children: ReactNode; evidence?: Evidence; showSourceNote?: boolean; loading?: boolean; id?: string }) {
    return <section id={id} aria-label={title} className="min-w-0 rounded-xl border border-mc-border-subtle bg-mc-surface p-4 [overflow-wrap:anywhere]">
        <h2 className="mb-3 text-lg font-semibold text-mc-text-primary">{title}</h2>
        <div className="space-y-3 text-sm text-mc-text-secondary">{showSourceNote && <SourceNote evidence={evidence} loading={loading} />}{children}</div>
    </section>;
}
function ObservedStatus({ value, reason, stale, unavailableLabel }: {
    value: unknown;
    reason?: unknown;
    stale?: boolean;
    unavailableLabel?: string;
}) {
    return <HealthEvidence compact status={safeText(value)} stale={stale} reason={safeText(reason)} unavailableLabel={unavailableLabel} />;
}

function ServiceCheckLocation({ service }: { service: unknown }) {
    const evidence = record(service);
    const url = record(evidence.details).url;
    const address = formatHealthCheckAddress(url);
    const unavailable = status(evidence.status) === "unavailable";
    const command = unavailable ? serviceReachabilityCommand(url) : null;
    const nextCheck = healthNextCheck(evidence.message);
    const httpStatus = formatHttpStatus(evidence.http_status);
    const response = httpStatus ?? (status(evidence.status) === "unavailable" ? "No response received" : "Not reported");
    const responseTime = typeof evidence.latency_ms === "number"
        && Number.isFinite(evidence.latency_ms) && evidence.latency_ms >= 0
        ? `${Math.round(evidence.latency_ms)} ms` : null;
    return <div className="mt-2">
        {unavailable && <>
            <p className="text-sm">Atlas Core could not reach this service. That does not tell whether its app is running on its own computer.</p>
            <details className="mt-2 text-xs text-mc-text-muted">
                <summary className="mc-focusable cursor-pointer text-mc-primary-strong">How to check from Atlas Core</summary>
                <div role="group" aria-label="Next connection check" className="mt-2 rounded-lg border border-mc-border-subtle bg-mc-surface-muted p-3 text-sm text-mc-text-secondary">
                    <p className="font-medium text-mc-text-primary">From the computer running Atlas Core, open a terminal in the folder containing <code>compose.production.yaml</code> and run this command. It makes a read-only request inside the <code>atlas-core</code> container; running it on the service computer or in your browser checks a different network path.</p>
                    <p className={address ? "mt-1 break-all font-mono text-mc-text-primary" : "mt-1 text-mc-text-primary"}>{address ?? "Configured service address not reported"}</p>
                    {command && <>
                        <p className="mt-2 text-xs text-mc-text-muted">Read-only connection check:</p>
                        <div role="group" aria-label="Read-only Core connection check command" className="mt-1 rounded border border-mc-border-subtle bg-mc-surface p-2">
                            <pre className="whitespace-pre-wrap break-all font-mono text-xs leading-5 text-mc-text-primary">{command}</pre>
                        </div>
                        <p className="mt-2 text-xs">An HTTP status means a server answered. A timeout or connection error means Core received no HTTP response. URL credentials and query values are left out.</p>
                        <p className="mt-2 text-sm"><strong>File not found?</strong> Compose did not run the check. Run it from Atlas&apos;s Compose folder or pass the full file path with <code>--file</code>.</p>
                    </>}
                </div>
            </details>
        </>}
        <details className="mt-2 text-xs text-mc-text-muted">
            <summary className="mc-focusable cursor-pointer text-mc-primary-strong">Docker and network checks</summary>
            <div className="mt-2 space-y-1">
                <ol aria-label="Docker and Compose checks" className="list-decimal space-y-2 pl-5 text-sm leading-6 text-mc-text-secondary">
                    <li>
                        On the service computer, run <code>{serviceContainerCheckCommand}</code> to show container names, running status, network, and published ports.
                    </li>
                    <li>
                        Find the service container. <code>Up</code> means the container is running, not that its web app is responding. If <code>Networks</code> says <code>host</code>, a blank <code>PORTS</code> field is expected. Otherwise, a blank field means no host port is published. A mapping starting with <code>127.0.0.1:</code> is reachable only from that computer.
                    </li>
                    <li>
                        To publish a port, use Compose&apos;s <code>ports:</code> or <code>docker run -p</code>. In <code>HOST_PORT:CONTAINER_PORT</code>, the number before the colon must match the port in Atlas&apos;s configured address. The number after it must match the app&apos;s listening port. Recreate the container after changing its ports.
                    </li>
                    <li>
                        With Docker host networking, no published-port mapping is expected; the app listens directly on the service computer&apos;s port.
                    </li>
                </ol>
                <p>Address Atlas checked: <span className={address ? "break-all font-mono" : ""}>{address ?? "Not reported"}</span></p>
                <p>HTTP response: {response}</p>
                {responseTime !== null && <p>Response time: {responseTime}</p>}
                {nextCheck !== null && <p>Next check: {nextCheck}</p>}
            </div>
        </details>
    </div>;
}

function formatHttpStatus(value: unknown): string | null {
    return typeof value === "number" && Number.isInteger(value) && value >= 100 && value <= 599
        ? String(value) : null;
}

function formatHealthCheckAddress(value: unknown): string | null {
    if (typeof value !== "string" || !value.trim()) return null;
    try {
        const url = new URL(value);
        return `${url.protocol}//${url.host}${url.pathname}${url.search ? "?…" : ""}`;
    } catch {
        return null;
    }
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

function workflowAttentionStage(state: string, effectKind?: string): string {
    switch (state) {
        case "planned": return "initial review";
        case "awaiting_approval": return "change preparation";
        case "awaiting_implementation_approval": return effectKind === "operational_action" ? "maintenance request approval" : "change approval";
        case "awaiting_execution": return effectKind === "operational_action" ? "the approved maintenance run" : "the approved change run";
        case "awaiting_verification_approval": return "verification approval";
        case "awaiting_commit_approval": return "commit approval";
        default: return formatWorkflowLabel(state);
    }
}

function workflowReasonRepeatsStage(reason: string, state: string, effectKind?: string): boolean {
    const normalizedReason = reason.trim().replace(/[.!?]+$/, "").toLowerCase();
    const legacyStatus = legacyWorkflowAttentionStatus(state, effectKind);
    return normalizedReason === workflowAttentionStage(state, effectKind).toLowerCase()
        || normalizedReason === workflowNextStepLabel(state, effectKind)?.replace(/[.!?]+$/, "").toLowerCase()
        || legacyStatus.some((label) => normalizedReason === label.toLowerCase());
}

function legacyWorkflowAttentionStatus(state: string, effectKind?: string): string[] {
    switch (state) {
        case "planned": return ["Ready for review"];
        case "awaiting_approval": return ["Waiting for approval"];
        case "awaiting_implementation_approval": return effectKind === "operational_action"
            ? ["Waiting for maintenance request approval", "Waiting for implementation approval"]
            : ["Waiting for implementation approval"];
        case "awaiting_execution": return ["Approved and ready to run"];
        case "awaiting_verification_approval": return ["Waiting for verification approval"];
        case "awaiting_commit_approval": return ["Waiting for commit approval"];
        default: return [];
    }
}

function workflowAttentionLabel(intent: unknown, state: string, stale: boolean, effectKind?: string): string {
    const safeIntent = safeText(intent);
    const action = safeIntent && safeIntent !== "[Sensitive text withheld]"
        ? formatWorkflowLabel(safeIntent)
        : "Workflow";
    const stage = stale || workflowActionRequired(state) ? "" : ` · ${workflowAttentionStage(state, effectKind)}`;
    return `${action}${stage}`;
}

function attentionKey(finding: Record<string, unknown>, providers: Record<string, unknown>[], services: [string, unknown][]) {
    if (typeof finding.source === "string" && typeof finding.message === "string" && finding.message.length > 0) {
        const providerMatch = providers.some(p => p.id === finding.source && record(p.health).message === finding.message);
        const serviceMatch = services.some(([, raw]) => record(raw).provider_id === finding.source && record(raw).message === finding.message);
        if (providerMatch || serviceMatch) return conditionKey(finding.source, finding.message);
    }
    return conditionKey("finding", finding.id, finding.source, finding.title, finding.message);
}

function findingAttentionPath(
    finding: Record<string, unknown>,
    providers: Record<string, unknown>[],
    aiProvider: Record<string, unknown>,
    aiHealth: Record<string, unknown>,
    services: [string, unknown][],
) {
    const { source, message } = finding;
    if (typeof source !== "string" || typeof message !== "string") return "#system-health";

    const matchingService = services.some(([, raw]) =>
        record(raw).provider_id === source && record(raw).message === message);
    if (matchingService) return "#service-checks";

    const matchingProvider = providers.some(p =>
        p.id === source && record(p.health).message === message);
    if (matchingProvider) return providerDetailPath(source) ?? "#providers";

    if (aiProvider.id === source && aiHealth.message === message) {
        return providerDetailPath(source) ?? "#ai-provider";
    }
    return "#system-health";
}

function AttentionListItem({ item }: { item: AttentionItem }) {
    return <li>
        {item.to.startsWith("#")
            ? <a className="mc-focusable" href={item.to}>{item.label || "Inspect condition"}</a>
            : <Link to={item.to}>{item.label || "Inspect condition"}</Link>}
        {item.actionRequired === true && <p>{isWorkflowAttention(item)
            ? item.stale
                ? `Last report: this workflow was waiting for ${workflowAttentionStage(item.workflowState, item.workflowEffectKind)}. Atlas could not confirm whether it still needs attention.`
                : `Action needed: ${workflowNextStepLabel(item.workflowState, item.workflowEffectKind) ?? "Open the workflow to review the next step."}`
            : item.stale ? "The last report said an operator needed to act. Atlas could not confirm whether that is still required." : "Human action required"}</p>}
        {isWorkflowAttention(item) ? <>
            {item.state === "blocked" && item.stale && <p className="text-red-300">Last report: this workflow was blocked. Atlas could not confirm its current status.</p>}
            {item.reason && !workflowReasonRepeatsStage(item.reason, item.workflowState, item.workflowEffectKind) && <p>{item.reason}</p>}
            <details><summary className="mc-focusable cursor-pointer text-sm text-mc-primary-strong">Technical details</summary>
                <p>Workflow ID: <span className="break-all font-mono">{item.workflowId}</span></p>
                <p className="text-xs text-mc-text-muted">Atlas did not provide a stage update time.</p>
            </details>
        </> : <ObservedStatus value={item.state} reason={item.reason} stale={item.stale} unavailableLabel={item.unavailableLabel} />}
    </li>;
}

export function Overview({ evidence, loading = false }: { evidence: OverviewEvidence; loading?: boolean }) {
    const [showAllAttention, setShowAllAttention] = useState(false);
    const [showAllServices, setShowAllServices] = useState(false);
    const health = record(evidence.health?.data);
    const services = Object.entries(record(health.services)).sort((a, b) =>
        healthPriority(record(a[1]).status) - healthPriority(record(b[1]).status));
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
    const attentionSourceIssues = [
        sourceIssue(evidence.summary, "System findings", loading, findingsKnown ? undefined : "finding details are incomplete."),
        sourceIssue(evidence.workflows, "Workflows", loading, workflowKnown ? undefined : "workflow results are incomplete."),
        sourceIssue(evidence.health, "System health", loading, healthStatusesKnown ? undefined : "health details are incomplete."),
        sourceIssue(evidence.providers, "Providers", loading, providersKnown ? undefined : "provider status details are incomplete."),
        sourceIssue(evidence.ai, "AI provider", loading, status(aiHealth.status) === "unknown" ? "provider status is unknown." : undefined),
    ].filter((issue): issue is string => issue !== null);
    const initialAttentionLoad = loading && !attentionSources.some(source =>
        source?.data !== undefined || source?.unavailable === true);
    // One row per authoritative source condition. Do not synthesize alerts from counts.
    const attention: AttentionItem[] = [
        ...services.filter(([, raw]) => ["degraded", "unavailable", "blocked"].includes(status(record(raw).status))).map(([name, raw]) => ({
            key: conditionKey(record(raw).provider_id || name, record(raw).message), label: safeText(name), reason: safeText(record(raw).message), state: record(raw).status, to: "#service-checks", stale: evidence.health?.stale, unavailableLabel: "Atlas Core could not connect",
        })),
        ...providers.filter(p => ["degraded", "unavailable", "blocked"].includes(status(record(p.health).status))).map(p => ({
            key: conditionKey(p.id, record(p.health).message), label: safeText(p.name), reason: safeText(record(p.health).message), state: record(p.health).status, to: providerDetailPath(p.id) ?? "#providers", stale: evidence.providers?.stale,
        })),
        ...(["degraded", "unavailable", "blocked"].includes(status(aiHealth.status)) ? [{
            key: detailPath("/providers", aiProvider.id) ? conditionKey(aiProvider.id, aiHealth.message) : conditionKey("ai/status", null, aiHealth.message), label: safeText(aiProvider.name) || "Configured AI provider", reason: safeText(aiHealth.message), state: aiHealth.status, to: providerDetailPath(aiProvider.id) ?? "#ai-provider", stale: evidence.ai?.stale,
        }] : []),
        ...findings.filter(f => typeof f.severity === "string" && ["warning", "critical", "blocked"].includes(f.severity)).map(f => ({
            key: attentionKey(f, [...providers, { ...aiProvider, health: aiHealth }], services), label: safeText(f.title), reason: safeText(f.message), state: f.severity, to: findingAttentionPath(f, providers, aiProvider, aiHealth, services), stale: evidence.summary?.stale,
        })),
        ...validWorkflows.filter(w => w.workflow_state === "blocked" || workflowActionRequired(String(w.workflow_state))).map(w => {
            const workflowEffectKind = typeof w.effect_kind === "string" ? w.effect_kind : undefined;
            return {
                actionRequired: workflowActionRequired(String(w.workflow_state)),
                workflowId: safeText(w.workflow_id),
                workflowEffectKind,
                key: `workflow:${String(w.workflow_id)}`,
                label: workflowAttentionLabel(w.execution_intent, String(w.workflow_state), evidence.workflows?.stale === true, workflowEffectKind),
                reason: safeText(w.last_result_summary),
                state: w.workflow_state === "blocked" ? "blocked" : "warning",
                to: detailPath("/workflows", w.workflow_id) ?? "/workflows",
                stale: evidence.workflows?.stale,
                workflowState: String(w.workflow_state),
            };
        }),
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
        <Card title="Needs attention" showSourceNote={false}>
            {!initialAttentionLoad && loading && <p role="status">Checking the latest information. This list may update when more checks finish.</p>}
            {!loading && !initialAttentionLoad && !attentionEvidenceComplete && <>
                <p role="status">Some checks aren't available. This list may be incomplete.</p>
                {attentionSourceIssues.length > 0 && <details>
                    <summary className="mc-focusable cursor-pointer text-sm text-mc-primary-strong">Which results are missing?</summary>
                    <ul className="mt-2 space-y-1">
                        {attentionSourceIssues.map(issue => <li key={issue}>{issue}</li>)}
                    </ul>
                </details>}
            </>}
            {uniqueAttention.length === 0 && loading && initialAttentionLoad && <p>Checking current information…</p>}
            {uniqueAttention.length === 0 && !loading && attentionEvidenceComplete && <p>The latest reports show no items needing attention.</p>}
            <ul aria-label="Items needing attention" className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">{displayedAttention.map(item => <AttentionListItem key={item.key} item={item} />)}</ul>
            {uniqueAttention.length > 5 && <button
                type="button"
                className="mc-control mc-focusable rounded-lg border border-mc-border-subtle px-3 py-2 text-sm font-medium text-mc-primary-strong"
                aria-expanded={showAllAttention}
                onClick={() => setShowAllAttention(current => !current)}
            >{showAllAttention ? "Show fewer items" : `Show all ${uniqueAttention.length} items`}</button>}
        </Card>
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3" data-testid="overview-grid">
            <Card id="system-health" title="System health" showSourceNote={false}>
                <SystemHealthSummary evidence={evidence} loading={loading} />
                <details>
                    <summary className="mc-focusable cursor-pointer text-sm text-mc-primary-strong">Use Atlas Doctor</summary>
                    <div className="mt-3"><AtlasDoctorPanel /></div>
                </details>
            </Card>
            <Card id="service-checks" title="Service checks" evidence={evidence.health} loading={loading}>
                <p>These results show whether Atlas Core can reach each service. Unavailable means it got no response; the service may still be running on its own computer.</p>
                {services.length === 0 && loading && evidence.health?.data === undefined && <p>Checking configured services…</p>}
                {services.length === 0 && evidence.health?.data !== undefined && <ObservedStatus value={null} reason={serviceChecksKnown ? "No configured service checks were reported." : "Service check details are unavailable."} stale={evidence.health.stale} />}
                {displayedServices.length > 0 && <ul aria-label="Configured service checks" className="space-y-3">{displayedServices.map(([name, raw]) => <li key={name}>
                    <p>{safeText(name)}</p>
                    <ObservedStatus
                        value={record(raw).status}
                        reason={record(raw).message}
                        stale={evidence.health?.stale}
                        unavailableLabel="Atlas Core could not connect"
                    />
                    <ServiceCheckLocation service={raw} />
                </li>)}</ul>}
                {services.length > 4 && <button
                    type="button"
                    className="mc-control mc-focusable rounded-lg border border-mc-border-subtle px-3 py-2 text-sm font-medium text-mc-primary-strong"
                    aria-expanded={showAllServices}
                    onClick={() => setShowAllServices(current => !current)}
                >{showAllServices ? "Show fewer service checks" : `Show all ${services.length} service checks`}</button>}
                <details><summary className="mc-focusable cursor-pointer text-sm text-mc-primary-strong">About service checks</summary>
                    <p>These checks cover the listed services. For Atlas Core's own health, use the System health card.</p>
                </details>
            </Card>
            <WorkerExecutionSection evidence={evidence.workflows} loading={loading} />
            <Card title="Agent details" showSourceNote={false}>
                <AgentOverviewContent evidence={evidence.agent} loading={loading} />
            </Card>
            <Card id="ai-provider" title="AI provider" evidence={evidence.ai} showSourceNote={evidence.ai?.data !== undefined} loading={loading}>
                <LocalAiContent evidence={evidence.ai} loading={loading} />
            </Card>
            <Card id="providers" title="Providers" showSourceNote={false}>
                <ProviderOverviewContent evidence={evidence.providers} loading={loading} />
            </Card>
        </div>
        <Card title="Recent provider actions" showSourceNote={false}>
            <RecentActivity evidence={evidence.activity} loading={loading} />
        </Card>
    </>;
}
export function MissionControl() {
    const { evidence, loading, hasLoaded, refresh } = useOverviewEvidence();
    return <main aria-label="Overview" className="mx-auto max-w-7xl space-y-6 p-4 sm:p-6 [&_a]:text-mc-primary [&_a]:underline [&_a]:underline-offset-4 [&_a:focus-visible]:outline-2">
        <header className="flex flex-wrap items-start justify-between gap-3"><div><h1 className="text-2xl font-semibold">Overview</h1><p className="text-sm text-mc-text-secondary">Status, alerts, and recent work.</p></div><button className="rounded-lg border border-mc-border-subtle px-4 py-2" disabled={loading} onClick={() => void refresh()}>{loading ? hasLoaded ? "Refreshing…" : "Loading…" : "Refresh"}</button></header>
        <Overview evidence={evidence} loading={loading} />
    </main>;
}
