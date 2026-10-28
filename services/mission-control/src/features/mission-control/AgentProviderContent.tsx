import { Link } from "react-router-dom";
import { HealthEvidence } from "../../components/HealthEvidence";
import { providerObservations, publicLabel } from "./agentProviderEvidence";
import { record, safeText } from "./overviewEvidence";
import type { Evidence } from "./useOverviewEvidence";

export function AgentOverviewContent({ evidence }: { evidence?: Evidence }) {
    const agent = record(evidence?.data);
    const name = publicLabel(agent.app_name);
    return <>
        <HealthEvidence status={null} stale={evidence?.stale} reason="Atlas Agent does not report health status." />
        <p>{name || "Agent name unavailable"}{publicLabel(agent.version) && ` · ${publicLabel(agent.version)}`}</p>
        <p>A reported name does not show whether the Agent is available or can run workflows.</p>
        <Link to="/forge">Open deployment analysis →</Link>
        <Link className="block" to="/workflows">View agent workflows</Link>
    </>;
}

export function ProviderOverviewContent({ evidence }: { evidence?: Evidence }) {
    const providers = providerObservations(evidence?.data);
    const stale = Boolean(evidence?.stale || (evidence?.unavailable && evidence.data !== undefined));
    const renderProvider = (provider: NonNullable<typeof providers>[number], index: number) => <article key={index} aria-label={provider.name}>
        <p>{provider.name}</p>
        <HealthEvidence status={safeText(provider.status)} reason={safeText(provider.reason)} stale={stale} />
        {provider.path && <Link to={provider.path}>View {provider.name} →</Link>}
    </article>;
    return <>
        <p>Saved providers and their reported status. A saved provider may still be unavailable.</p>
        {providers === null && <p>Provider configuration unknown.</p>}
        {providers?.length === 0 && <p>{stale ? "No providers were in the last available list; the current list is unknown." : evidence?.unavailable ? "Provider configuration unknown." : "No providers configured."}</p>}
        {providers?.slice(0, 4).map(renderProvider)}
        {providers && providers.length > 4 && <details><summary>{providers.length - 4} more providers</summary>{providers.slice(4).map(renderProvider)}</details>}
        <details>
            <summary className="mc-focusable cursor-pointer text-mc-primary">Technical details</summary>
            <p className="mt-2">Provider health does not confirm an available connection or permission to run actions. Atlas does not report which model an Agent uses.</p>
        </details>
        <Link to="/providers">View provider registry</Link>
    </>;
}
