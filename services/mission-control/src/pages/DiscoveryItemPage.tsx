import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { getAtlasErrorMessage } from "../api/atlas";
import {
    getDiscoveryCompatibility,
    getDiscoveryItem,
    getDiscoveryRelationships,
} from "../api/discovery";
import type {
    DiscoveryCatalogEntry,
    DiscoveryCompatibilityAssessment,
    DiscoveryRelationshipReference,
    DiscoveryRequirements,
} from "../types/discovery";

type DetailState = {
    entry: DiscoveryCatalogEntry | null;
    incoming: DiscoveryRelationshipReference[];
    outgoing: DiscoveryRelationshipReference[];
};

export function DiscoveryItemPage() {
    const { itemId = "" } = useParams<{ itemId: string }>();
    const [state, setState] = useState<DetailState>({
        entry: null,
        incoming: [],
        outgoing: [],
    });
    const [compatibility, setCompatibility] =
        useState<DiscoveryCompatibilityAssessment | null>(null);
    const [isLoading, setIsLoading] = useState(true);
    const [compatibilityLoading, setCompatibilityLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [notFound, setNotFound] = useState(false);
    const [compatibilityError, setCompatibilityError] = useState<string | null>(null);
    const compatibilityRequestId = useRef(0);
    const compatibilityLoadHandle = useRef<ReturnType<typeof window.setTimeout> | null>(null);

    const loadCompatibility = useCallback(() => {
        const requestId = ++compatibilityRequestId.current;

        setCompatibility(null);
        setCompatibilityLoading(true);
        setCompatibilityError(null);

        getDiscoveryCompatibility(itemId)
            .then((nextCompatibility) => {
                if (requestId !== compatibilityRequestId.current) {
                    return;
                }
                setCompatibility(nextCompatibility);
            })
            .catch((requestError: unknown) => {
                if (requestId !== compatibilityRequestId.current) {
                    return;
                }
                console.error(`Unable to load Discovery compatibility for ${itemId}:`, requestError);
                setCompatibilityError(
                    getAtlasErrorMessage(
                        requestError,
                        "Mission Control could not load compatibility for this item.",
                    ),
                );
            })
        .finally(() => {
                if (requestId !== compatibilityRequestId.current) {
                    return;
                }
                setCompatibilityLoading(false);
            });
    }, [itemId]);

    useEffect(() => {
        let cancelled = false;

        Promise.all([getDiscoveryItem(itemId), getDiscoveryRelationships(itemId)])
            .then(([entry, relationships]) => {
                if (cancelled) {
                    return;
                }
                setState({
                    entry,
                    incoming: relationships.incoming,
                    outgoing: relationships.outgoing,
                });
            })
            .catch((requestError: unknown) => {
                if (cancelled) {
                    return;
                }
                console.error(`Unable to load Discovery item ${itemId}:`, requestError);
                const message = getAtlasErrorMessage(
                    requestError,
                    "Mission Control could not load this Discovery item.",
                );
                if (message.toLowerCase().includes("not found")) {
                    setNotFound(true);
                }
                setError(message);
            })
            .finally(() => {
                if (!cancelled) {
                    setIsLoading(false);
                }
            });

        return () => {
            cancelled = true;
        };
    }, [itemId]);

    useEffect(() => {
        const handle = window.setTimeout(() => {
            loadCompatibility();
        }, 0);
        compatibilityLoadHandle.current = handle;

        return () => {
            compatibilityRequestId.current += 1;
            if (compatibilityLoadHandle.current !== null) {
                window.clearTimeout(compatibilityLoadHandle.current);
                compatibilityLoadHandle.current = null;
            }
        };
    }, [itemId, loadCompatibility]);

    if (isLoading) {
        return (
            <main className="mx-auto max-w-5xl p-8">
                <Link
                    to="/discovery"
                    className="text-sm font-medium text-blue-400 transition hover:text-blue-300 focus:outline-none focus:ring-2 focus:ring-blue-300"
                >
                    ← Discovery Center
                </Link>
                <div className="mt-6 rounded-xl border border-slate-800 bg-slate-900/70 p-6 text-sm text-slate-400">
                    Loading Discovery item…
                </div>
            </main>
        );
    }

    if (notFound) {
        return (
            <main className="mx-auto max-w-5xl space-y-6 p-8">
                <Link
                    to="/discovery"
                    className="text-sm font-medium text-blue-400 transition hover:text-blue-300 focus:outline-none focus:ring-2 focus:ring-blue-300"
                >
                    ← Discovery Center
                </Link>
                <section className="rounded-xl border border-slate-800 bg-slate-900/70 p-6">
                    <h1 className="text-2xl font-bold text-white">
                        Discovery item not found
                    </h1>
                    <p className="mt-2 text-sm text-slate-400">
                        Atlas could not find a catalog entry for {itemId}.
                    </p>
                </section>
            </main>
        );
    }

    if (error || state.entry === null) {
        return (
            <main className="mx-auto max-w-5xl space-y-6 p-8">
                <Link
                    to="/discovery"
                    className="text-sm font-medium text-blue-400 transition hover:text-blue-300 focus:outline-none focus:ring-2 focus:ring-blue-300"
                >
                    ← Discovery Center
                </Link>
                <div
                    role="alert"
                    className="rounded-xl border border-red-500/30 bg-red-500/10 p-5"
                >
                    <p className="font-semibold text-red-300">
                        Discovery catalog unavailable
                    </p>
                    <p className="mt-1 text-sm text-red-200/80">
                        {error ?? "Mission Control could not load this Discovery item."}
                    </p>
                </div>
            </main>
        );
    }

    const { entry } = state;
    const { item } = entry;

    return (
        <main className="mx-auto max-w-5xl space-y-8 p-8">
            <header className="space-y-4">
                <Link
                    to="/discovery"
                    className="text-sm font-medium text-blue-400 transition hover:text-blue-300 focus:outline-none focus:ring-2 focus:ring-blue-300"
                >
                    ← Discovery Center
                </Link>
                <div>
                    <p className="text-xs uppercase tracking-[0.3em] text-blue-300">
                        Discovery item
                    </p>
                    <div className="mt-3 flex flex-wrap items-start justify-between gap-4">
                        <div>
                            <h1 className="text-3xl font-bold text-white">
                                {item.name}
                            </h1>
                            <p className="mt-1 text-sm text-slate-500">{item.id}</p>
                        </div>
                        <div className="flex flex-wrap gap-2">
                            <Badge>{formatLabel(item.type)}</Badge>
                            <Badge>{formatLabel(item.status)}</Badge>
                        </div>
                    </div>
                    <p className="mt-4 max-w-3xl text-sm leading-6 text-slate-400">
                        {item.description}
                    </p>
                    <p className="mt-3 text-xs text-slate-500">
                        Read-only catalog information. This entry does not imply
                        compatibility, support, installability, or authorization to
                        execute changes.
                    </p>
                </div>
            </header>

            <section className="grid gap-4 lg:grid-cols-2">
                <InfoPanel title="Capabilities">
                    <ChipList values={item.capabilities} empty="No capabilities listed." />
                </InfoPanel>
                <InfoPanel title="Tags">
                    <ChipList values={item.tags} empty="No tags listed." />
                </InfoPanel>
            </section>

            <CompatibilityPanel
                compatibility={compatibility}
                compatibilityLoading={compatibilityLoading}
                compatibilityError={compatibilityError}
                targetItemId={itemId}
                onRetry={loadCompatibility}
            />

            <RequirementsPanel requirements={item.requirements} />

            <section className="grid gap-4 lg:grid-cols-2">
                <RelationshipsPanel
                    title="Outgoing relationships"
                    empty="No outgoing relationships."
                    relationships={state.outgoing}
                />
                <RelationshipsPanel
                    title="Incoming relationships"
                    empty="No incoming relationships."
                    relationships={state.incoming}
                />
            </section>

            <section className="grid gap-4 lg:grid-cols-2">
                <ProvenancePanel entry={entry} />
                <ApprovedMetadataPanel entry={entry} />
            </section>
        </main>
    );
}

function CompatibilityPanel({
    compatibility,
    compatibilityLoading,
    compatibilityError,
    targetItemId,
    onRetry,
}: {
    compatibility: DiscoveryCompatibilityAssessment | null;
    compatibilityLoading: boolean;
    compatibilityError: string | null;
    targetItemId: string;
    onRetry: () => void;
}) {
    const findingsBySeverity = compatibility
        ? compatibility.findings.reduce(
              (groups, finding) => {
                  const key = finding.severity;
                  const existing = groups[key] ?? [];
                  groups[key] = [...existing, finding];
                  return groups;
              },
              {} as Record<string, typeof compatibility.findings>,
          )
        : {};

    const evidenceById = new Map(
        compatibility?.evidence.map((evidence) => [evidence.id, evidence]) ?? [],
    );

    if (compatibilityLoading) {
        return (
            <InfoPanel title="Compatibility assessment">
                <p className="text-sm text-slate-400">Loading compatibility assessment…</p>
            </InfoPanel>
        );
    }

    if (compatibilityError) {
        return (
            <InfoPanel title="Compatibility assessment">
                <div className="rounded-lg border border-amber-500/30 bg-amber-500/10 p-4 text-sm text-amber-200">
                    <p className="font-semibold">Compatibility unavailable</p>
                    <p className="mt-1 text-sm text-amber-200/90">{compatibilityError}</p>
                    <button
                        type="button"
                        className="mt-3 rounded-lg border border-amber-400/50 bg-amber-500/10 px-3 py-1.5 text-xs font-semibold text-amber-200 transition hover:border-amber-300 hover:text-amber-100"
                        onClick={onRetry}
                    >
                        Retry compatibility check
                    </button>
                </div>
            </InfoPanel>
        );
    }

    if (!compatibility) {
        return (
            <InfoPanel title="Compatibility assessment">
                <p className="text-sm text-slate-400">Compatibility assessment not available.</p>
            </InfoPanel>
        );
    }

    return (
        <section className="grid gap-4 lg:grid-cols-2">
            <InfoPanel title="Compatibility status">
                <dl className="grid gap-2 text-sm">
                    <KeyValue label="Item" value={compatibility.item_id} />
                    <KeyValue label="Target" value={compatibility.target_type} />
                    <KeyValue label="Target ID" value={compatibility.target_id} />
                    <KeyValue label="Status" value={formatCompatibilityStatus(compatibility.status)} />
                    <KeyValue label="Checked at" value={compatibility.checked_at} />
                    <KeyValue label="Findings" value={String(compatibility.findings.length)} />
                    <KeyValue label="Evidence" value={String(compatibility.evidence.length)} />
                    <KeyValue
                        label="Unknown facts"
                        value={compatibility.unknown_facts.length === 0 ? "None" : `${compatibility.unknown_facts.length}`}
                    />
                </dl>
            </InfoPanel>

            <InfoPanel title="Compatibility details">
                <div className="space-y-4">
                    {compatibility.findings.length === 0 ? (
                        <p className="text-sm text-slate-500">No findings were reported.</p>
                    ) : (
                        Object.entries(findingsBySeverity).map(([severity, findings]) => (
                            <div key={`${targetItemId}-${severity}`}>
                                <p className="text-xs uppercase tracking-wider text-slate-500">
                                    {formatLabel(`findings_${severity}`)}
                                </p>
                                <div className="mt-2 space-y-3">
                                    {findings.map((finding) => (
                                        <article
                                            key={finding.id}
                                            className="rounded-lg border border-slate-800 bg-slate-950 p-3"
                                        >
                                            <div className="flex flex-wrap gap-2 text-xs uppercase tracking-wide text-slate-400">
                                                <span className="rounded-full border border-slate-700 px-2 py-0.5 text-slate-300">
                                                    {finding.severity}
                                                </span>
                                                <span className="rounded-full border border-slate-700 px-2 py-0.5 text-slate-300">
                                                    {formatLabel(finding.check_type)}
                                                </span>
                                                <span className="rounded-full border border-slate-700 px-2 py-0.5 text-slate-300">
                                                    {finding.status}
                                                </span>
                                            </div>
                                            <p className="mt-2 text-sm text-slate-300">{finding.message}</p>
                                            <p className="mt-1 text-xs text-slate-500">Code: {finding.id}</p>
                                            <p className="mt-1 text-xs text-slate-500">Subject: {finding.subject}</p>
                                            {finding.evidence_ids.length > 0 ? (
                                                <ul className="mt-3 space-y-2 text-xs text-slate-400">
                                                    {finding.evidence_ids.map((evidenceId) => {
                                                        const evidence = evidenceById.get(evidenceId);
                                                        return (
                                                            <li
                                                                key={`${finding.id}-${evidenceId}`}
                                                                className="rounded-md border border-slate-800 bg-slate-900 p-2"
                                                            >
                                                                {evidence ? (
                                                                    <div>
                                                                        <p>Evidence {evidence.id}</p>
                                                                        <p>Source: {evidence.source}</p>
                                                                        <p>Message: {evidence.message}</p>
                                                                    </div>
                                                                ) : (
                                                                    <p>Evidence {evidenceId}</p>
                                                                )}
                                                            </li>
                                                        );
                                                    })}
                                                </ul>
                                            ) : (
                                                <p className="mt-2 text-xs text-slate-500">
                                                    No evidence IDs were attached.
                                                </p>
                                            )}
                                        </article>
                                    ))}
                                </div>
                            </div>
                        ))
                    )}

                    {compatibility.unknown_facts.length > 0 && (
                        <div>
                            <p className="text-xs uppercase tracking-wider text-slate-500">Unknown facts</p>
                            <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-slate-400">
                                {compatibility.unknown_facts.map((item) => (
                                    <li key={item}>{item}</li>
                                ))}
                            </ul>
                        </div>
                    )}
                </div>
            </InfoPanel>
        </section>
    );
}

function RequirementsPanel({ requirements }: { requirements: DiscoveryRequirements }) {
    const resourceRequirements = [
        requirements.resources.cpu_cores_min
            ? `CPU cores: ${requirements.resources.cpu_cores_min}`
            : null,
        requirements.resources.memory_mb_min
            ? `Memory: ${requirements.resources.memory_mb_min} MB`
            : null,
        requirements.resources.storage_gb_min
            ? `Storage: ${requirements.resources.storage_gb_min} GB`
            : null,
        requirements.resources.gpu_required ? "GPU required" : null,
        requirements.resources.gpu_memory_gb_min
            ? `GPU memory: ${requirements.resources.gpu_memory_gb_min} GB`
            : null,
    ].filter(Boolean) as string[];
    const platformRequirements = [
        ...requirements.platform.architectures.map((item) => `Architecture: ${item}`),
        ...requirements.platform.operating_systems.map((item) => `OS: ${item}`),
        ...requirements.platform.runtimes.map((item) => `Runtime: ${item}`),
        ...requirements.platform.devices.map((item) => `Device: ${item}`),
    ];
    const capabilityRequirements = requirements.capabilities.map((item) => item.id);
    const networkRequirements = [
        ...requirements.network.ports.map(
            (port) =>
                `${port.protocol.toUpperCase()} ${port.port} ${port.direction}${
                    port.required ? " required" : " optional"
                }${port.description ? `: ${port.description}` : ""}`,
        ),
        requirements.network.requires_internet === true ? "Internet access" : null,
        requirements.network.requires_lan === true ? "LAN access" : null,
        requirements.network.notes ?? null,
    ].filter(Boolean) as string[];

    const hasRequirements =
        capabilityRequirements.length > 0 ||
        resourceRequirements.length > 0 ||
        platformRequirements.length > 0 ||
        networkRequirements.length > 0;

    if (!hasRequirements) {
        return null;
    }

    return (
        <InfoPanel title="Requirements">
            <RequirementGroup title="Capabilities" values={capabilityRequirements} />
            <RequirementGroup title="Resources" values={resourceRequirements} />
            <RequirementGroup title="Platform" values={platformRequirements} />
            <RequirementGroup title="Network" values={networkRequirements} />
        </InfoPanel>
    );
}

function RequirementGroup({ title, values }: { title: string; values: string[] }) {
    if (values.length === 0) {
        return null;
    }

    return (
        <div className="mt-4 first:mt-0">
            <p className="text-xs uppercase tracking-wider text-slate-500">{title}</p>
            <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-slate-300">
                {values.map((value) => (
                    <li key={value}>{value}</li>
                ))}
            </ul>
        </div>
    );
}

function RelationshipsPanel({
    title,
    empty,
    relationships,
}: {
    title: string;
    empty: string;
    relationships: DiscoveryRelationshipReference[];
}) {
    return (
        <InfoPanel title={title}>
            {relationships.length === 0 ? (
                <p className="text-sm text-slate-500">{empty}</p>
            ) : (
                <ul className="space-y-3">
                    {relationships.map((reference) => (
                        <li
                            key={`${reference.source_item_id}-${reference.relationship.type}-${reference.target}`}
                            className="rounded-lg border border-slate-800 bg-slate-950 p-3"
                        >
                            <div className="flex flex-wrap items-center gap-2 text-sm">
                                <span className="font-medium text-slate-200">
                                    {formatLabel(reference.relationship.type)}
                                </span>
                                <span className="text-slate-600">→</span>
                                {reference.resolved_target_item_id ? (
                                    <Link
                                        to={`/discovery/items/${encodeURIComponent(
                                            reference.resolved_target_item_id,
                                        )}`}
                                        className="text-blue-300 hover:text-blue-200 focus:outline-none focus:ring-2 focus:ring-blue-300"
                                    >
                                        {reference.target}
                                    </Link>
                                ) : (
                                    <span className="text-slate-300">{reference.target}</span>
                                )}
                                <span className="rounded-full border border-slate-700 px-2 py-0.5 text-xs text-slate-300">
                                    {reference.relationship.required ? "Required" : "Optional"}
                                </span>
                                <span className="rounded-full border border-slate-700 px-2 py-0.5 text-xs text-slate-300">
                                    {reference.resolved ? "Resolved" : "Unresolved"}
                                </span>
                            </div>
                            {reference.relationship.description && (
                                <p className="mt-2 text-sm text-slate-500">
                                    {reference.relationship.description}
                                </p>
                            )}
                        </li>
                    ))}
                </ul>
            )}
        </InfoPanel>
    );
}

function ProvenancePanel({ entry }: { entry: DiscoveryCatalogEntry }) {
    return (
        <InfoPanel title="Provenance">
            <dl className="space-y-2 text-sm">
                <KeyValue label="Source type" value={formatLabel(entry.provenance.source_type)} />
                <KeyValue label="Source" value={entry.provenance.source} />
                <KeyValue label="Trust" value={formatLabel(entry.provenance.trust_level)} />
                {entry.provenance.entry_id && (
                    <KeyValue label="Entry ID" value={entry.provenance.entry_id} />
                )}
                <KeyValue label="Schema" value={`v${entry.schema_version}`} />
            </dl>
        </InfoPanel>
    );
}

function ApprovedMetadataPanel({ entry }: { entry: DiscoveryCatalogEntry }) {
    const notes = entry.metadata.catalog_notes ?? entry.item.metadata.catalog_notes ?? [];
    const reviewed = entry.metadata.reviewed_for_d5 ?? entry.item.metadata.reviewed_for_d5;

    return (
        <InfoPanel title="Catalog review">
            {reviewed !== undefined && (
                <p className="text-sm text-slate-300">
                    Reviewed for D5: {reviewed ? "Yes" : "No"}
                </p>
            )}
            {notes.length > 0 ? (
                <ul className="mt-3 list-disc space-y-1 pl-5 text-sm text-slate-400">
                    {notes.map((note) => (
                        <li key={note}>{note}</li>
                    ))}
                </ul>
            ) : (
                <p className="text-sm text-slate-500">No catalog notes listed.</p>
            )}
        </InfoPanel>
    );
}

function InfoPanel({ title, children }: { title: string; children: React.ReactNode }) {
    return (
        <section className="rounded-xl border border-slate-800 bg-slate-900/70 p-5">
            <h2 className="text-lg font-semibold text-white">{title}</h2>
            <div className="mt-4">{children}</div>
        </section>
    );
}

function ChipList({ values, empty }: { values: string[]; empty: string }) {
    if (values.length === 0) {
        return <p className="text-sm text-slate-500">{empty}</p>;
    }

    return (
        <div className="flex flex-wrap gap-2">
            {values.map((value) => (
                <span
                    key={value}
                    className="rounded-full border border-slate-700 bg-slate-950 px-2.5 py-1 text-xs text-slate-300"
                >
                    {value}
                </span>
            ))}
        </div>
    );
}

function Badge({ children }: { children: string }) {
    return (
        <span className="rounded-full border border-blue-400/30 bg-blue-400/10 px-2.5 py-1 text-xs font-medium text-blue-200">
            {children}
        </span>
    );
}

function KeyValue({ label, value }: { label: string; value: string }) {
    return (
        <div className="grid gap-1 sm:grid-cols-[8rem_1fr]">
            <dt className="text-slate-500">{label}</dt>
            <dd className="text-slate-300">{value}</dd>
        </div>
    );
}

function formatLabel(value: string): string {
    return value
        .split("_")
        .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
        .join(" ");
}

function formatCompatibilityStatus(status: string): string {
    return formatLabel(status);
}
