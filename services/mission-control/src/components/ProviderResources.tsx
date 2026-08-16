import {
    useCallback,
    useEffect,
    useMemo,
    useState,
} from "react";
import { isAxiosError } from "axios";

import {
    getAtlasErrorMessage,
} from "../api/atlas";
import {
    getProviderResources,
    refreshProviderResources,
} from "../api/resources";
import {
    getAuthenticatedProviderManagement,
    putProviderMonitoringIntent,
} from "../api/providerManagement";
import { useOperatorSession } from "../hooks/operatorSessionContext";
import type { Provider } from "../types/provider";
import type {
    ProviderResource,
    ProviderResourceCollection,
} from "../types/resources";
import type {
    ManagedProviderResourceV3,
    ProviderManagementV3,
    ProviderMonitoringExpectation,
} from "../types/providerManagement";
import { ProviderIntentEditor } from "./ProviderIntentEditor";
import { SectionHeader } from "./SectionHeader";

type ProviderResourcesProps = {
    provider: Provider;
};

type MetadataColumn = {
    key: string;
    label: string;
    render: (resource: ProviderResource) => string;
};

const metadataColumnsByProvider: Record<string, MetadataColumn[]> = {
    proxmox: [
        {
            key: "vmid",
            label: "VMID",
            render: (resource) => formatMetadata(resource.metadata.vmid),
        },
        {
            key: "node",
            label: "Node",
            render: (resource) => formatMetadata(resource.metadata.node),
        },
    ],
};

export function ProviderResources({ provider }: ProviderResourcesProps) {
    const session = useOperatorSession();
    const hasResourceCapability = provider.capabilities.includes("resources");
    const [collection, setCollection] =
        useState<ProviderResourceCollection | null>(null);
    const [management, setManagement] = useState<ProviderManagementV3 | null>(null);
    const [isLoading, setIsLoading] = useState(hasResourceCapability);
    const [isRefreshing, setIsRefreshing] = useState(false);
    const [updatingResourceId, setUpdatingResourceId] = useState<
        string | null
    >(null);
    const [error, setError] = useState<string | null>(null);
    const [decisionRevision, setDecisionRevision] = useState(0);
    const metadataColumns = useMemo(
        () => metadataColumnsByProvider[provider.id] ?? [],
        [provider.id],
    );

    const loadResources = useCallback(async (preserveError = false) => {
        if (!hasResourceCapability) {
            return;
        }

        setIsLoading(true);
        if (!preserveError) setError(null);

        try {
            const resources = await getProviderResources(provider.id);
            setCollection(resources);
            if (session.authenticated) {
                setManagement(
                    await getAuthenticatedProviderManagement(provider.id),
                );
            } else {
                setManagement(null);
            }
            return true;
        } catch (requestError) {
            console.error(
                `Unable to load resources for ${provider.id}:`,
                requestError,
            );
            setError(
                getAtlasErrorMessage(
                    requestError,
                    `Mission Control could not load resources for ${provider.name}.`,
                ),
            );
            return false;
        } finally {
            setIsLoading(false);
        }
    }, [hasResourceCapability, provider.id, provider.name, session.authenticated]);

    useEffect(() => {
        if (!hasResourceCapability) {
            return;
        }

        let cancelled = false;

        getProviderResources(provider.id)
            .then((resources) => {
                if (cancelled) {
                    return;
                }
                setCollection(resources);
            })
            .catch((requestError: unknown) => {
                if (cancelled) {
                    return;
                }
                console.error(
                    `Unable to load resources for ${provider.id}:`,
                    requestError,
                );
                setError(
                    getAtlasErrorMessage(
                        requestError,
                        `Mission Control could not load resources for ${provider.name}.`,
                    ),
                );
            })
            .finally(() => {
                if (!cancelled) {
                    setIsLoading(false);
                }
            });

        return () => {
            cancelled = true;
        };
    }, [hasResourceCapability, provider.id, provider.name]);

    useEffect(() => {
        if (!hasResourceCapability || !session.authenticated) {
            return;
        }
        let cancelled = false;
        getAuthenticatedProviderManagement(provider.id)
            .then((descriptor) => {
                if (!cancelled) setManagement(descriptor);
            })
            .catch((requestError: unknown) => {
                if (cancelled) return;
                if (isAxiosError(requestError) && requestError.response?.status === 401) {
                    session.invalidate();
                }
                setManagement(null);
            });
        return () => { cancelled = true; };
    }, [hasResourceCapability, provider.id, session]);

    if (!hasResourceCapability) {
        return null;
    }

    async function refreshInventory(): Promise<void> {
        setIsRefreshing(true);
        setError(null);

        try {
            const resources = await refreshProviderResources(provider.id);
            setCollection(resources);
            if (session.authenticated) {
                setManagement(
                    await getAuthenticatedProviderManagement(provider.id),
                );
            }
        } catch (requestError) {
            console.error(
                `Unable to refresh resources for ${provider.id}:`,
                requestError,
            );
            setError(
                getAtlasErrorMessage(
                    requestError,
                    "Atlas Core could not refresh provider inventory.",
                ),
            );
        } finally {
            setIsRefreshing(false);
        }
    }

    async function saveProviderIntent(
        resource: ManagedProviderResourceV3,
        expectation: ProviderMonitoringExpectation,
        acknowledgeSuppression: boolean,
    ): Promise<void> {
        if (!resource.management_fingerprint || !session.csrfToken) {
            return;
        }
        setUpdatingResourceId(resource.resource_id);
        setError(null);
        try {
            await putProviderMonitoringIntent(
                provider.id,
                resource.resource_type,
                resource.resource_id,
                {
                    request_id: `provider-intent-mutation-${crypto.randomUUID().replaceAll("-", "")}`,
                    expected_management_fingerprint: resource.management_fingerprint,
                    expectation,
                    expected_record_version: resource.replacement_detected
                        ? 0
                        : resource.record_version ?? 0,
                    acknowledge_monitoring_suppression: acknowledgeSuppression,
                },
                session.csrfToken,
            );
            setDecisionRevision((value) => value + 1);
            const reloaded = await loadResources();
            if (!reloaded) {
                setError(
                    "Provider Intent was saved, but refreshed server state could not be loaded.",
                );
            }
        } catch (requestError) {
            const status = isAxiosError(requestError)
                ? requestError.response?.status
                : undefined;
            const detail = isAxiosError<{ detail?: string }>(requestError)
                ? requestError.response?.data?.detail
                : undefined;
            if (status === 401) {
                session.invalidate();
                setError("Operator session expired. Sign in again.");
            } else if (status === 403) {
                setError("Your operator session does not permit Provider Intent updates.");
            } else if (status === 409 && detail === "cas_conflict") {
                setError("Provider Intent changed. Review the current state and make a fresh decision.");
                setDecisionRevision((value) => value + 1);
                await loadResources(true);
            } else if (status === 409 && detail === "fingerprint_mismatch") {
                setError("The resource identity changed. Review the replacement before saving.");
                setDecisionRevision((value) => value + 1);
                await loadResources(true);
            } else if (status === 409 && detail === "request_conflict") {
                setError("This save request is stale. Start a new Save action.");
            } else if (status === 429) {
                setError("Provider Intent saves are rate limited. Wait before trying again.");
            } else if (status === 422) {
                setError("The Provider Intent request is invalid. Review the current state and choose again.");
            } else if (status === 503) {
                setError("Provider Intent editing is temporarily unavailable or awaiting migration.");
            } else {
                setError("Atlas Core could not save the monitoring expectation.");
            }
        } finally {
            setUpdatingResourceId(null);
        }
    }

    const refreshedAt = collection
        ? new Date(collection.refreshed_at).toLocaleString()
        : "Not refreshed yet";

    return (
        <section className="rounded-2xl border border-slate-800 bg-slate-950/70 p-6 shadow-lg shadow-slate-950/30">
            <div className="flex flex-wrap items-start justify-between gap-4">
                <div>
                    <SectionHeader
                        title="Resources"
                        description="Review discovered resources and set Atlas monitoring intent."
                    />
                    <p className="mt-2 text-xs text-slate-500">
                        Last refreshed: {refreshedAt}
                    </p>
                </div>

                <button
                    type="button"
                    onClick={() => void refreshInventory()}
                    disabled={isRefreshing}
                    className="rounded-lg border border-slate-700 bg-slate-900 px-4 py-2 text-sm font-medium text-slate-300 transition hover:border-slate-600 hover:text-white disabled:cursor-not-allowed disabled:opacity-50"
                >
                    {isRefreshing ? "Refreshing..." : "Refresh Inventory"}
                </button>
            </div>

            {error && (
                <div
                    role="alert"
                    className="mt-4 rounded-lg border border-red-500/30 bg-red-500/10 p-4 text-sm text-red-200"
                >
                    {error}
                </div>
            )}

            {isLoading && collection === null ? (
                <p className="mt-6 text-sm text-slate-400">
                    Loading provider resources...
                </p>
            ) : collection === null ? (
                <button
                    type="button"
                    onClick={() => void loadResources()}
                    className="mt-6 rounded-lg border border-slate-700 px-4 py-2 text-sm text-slate-300 hover:text-white"
                >
                    Retry loading resources
                </button>
            ) : (
                <>
                    <ResourceSummary collection={collection} />

                    <div className="mt-6 overflow-x-auto">
                        <table className="min-w-full divide-y divide-slate-800 text-left text-sm">
                            <thead className="text-xs uppercase tracking-wider text-slate-500">
                                <tr>
                                    <th className="px-3 py-3">Resource</th>
                                    <th className="px-3 py-3">Type</th>
                                    {metadataColumns.map((column) => (
                                        <th
                                            key={column.key}
                                            className="px-3 py-3"
                                        >
                                            {column.label}
                                        </th>
                                    ))}
                                    <th className="px-3 py-3">
                                        Current State
                                    </th>
                                    <th className="px-3 py-3">
                                        Atlas Expectation
                                    </th>
                                </tr>
                            </thead>
                            <tbody className="divide-y divide-slate-900">
                                {collection.resources.map((resource) => (
                                    <ResourceRow
                                        key={`${resource.resource_type}:${resource.resource_id}`}
                                        resource={resource}
                                        managementResource={(session.authenticated ? management : null)?.resources.find(
                                            (candidate) =>
                                                candidate.resource_type === resource.resource_type
                                                && candidate.resource_id === resource.resource_id,
                                        ) ?? null}
                                        metadataColumns={metadataColumns}
                                        isUpdating={
                                            updatingResourceId ===
                                            resource.resource_id
                                        }
                                        decisionRevision={decisionRevision}
                                        onSave={saveProviderIntent}
                                    />
                                ))}
                            </tbody>
                        </table>
                    </div>
                </>
            )}
        </section>
    );
}

function ResourceSummary({
    collection,
}: {
    collection: ProviderResourceCollection;
}) {
    const items = [
        ["Total", collection.summary.total],
        ["Configured", collection.summary.configured],
        ["Needs Review", collection.summary.needs_review],
        ["Missing", collection.summary.missing],
        ["Ignored", collection.summary.ignored],
    ];

    return (
        <div className="mt-6 grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
            {items.map(([label, value]) => (
                <div
                    key={label}
                    className="rounded-xl border border-slate-800 bg-slate-900/70 p-4"
                >
                    <p className="text-xs uppercase tracking-wider text-slate-500">
                        {label}
                    </p>
                    <p className="mt-2 text-2xl font-semibold text-slate-100">
                        {value}
                    </p>
                </div>
            ))}
        </div>
    );
}

function ResourceRow({
    resource,
    managementResource,
    metadataColumns,
    isUpdating,
    decisionRevision,
    onSave,
}: {
    resource: ProviderResource;
    managementResource: ManagedProviderResourceV3 | null;
    metadataColumns: MetadataColumn[];
    isUpdating: boolean;
    decisionRevision: number;
    onSave: (
        resource: ManagedProviderResourceV3,
        expectation: ProviderMonitoringExpectation,
        acknowledgeSuppression: boolean,
    ) => Promise<void>;
}) {
    const rowClassName = resource.needs_review
        ? "bg-amber-500/10"
        : resource.missing
          ? "bg-red-500/10"
          : "";

    return (
        <tr className={rowClassName} data-testid={`resource-row-${resource.resource_id}`}>
            <td className="px-3 py-4">
                <div className="font-medium text-slate-100">
                    {resource.display_name}
                </div>
                <div className="mt-1 flex flex-wrap gap-2 text-xs">
                    {resource.needs_review && (
                        <span className="rounded-full border border-amber-500/30 bg-amber-500/10 px-2 py-0.5 text-amber-200">
                            Needs Review
                        </span>
                    )}
                    {resource.missing && (
                        <span className="rounded-full border border-red-500/30 bg-red-500/10 px-2 py-0.5 text-red-200">
                            Missing
                        </span>
                    )}
                    {resource.expectation.state === "ignored" && (
                        <span className="rounded-full border border-slate-600 bg-slate-800 px-2 py-0.5 text-slate-300">
                            Ignored
                        </span>
                    )}
                </div>
            </td>
            <td className="px-3 py-4 text-slate-300">
                {resource.resource_type}
            </td>
            {metadataColumns.map((column) => (
                <td
                    key={column.key}
                    className="px-3 py-4 text-slate-300"
                >
                    {column.render(resource)}
                </td>
            ))}
            <td className="px-3 py-4 text-slate-300">
                {resource.current_state}
            </td>
            <td className="px-3 py-4">
                {managementResource ? (
                    <ProviderIntentEditor
                        key={`${managementResource.management_fingerprint}:${managementResource.record_version}:${decisionRevision}`}
                        resource={managementResource}
                        saving={isUpdating}
                        onSave={(expectation, acknowledgeSuppression) =>
                            onSave(
                                managementResource,
                                expectation,
                                acknowledgeSuppression,
                            )
                        }
                    />
                ) : (
                    <p className="text-xs text-slate-500">
                        {resource.expectation.label} — sign in to view Provider Intent edit readiness.
                    </p>
                )}
            </td>
        </tr>
    );
}

function formatMetadata(value: unknown): string {
    if (typeof value === "string" || typeof value === "number") {
        return String(value);
    }

    return "—";
}
