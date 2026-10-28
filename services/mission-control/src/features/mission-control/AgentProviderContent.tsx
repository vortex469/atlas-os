import { Link } from "react-router-dom";
import { HealthEvidence } from "../../components/HealthEvidence";
import { providerObservations, publicLabel } from "./agentProviderEvidence";
import { record, safeText } from "./overviewEvidence";
import type { Evidence } from "./useOverviewEvidence";

export function AgentOverviewContent({ evidence }: { evidence?: Evidence }) {
    const agent = record(evidence?.data);
    const name = publicLabel(agent.app_name);
    const version = publicLabel(agent.version);
    const identity = [name, version].filter(Boolean).join(" · ");
    return <>
        <HealthEvidence status={null} stale={evidence?.stale} reason="Atlas Agent does not report its current health." />
        <Link to="/forge">Open Forge →</Link>
        <Link className="block" to="/workflows">View agent workflows</Link>
        <details>
            <summary className="mc-focusable cursor-pointer text-mc-primary">Agent details</summary>
            <div className="mt-3 space-y-3">
                <p>{identity || "Agent name and version not reported."}</p>
                <p>{identity ? "Agent name or version reported by Atlas Agent." : "Atlas Agent has not reported its name or version."} The name and version do not show whether it can run workflows.</p>
            </div>
        </details>
    </>;
}

export function ProviderOverviewContent({ evidence }: { evidence?: Evidence }) {
    const providers = providerObservations(evidence?.data);
    const stale = Boolean(evidence?.stale || (evidence?.unavailable && evidence.data !== undefined));
    const renderProvider = (provider: NonNullable<typeof providers>[number], index: number) => <article key={index} aria-label={provider.name}>
        <p>{provider.name} · {provider.path ? "Configured" : "Configuration unknown"}</p>
        <HealthEvidence status={safeText(provider.status)} reason={safeText(provider.reason)} stale={stale} />
        {provider.path && <Link to={provider.path}>Inspect {provider.name} →</Link>}
    </article>;
    return <>
        <p>A provider listed here may not be connected or allowed to perform actions.</p>
        {providers === null && <p>Provider configuration unknown.</p>}
        {providers?.length === 0 && <p>{stale ? "No providers appeared in the last successful refresh. Current configuration is unknown." : evidence?.unavailable ? "Provider configuration unknown." : "No providers configured."}</p>}
        {providers?.slice(0, 4).map(renderProvider)}
        {providers && providers.length > 4 && <details><summary>{providers.length - 4} more provider observations</summary>{providers.slice(4).map(renderProvider)}</details>}
        <p>This screen does not show model names or which provider the Agent uses.</p>
        <Link to="/providers">View provider registry</Link>
    </>;
}
