import { Link } from "react-router-dom";
import { HealthEvidence } from "../../components/HealthEvidence";
import { agentDisplayName, providerObservations, publicLabel } from "./agentProviderEvidence";
import { record, safeText, status } from "./overviewEvidence";
import type { Evidence } from "./useOverviewEvidence";

export function AgentOverviewContent({ evidence, loading = false }: { evidence?: Evidence; loading?: boolean }) {
    const agent = record(evidence?.data);
    const name = agentDisplayName(agent.app_name);
    const version = publicLabel(agent.version);
    const hasData = evidence?.data !== undefined;
    const stale = Boolean(evidence?.stale || (evidence?.unavailable && hasData));
    const loadingDetails = loading && !hasData && !evidence?.unavailable;
    const summary = !hasData
        ? evidence?.unavailable
            ? "Agent details could not be loaded."
            : loadingDetails
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
        {summary && (loadingDetails
            ? <p role="status" aria-live="polite">{summary}</p>
            : <p>{summary}</p>)}
    </>;
}

export function ProviderOverviewContent({ evidence, loading = false }: { evidence?: Evidence; loading?: boolean }) {
    const providers = providerObservations(evidence?.data);
    const providersNeedingAttention = providers?.filter(provider => ["degraded", "unavailable", "blocked"].includes(status(provider.status))).length ?? 0;
    const providersWithUnknownStatus = providers?.filter(provider => status(provider.status) === "unknown").length ?? 0;
    const hasData = evidence?.data !== undefined;
    const stale = Boolean(evidence?.stale || (evidence?.unavailable && evidence.data !== undefined));
    const loadingProviders = loading && !hasData && !evidence?.unavailable;
    const unavailableMessage = !hasData
        ? evidence?.unavailable
            ? "Atlas Core’s provider list could not be loaded."
            : loadingProviders
                ? "Loading providers…"
                : "Atlas Core’s provider list is not available."
        : "Provider list could not be read.";
    const renderProvider = (provider: NonNullable<typeof providers>[number], index: number) => <article key={index} aria-label={provider.name}>
        <p>{provider.name}</p>
        <HealthEvidence compact status={safeText(provider.status)} reason={safeText(provider.reason)} stale={stale} />
        {provider.path && <Link to={provider.path}>View {provider.name} →</Link>}
    </article>;
    return <>
        {providers && providers.length > 0 && <>
            <p>{stale
                ? `Last report included ${providers.length} ${providers.length === 1 ? "provider" : "providers"}; current status may have changed.`
                : `Atlas Core reports ${providers.length} ${providers.length === 1 ? "provider" : "providers"}. ${providersNeedingAttention === 0 ? "No providers need attention." : `${providersNeedingAttention} need attention.`}${providersWithUnknownStatus > 0 ? ` ${providersWithUnknownStatus} ${providersWithUnknownStatus === 1 ? "status is" : "statuses are"} unknown.` : ""}`}</p>
            <details>
                <summary className="mc-focusable cursor-pointer text-mc-primary">Show provider status ({providers.length})</summary>
                <div className="mt-2 space-y-3">{providers.map(renderProvider)}</div>
            </details>
        </>}
        {providers === null && (loadingProviders
            ? <p role="status" aria-live="polite">{unavailableMessage}</p>
            : <p>{unavailableMessage}</p>)}
        {providers?.length === 0 && <p>{stale ? "No providers were in the last Atlas Core report; the current list is unknown." : "No providers configured."}</p>}
        <details>
            <summary className="mc-focusable cursor-pointer text-mc-primary">About provider status</summary>
            <p className="mt-2">A healthy status describes Atlas Core’s latest check. The connection may change later, and this status does not allow provider actions.</p>
        </details>
        <Link to="/providers">View provider registry</Link>
    </>;
}
