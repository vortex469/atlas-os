import { Link } from "react-router-dom";
import { HealthEvidence } from "../../components/HealthEvidence";
import { publicLabel, providerDetailPath } from "./agentProviderEvidence";
import { record, safeText } from "./overviewEvidence";
import type { Evidence } from "./useOverviewEvidence";

// Inventory is an observation, never a configured selection or readiness signal.
function inventory(data: Record<string, unknown>, key: "installed" | "running"): string {
    const models = record(data.models)[key];
    const errors = record(data.errors);
    const error = errors[`${key}_models`];
    if ((data.errors !== undefined && (data.errors === null || typeof data.errors !== "object" || Array.isArray(data.errors)))
        || (error !== undefined && error !== null) || !Array.isArray(models)) return "Not available";
    if (models.length === 0) return "None reported";
    const names = models.map(model => {
        const row = record(model);
        return safeText(row.name ?? row.model).trim();
    });
    const valid = names.filter(Boolean);
    if (valid.length === 0) return "Model names unavailable";
    return `${valid.slice(0, 3).join(", ")}${valid.length > 3 ? ` (first 3 of ${valid.length})` : ""}${valid.length !== names.length ? " · Some names unavailable" : ""}`;
}

export function LocalAiContent({ evidence }: { evidence?: Evidence }) {
    const data = record(evidence?.data);
    const provider = record(data.provider);
    const health = record(data.health);
    const path = providerDetailPath(provider.id);
    const lastKnown = Boolean(evidence?.stale || (evidence?.unavailable && evidence.data !== undefined));
    const responseTime = typeof health.latency_ms === "number" && Number.isFinite(health.latency_ms) && health.latency_ms >= 0
        ? `${health.latency_ms} ms` : "Not reported";
    return <>
        <p>Configured provider: {publicLabel(provider.name) ?? publicLabel(provider.id) ?? "Unknown"}</p>
        <HealthEvidence status={safeText(health.status)} reason={safeText(health.message)} stale={lastKnown} />
        <p>Atlas does not report where this provider runs or which model is selected or ready to use.</p>
        {lastKnown && <p>Details below are from the last available report. Current version, response time, and model list are unknown.</p>}
        {evidence?.unavailable && !lastKnown && <p>Provider status could not be checked. Local runtime availability is unknown.</p>}
        <details>
            <summary className="mc-focusable cursor-pointer text-mc-primary">Technical details</summary>
            <div className="mt-3 space-y-3">
                <dl className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                    <div><dt>Version</dt><dd>{safeText(record(health.details).version).trim() || "Not reported"}</dd></div>
                    <div><dt>Response time</dt><dd>{responseTime}</dd></div>
                </dl>
                <p>{lastKnown ? "Last known installed models" : "Installed models"}: {inventory(data, "installed")}</p>
                <p>{lastKnown ? "Last known running models" : "Running models"}: {inventory(data, "running")}</p>
            </div>
        </details>
        {path && <Link to={path}>Inspect provider →</Link>}
    </>;
}
