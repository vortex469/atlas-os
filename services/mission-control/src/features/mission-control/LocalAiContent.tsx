import { Link } from "react-router-dom";
import { HealthEvidence } from "../../components/HealthEvidence";
import { publicLabel, providerDetailPath } from "./agentProviderEvidence";
import { record, safeText } from "./overviewEvidence";
import type { Evidence } from "./useOverviewEvidence";

// Inventory is an observation, never a configured selection or readiness signal.
function inventory(data: Record<string, unknown>, key: "installed" | "running"): { summary: string; names: string[] } {
    const models = record(data.models)[key];
    const errors = record(data.errors);
    const error = errors[`${key}_models`];
    if ((data.errors !== undefined && (data.errors === null || typeof data.errors !== "object" || Array.isArray(data.errors)))
        || (error !== undefined && error !== null) || !Array.isArray(models)) return { summary: "Not available", names: [] };
    if (models.length === 0) return { summary: "None reported", names: [] };
    const names = models.map(model => {
        const row = record(model);
        return safeText(row.name ?? row.model).trim();
    });
    const valid = names.filter(Boolean);
    if (valid.length === 0) return { summary: "Model names unavailable", names: [] };
    return {
        summary: `${valid.slice(0, 3).join(", ")}${valid.length > 3 ? ` (first 3 of ${valid.length})` : ""}${valid.length !== names.length ? " · Some names unavailable" : ""}`,
        names: valid,
    };
}

function ModelInventory({ data, kind, lastKnown }: { data: Record<string, unknown>; kind: "installed" | "running"; lastKnown: boolean }) {
    const result = inventory(data, kind);
    const label = kind === "installed" ? "Installed" : "Running";
    return <>
        <p>{lastKnown ? `Last known ${kind} models` : `${label} models`}: {result.summary}</p>
        {result.names.length > 3 && <details>
            <summary className="mc-focusable cursor-pointer text-xs text-mc-primary">Show all {result.names.length} {kind} model names</summary>
            <ul className="mt-2 list-disc space-y-1 pl-5 text-sm">
                {result.names.map((name, index) => <li key={`${index}-${name}`} className="break-all">{name}</li>)}
            </ul>
        </details>}
    </>;
}

export function LocalAiContent({ evidence, loading = false }: { evidence?: Evidence; loading?: boolean }) {
    if (evidence?.data === undefined) {
        const message = evidence?.unavailable
            ? "Atlas couldn't load AI provider status."
            : loading
                ? "Loading AI provider information…"
                : "AI provider status is not available.";
        return <p role="status">{message}</p>;
    }

    const data = record(evidence?.data);
    const provider = record(data.provider);
    const health = record(data.health);
    const path = providerDetailPath(provider.id);
    const lastKnown = Boolean(evidence?.stale || (evidence?.unavailable && evidence.data !== undefined));
    const responseTime = typeof health.latency_ms === "number" && Number.isFinite(health.latency_ms) && health.latency_ms >= 0
        ? `${health.latency_ms} ms` : "Not reported";
    return <>
        <p>Configured provider: {publicLabel(provider.name) ?? publicLabel(provider.id) ?? "Not reported"}</p>
        <HealthEvidence compact status={safeText(health.status)} reason={safeText(health.message)} stale={lastKnown} />
        <p>Atlas does not report where this provider runs or which model is selected or ready to use.</p>
        {lastKnown && <p>Details below are from the last available report. Atlas could not confirm the current version, response time, or model list.</p>}
        <details>
            <summary className="mc-focusable cursor-pointer text-mc-primary">Technical details</summary>
            <div className="mt-3 space-y-3">
                <dl className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                    <div><dt>Version</dt><dd>{safeText(record(health.details).version).trim() || "Not reported"}</dd></div>
                    <div><dt>Response time</dt><dd>{responseTime}</dd></div>
                </dl>
                <ModelInventory data={data} kind="installed" lastKnown={lastKnown} />
                <ModelInventory data={data} kind="running" lastKnown={lastKnown} />
            </div>
        </details>
        {path && <Link to={path}>Inspect provider →</Link>}
    </>;
}
