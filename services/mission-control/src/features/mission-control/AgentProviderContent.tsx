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
        {providers === null && <p>{evidence?.unavailable ? "Provider details could not be loaded. Refresh Mission Control to try again." : "Provider configuration is not available."}</p>}
        {providers?.length === 0 && <p>{stale ? "No providers appeared in the last successful refresh. Current configuration is unknown." : evidence?.unavailable ? "Provider configuration unknown." : "No providers configured."}</p>}
        {providers && providers.length > 0 && <>
            <p>{stale ? `Showing last reported details for ${providers.length} provider${providers.length === 1 ? "" : "s"}. Current status is unknown.` : `${providers.length} provider${providers.length === 1 ? "" : "s"} reported.`}</p>
            <details className="rounded-lg border border-mc-border-subtle p-3">
                <summary className="mc-focusable cursor-pointer text-mc-primary">Show provider status ({providers.length})</summary>
                <div className="mt-3 space-y-3">
                    {providers.slice(0, 4).map(renderProvider)}
                    {providers.length > 4 && <details><summary className="mc-focusable cursor-pointer text-mc-primary">More providers ({providers.length - 4})</summary><div className="mt-3 space-y-3">{providers.slice(4).map(renderProvider)}</div></details>}
                </div>
            </details>
        </>}
        <p>Provider health does not show whether actions are allowed.</p>
        <Link to="/providers">View provider registry</Link>
    </>;
}
