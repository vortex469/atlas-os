import { Link } from "react-router-dom";
import { HealthEvidence } from "../../components/HealthEvidence";
import { agentDisplayName, providerObservations, publicLabel } from "./agentProviderEvidence";
import { record, safeText } from "./overviewEvidence";
import type { Evidence } from "./useOverviewEvidence";

export function AgentOverviewContent({ evidence, loading = false }: { evidence?: Evidence; loading?: boolean }) {
    const agent = record(evidence?.data);
    const name = agentDisplayName(agent.app_name);
    const version = publicLabel(agent.version);
    const hasData = evidence?.data !== undefined;
    const stale = Boolean(evidence?.stale || (evidence?.unavailable && hasData));
    const summary = !hasData
        ? evidence?.unavailable
            ? "Agent details could not be loaded."
            : loading
                ? "Loading Agent details…"
                : "Agent details are not available."
        : stale
            ? "Showing the last Agent report; current details could not be loaded."
            : null;
    return <>
        {hasData && <dl className="grid grid-cols-1 gap-2 sm:grid-cols-2">
            <div><dt className="text-xs uppercase tracking-wider text-mc-text-muted">Agent</dt><dd>{name || "Agent name unavailable"}</dd></div>
            <div><dt className="text-xs uppercase tracking-wider text-mc-text-muted">Version</dt><dd>{version || "Not reported"}</dd></div>
        </dl>}
        {summary && <p>{summary}</p>}
    </>;
}

export function ProviderOverviewContent({ evidence, loading = false }: { evidence?: Evidence; loading?: boolean }) {
    const providers = providerObservations(evidence?.data);
    const additionalProviders = providers ? Math.max(0, providers.length - 4) : 0;
    const additionalProviderNoun = additionalProviders === 1 ? "provider" : "providers";
    const hasData = evidence?.data !== undefined;
    const stale = Boolean(evidence?.stale || (evidence?.unavailable && evidence.data !== undefined));
    const unavailableMessage = !hasData
        ? evidence?.unavailable
            ? "Provider list could not be loaded."
            : loading
                ? "Loading providers…"
                : "Provider list is not available."
        : "Provider list could not be read.";
    const renderProvider = (provider: NonNullable<typeof providers>[number], index: number) => <article key={index} aria-label={provider.name}>
        <p>{provider.name}</p>
        <HealthEvidence compact status={safeText(provider.status)} reason={safeText(provider.reason)} stale={stale} />
        {provider.path && <Link to={provider.path}>View {provider.name} →</Link>}
    </article>;
    return <>
        {providers && providers.length > 0 && <p>{stale ? "Showing providers from the last available report." : "Saved providers and the status Atlas reports for each one."}</p>}
        {providers === null && <p>{unavailableMessage}</p>}
        {providers?.length === 0 && <p>{stale ? "No providers were in the last available list; the current list is unknown." : "No providers configured."}</p>}
        {providers?.slice(0, 4).map(renderProvider)}
        {providers && additionalProviders > 0 && <details>
            <summary>{additionalProviders} more {additionalProviderNoun}</summary>
            {providers.slice(4).map(renderProvider)}
        </details>}
        <details>
            <summary className="mc-focusable cursor-pointer text-mc-primary">About provider status</summary>
            <p className="mt-2">A reported healthy status does not guarantee that the connection works or that actions are allowed.</p>
        </details>
        <Link to="/providers">View provider registry</Link>
    </>;
}
