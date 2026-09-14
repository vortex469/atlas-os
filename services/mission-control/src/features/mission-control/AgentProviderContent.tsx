import { Link } from "react-router-dom";
import { HealthEvidence } from "../../components/HealthEvidence";
import { providerObservations, publicLabel } from "./agentProviderEvidence";
import { record, safeText } from "./overviewEvidence";
import type { Evidence } from "./useOverviewEvidence";

export function AgentOverviewContent({ evidence }: { evidence?: Evidence }) {
    const agent = record(evidence?.data);
    const name = publicLabel(agent.app_name);
    return <>
        <HealthEvidence status={null} stale={evidence?.stale} reason="Agent health is not supplied by the information API." />
        <p>{name || "Agent identity unknown"}{publicLabel(agent.version) && ` · ${publicLabel(agent.version)}`}</p>
        <p>{name ? "Agent identity observed from Atlas Agent." : "Agent configuration unknown."} Identity does not establish availability or execution readiness.</p>
        <Link to="/forge">Open agent details →</Link>
        <Link className="block" to="/workflows">View agent workflows</Link>
    </>;
}

export function ProviderOverviewContent({ evidence }: { evidence?: Evidence }) {
    const providers = providerObservations(evidence?.data);
    const stale = Boolean(evidence?.stale || (evidence?.unavailable && evidence.data !== undefined));
    const renderProvider = (provider: NonNullable<typeof providers>[number], index: number) => <article key={index} aria-label={provider.name}>
        <p>{provider.name} · {provider.path ? "Configured · Registered provider" : "Configuration unknown"}</p>
        <HealthEvidence status={safeText(provider.status)} reason={safeText(provider.reason)} stale={stale} />
        {provider.path && <Link to={provider.path}>Inspect {provider.name} →</Link>}
    </article>;
    return <>
        <p>Atlas Core registry observations. Registration does not establish connection readiness or execution permission.</p>
        {providers === null && <p>Provider configuration unknown.</p>}
        {providers?.length === 0 && <p>{stale ? "No providers in the last-known registry; current configuration unknown." : evidence?.unavailable ? "Provider configuration unknown." : "No providers configured."}</p>}
        {providers?.slice(0, 4).map(renderProvider)}
        {providers && providers.length > 4 && <details><summary>{providers.length - 4} more provider observations</summary>{providers.slice(4).map(renderProvider)}</details>}
        <p>Model labels and agent-to-provider assignments are not supplied by these APIs.</p>
        <Link to="/providers">View provider registry</Link>
    </>;
}
