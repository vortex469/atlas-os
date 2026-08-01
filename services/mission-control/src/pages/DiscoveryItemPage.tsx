import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { getAtlasErrorMessage } from "../api/atlas";
import { getDiscoveryItem, getDiscoveryRelationships } from "../api/discovery";
import type {
    DiscoveryCatalogEntry,
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
    const [isLoading, setIsLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [notFound, setNotFound] = useState(false);

    useEffect(() => {
        let cancelled = false;

        Promise.all([
            getDiscoveryItem(itemId),
            getDiscoveryRelationships(itemId),
        ])
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
