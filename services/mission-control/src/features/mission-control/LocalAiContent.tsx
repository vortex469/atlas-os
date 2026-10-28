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
        || (error !== undefined && error !== null) || !Array.isArray(models)) return "Could not load list";
    if (models.length === 0) return "None reported";
    const names = models.map(model => {
        const row = record(model);
        return safeText(row.name ?? row.model).trim();
    });
    const valid = names.filter(Boolean);
    if (valid.length === 0) return "Model names could not be read";
    return `${valid.slice(0, 3).join(", ")}${valid.length > 3 ? ` (showing 3 of ${valid.length})` : ""}${valid.length !== names.length ? " · Some model names could not be read" : ""}`;
}

export function LocalAiContent({ evidence }: { evidence?: Evidence }) {
    if (evidence?.data === undefined) return <>
        <p>{evidence?.unavailable ? "AI provider details could not be loaded. Refresh Mission Control to try again." : "AI provider information has not been received yet."}</p>
        <Link to="/providers">View provider registry</Link>
    </>;
    const data = record(evidence?.data);
    const provider = record(data.provider);
    const health = record(data.health);
    const path = providerDetailPath(provider.id);
    const lastKnown = Boolean(evidence?.stale || (evidence?.unavailable && evidence.data !== undefined));
    const latency = typeof health.latency_ms === "number" && Number.isFinite(health.latency_ms) && health.latency_ms >= 0
        ? `${health.latency_ms} ms` : "Not reported";
    return <>
        <p>Configured AI provider: {publicLabel(provider.name) ?? publicLabel(provider.id) ?? "Unknown"}</p>
        <HealthEvidence status={safeText(health.status)} reason={safeText(health.message)} stale={lastKnown} />
        <p>Provider health does not show whether AI is available on this computer.</p>
        {lastKnown && <p>The details below are from the last successful refresh. Current version, response time, and model lists are not confirmed.</p>}
        {path && <Link to={path}>Inspect AI provider →</Link>}
        <details>
            <summary className="mc-focusable cursor-pointer text-mc-primary">AI details</summary>
            <div className="mt-3 space-y-3">
                <p>These details describe the configured provider. They do not confirm whether AI runs on this computer.</p>
                <p>Selected model: Not reported.</p>
                <dl className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                    <div><dt>Runtime version</dt><dd>{safeText(record(health.details).version).trim() || "Not reported"}</dd></div>
                    <div><dt>Health check response time</dt><dd>{latency}</dd></div>
                </dl>
                <p>Installed models: {inventory(data, "installed")}</p>
                <p>Running models: {inventory(data, "running")}</p>
                <p>These lists do not show which model is selected or ready to use.</p>
            </div>
        </details>
    </>;
}
