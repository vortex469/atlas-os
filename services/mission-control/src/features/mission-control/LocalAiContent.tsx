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
        || (error !== undefined && error !== null) || !Array.isArray(models)) return "Unknown — inventory unavailable";
    if (models.length === 0) return "None reported";
    const names = models.map(model => {
        const row = record(model);
        return safeText(row.name ?? row.model).trim();
    });
    const valid = names.filter(Boolean);
    if (valid.length === 0) return "Unknown — inventory malformed or incomplete";
    return `${valid.slice(0, 3).join(", ")}${valid.length > 3 ? ` (showing 3 of ${valid.length} reported identities)` : ""}${valid.length !== names.length ? " · Some model identities unknown" : ""}`;
}

export function LocalAiContent({ evidence }: { evidence?: Evidence }) {
    const data = record(evidence?.data);
    const provider = record(data.provider);
    const health = record(data.health);
    const path = providerDetailPath(provider.id);
    const lastKnown = Boolean(evidence?.stale || (evidence?.unavailable && evidence.data !== undefined));
    const latency = typeof health.latency_ms === "number" && Number.isFinite(health.latency_ms) && health.latency_ms >= 0
        ? `${health.latency_ms} ms` : "Unknown — not exposed";
    return <>
        <HealthEvidence status={null} reason="Local AI availability is unknown; locality is not reported." />
        <p>Configured provider health</p>
        <HealthEvidence status={safeText(health.status)} reason={safeText(health.message)} stale={lastKnown} />
        <p>Configured AI provider: {publicLabel(provider.name) ?? publicLabel(provider.id) ?? "Unknown"}</p>
        <p>Locality and dedicated Local AI Runtime capabilities are not exposed. This is configured AI provider health only.</p>
        <p>Configured model identity: Unknown.</p>
        {lastKnown && <p>Last-known runtime observations below; current version, latency, and model inventory unknown.</p>}
        {evidence?.unavailable && !lastKnown && <p>AI status observation unavailable; runtime availability is unknown.</p>}
        <dl className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <div><dt>Reported runtime version</dt><dd>{safeText(record(health.details).version).trim() || "Unknown — not exposed"}</dd></div>
            <div><dt>Reported health latency</dt><dd>{latency}</dd></div>
        </dl>
        <p>{lastKnown ? "Last-known installed models" : "Reported installed models"}: {inventory(data, "installed")}</p>
        <p>{lastKnown ? "Last-known running models" : "Reported running models"}: {inventory(data, "running")}</p>
        <p>Installed or running inventory does not establish configured model selection, current loaded state, active execution, or inference readiness.</p>
        {path && <Link to={path}>Inspect runtime provider →</Link>}
    </>;
}
