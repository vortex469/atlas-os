import {
    useCallback,
    useEffect,
    useMemo,
    useState,
} from "react";

import {
    getAtlasErrorMessage,
} from "../api/atlas";
import {
    getProviderResources,
    refreshProviderResources,
    updateProviderResourceExpectation,
} from "../api/resources";
import type { Provider } from "../types/provider";
import type {
    ProviderResource,
    ProviderResourceCollection,
} from "../types/resources";
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
    const hasResourceCapability = provider.capabilities.includes("resources");
    const [collection, setCollection] =
        useState<ProviderResourceCollection | null>(null);
    const [isLoading, setIsLoading] = useState(hasResourceCapability);
    const [isRefreshing, setIsRefreshing] = useState(false);
    const [updatingResourceId, setUpdatingResourceId] = useState<
        string | null
    >(null);
    const [error, setError] = useState<string | null>(null);
    const metadataColumns = useMemo(
        () => metadataColumnsByProvider[provider.id] ?? [],
        [provider.id],
    );

    const loadResources = useCallback(async () => {
        if (!hasResourceCapability) {
            return;
        }

        setIsLoading(true);
        setError(null);

        try {
            const resources = await getProviderResources(provider.id);
            setCollection(resources);
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
        } finally {
            setIsLoading(false);
        }
    }, [hasResourceCapability, provider.id, provider.name]);

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

    if (!hasResourceCapability) {
        return null;
    }

    async function refreshInventory(): Promise<void> {
        setIsRefreshing(true);
        setError(null);

        try {
            const resources = await refreshProviderResources(provider.id);
            setCollection(resources);
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

    async function updateExpectation(
        resource: ProviderResource,
        expectation: string,
    ): Promise<void> {
        if (expectation === resource.expectation.value) {
            return;
        }

        const option = resource.expectation.allowed_values.find(
            (candidate) => candidate.value === expectation,
        );
        const label = option?.label ?? expectation;
        const confirmed = window.confirm(
            `Update Atlas expectation for ${resource.display_name} to ${label}?`,
        );

        if (!confirmed) {
            return;
        }

        setUpdatingResourceId(resource.resource_id);
        setError(null);

        try {
            const result = await updateProviderResourceExpectation(
                provider.id,
                resource.resource_id,
                expectation,
                true,
            );

            setCollection((current) => {
                if (current === null) {
                    return current;
                }

                return {
                    ...current,
                    resources: current.resources.map((candidate) =>
                        candidate.resource_id === resource.resource_id
                            ? {
                                  ...candidate,
                                  expectation: result.expectation,
                                  configured:
                                      result.expectation.state !==
                                      "needs_review",
                                  needs_review:
                                      result.expectation.state ===
                                      "needs_review",
                              }
                            : candidate,
                    ),
                };
            });
        } catch (requestError) {
            console.error(
                `Unable to update resource ${resource.resource_id} for ${provider.id}:`,
                requestError,
            );
            setError(
                getAtlasErrorMessage(
                    requestError,
                    "Atlas Core could not update the resource expectation.",
                ),
            );
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
                                        key={resource.resource_id}
                                        resource={resource}
                                        metadataColumns={metadataColumns}
                                        isUpdating={
                                            updatingResourceId ===
                                            resource.resource_id
                                        }
                                        onUpdate={updateExpectation}
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
    metadataColumns,
    isUpdating,
    onUpdate,
}: {
    resource: ProviderResource;
    metadataColumns: MetadataColumn[];
    isUpdating: boolean;
    onUpdate: (
        resource: ProviderResource,
        expectation: string,
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
                <label className="sr-only" htmlFor={`expectation-${resource.resource_id}`}>
                    Atlas Expectation for {resource.display_name}
                </label>
                <select
                    id={`expectation-${resource.resource_id}`}
                    value={resource.expectation.value ?? ""}
                    disabled={isUpdating}
                    onChange={(event) =>
                        void onUpdate(resource, event.target.value)
                    }
                    className="rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-100 disabled:cursor-not-allowed disabled:opacity-50"
                >
                    {resource.expectation.value === null && (
                        <option value="">Needs Review</option>
                    )}
                    {resource.expectation.allowed_values.map((option) => (
                        <option key={option.value} value={option.value}>
                            {option.label}
                        </option>
                    ))}
                </select>
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
