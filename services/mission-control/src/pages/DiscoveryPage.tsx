import { useCallback, useEffect, useState } from "react";
import type { FormEvent } from "react";
import { Link } from "react-router-dom";

import { getAtlasErrorMessage } from "../api/atlas";
import {
    getDiscoveryMetadata,
    listDiscoveryItems,
    searchDiscoveryItems,
} from "../api/discovery";
import type {
    DiscoveryCatalogEntry,
    DiscoveryItemStatus,
    DiscoveryItemType,
    DiscoveryListQuery,
    DiscoveryMetadata,
} from "../types/discovery";

const PAGE_SIZE = 25;

const itemTypeOptions: { label: string; value: DiscoveryItemType }[] = [
    { label: "Application", value: "application" },
    { label: "Service", value: "service" },
    { label: "Container Image", value: "container_image" },
    { label: "AI Model", value: "ai_model" },
    { label: "Integration", value: "integration" },
    { label: "Hardware Device", value: "hardware_device" },
    { label: "Deployment Method", value: "deployment_method" },
];

const statusOptions: { label: string; value: DiscoveryItemStatus }[] = [
    { label: "Active", value: "active" },
    { label: "Experimental", value: "experimental" },
    { label: "Deprecated", value: "deprecated" },
    { label: "Unknown", value: "unknown" },
];

type DiscoveryResult = {
    entries: DiscoveryCatalogEntry[];
    total: number;
    offset: number;
    hasMore: boolean;
};

type FilterState = {
    query: string;
    type: "" | DiscoveryItemType;
    status: "" | DiscoveryItemStatus;
    tag: string;
    capability: string;
};

const emptyFilters: FilterState = {
    query: "",
    type: "",
    status: "",
    tag: "",
    capability: "",
};

export function DiscoveryPage() {
    const [metadata, setMetadata] = useState<DiscoveryMetadata | null>(null);
    const [filters, setFilters] = useState<FilterState>(emptyFilters);
    const [submittedFilters, setSubmittedFilters] =
        useState<FilterState>(emptyFilters);
    const [result, setResult] = useState<DiscoveryResult>({
        entries: [],
        total: 0,
        offset: 0,
        hasMore: false,
    });
    const [isLoading, setIsLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    const loadCatalog = useCallback(
        async (nextFilters: FilterState, offset: number) => {
            setIsLoading(true);
            setError(null);

            try {
                const [nextMetadata, page] = await Promise.all([
                    getDiscoveryMetadata(),
                    fetchDiscoveryPage(nextFilters, offset),
                ]);

                setMetadata(nextMetadata);
                setResult({
                    entries: page.entries,
                    total: page.total,
                    offset: page.offset,
                    hasMore: page.has_more,
                });
            } catch (requestError) {
                console.error("Unable to load Discovery catalog:", requestError);
                setError(
                    getAtlasErrorMessage(
                        requestError,
                        "Mission Control could not load Discovery Center.",
                    ),
                );
            } finally {
                setIsLoading(false);
            }
        },
        [],
    );

    useEffect(() => {
        let cancelled = false;

        Promise.all([
            getDiscoveryMetadata(),
            fetchDiscoveryPage(emptyFilters, 0),
        ])
            .then(([nextMetadata, page]) => {
                if (cancelled) {
                    return;
                }
                setMetadata(nextMetadata);
                setResult({
                    entries: page.entries,
                    total: page.total,
                    offset: page.offset,
                    hasMore: page.has_more,
                });
            })
            .catch((requestError: unknown) => {
                if (cancelled) {
                    return;
                }
                console.error("Unable to load Discovery catalog:", requestError);
                setError(
                    getAtlasErrorMessage(
                        requestError,
                        "Mission Control could not load Discovery Center.",
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
    }, []);

    const isSearchMode = submittedFilters.query.trim().length > 0;
    function submitFilters(event: FormEvent<HTMLFormElement>) {
        event.preventDefault();
        const normalized = normalizeFilters(filters);
        setSubmittedFilters(normalized);
        void loadCatalog(normalized, 0);
    }

    function clearFilters() {
        setFilters(emptyFilters);
        setSubmittedFilters(emptyFilters);
        void loadCatalog(emptyFilters, 0);
    }

    function goToPreviousPage() {
        const nextOffset = Math.max(0, result.offset - PAGE_SIZE);
        void loadCatalog(submittedFilters, nextOffset);
    }

    function goToNextPage() {
        void loadCatalog(submittedFilters, result.offset + PAGE_SIZE);
    }

    return (
        <main className="mx-auto max-w-7xl space-y-8 p-8">
            <header className="space-y-4">
                <div>
                    <p className="text-xs uppercase tracking-[0.3em] text-blue-300">
                        Discovery Center
                    </p>
                    <h1 className="mt-3 text-3xl font-bold text-white">
                        Provider-neutral catalog
                    </h1>
                    <p className="mt-3 max-w-3xl text-sm leading-6 text-slate-400">
                        Browse Atlas&apos;s read-only catalog of applications, services,
                        integrations, hardware devices, AI models, and deployment
                        methods. Catalog inclusion does not mean compatibility,
                        support, installability, or approval to execute changes.
                    </p>
                </div>

                <DiscoveryStatus metadata={metadata} isLoading={isLoading} />
            </header>

            {error && (
                <div
                    role="alert"
                    className="rounded-xl border border-red-500/30 bg-red-500/10 p-5"
                >
                    <p className="font-semibold text-red-300">
                        Discovery catalog unavailable
                    </p>
                    <p className="mt-1 text-sm text-red-200/80">{error}</p>
                </div>
            )}

            <section className="rounded-xl border border-slate-800 bg-slate-900/70 p-5">
                <form
                    className="grid gap-4 lg:grid-cols-[2fr_repeat(4,1fr)_auto]"
                    onSubmit={submitFilters}
                    aria-label="Search Discovery catalog"
                >
                    <label className="space-y-2 text-sm text-slate-300">
                        <span>Keyword search</span>
                        <input
                            type="search"
                            value={filters.query}
                            onChange={(event) =>
                                setFilters((current) => ({
                                    ...current,
                                    query: event.target.value,
                                }))
                            }
                            placeholder="Search by name or description"
                            className="w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-100 outline-none transition focus:border-blue-400 focus:ring-2 focus:ring-blue-500/30"
                        />
                    </label>

                    <SelectFilter
                        label="Item type"
                        value={filters.type}
                        onChange={(value) =>
                            setFilters((current) => ({
                                ...current,
                                type: value as "" | DiscoveryItemType,
                            }))
                        }
                        options={itemTypeOptions}
                    />

                    <SelectFilter
                        label="Status"
                        value={filters.status}
                        onChange={(value) =>
                            setFilters((current) => ({
                                ...current,
                                status: value as "" | DiscoveryItemStatus,
                            }))
                        }
                        options={statusOptions}
                    />

                    <TextFilter
                        label="Tag"
                        value={filters.tag}
                        placeholder="ai"
                        onChange={(value) =>
                            setFilters((current) => ({ ...current, tag: value }))
                        }
                    />

                    <TextFilter
                        label="Capability"
                        value={filters.capability}
                        placeholder="mqtt-broker"
                        onChange={(value) =>
                            setFilters((current) => ({
                                ...current,
                                capability: value,
                            }))
                        }
                    />

                    <div className="flex items-end gap-2">
                        <button
                            type="submit"
                            className="rounded-lg bg-blue-500 px-4 py-2 text-sm font-semibold text-white transition hover:bg-blue-400 focus:outline-none focus:ring-2 focus:ring-blue-300 disabled:cursor-not-allowed disabled:opacity-50"
                            disabled={isLoading}
                        >
                            Search
                        </button>
                        <button
                            type="button"
                            onClick={clearFilters}
                            disabled={isLoading}
                            className="rounded-lg border border-slate-700 px-4 py-2 text-sm font-semibold text-slate-300 transition hover:border-slate-500 hover:text-white focus:outline-none focus:ring-2 focus:ring-blue-300 disabled:cursor-not-allowed disabled:opacity-50"
                            aria-label="Clear Discovery filters"
                        >
                            Clear
                        </button>
                    </div>
                </form>
            </section>

            <section className="space-y-4" aria-live="polite">
                <div className="flex flex-wrap items-center justify-between gap-3">
                    <div>
                        <h2 className="text-xl font-semibold text-white">
                            {isSearchMode ? "Search results" : "Catalog items"}
                        </h2>
                        <p className="mt-1 text-sm text-slate-500">
                            {result.total} item{result.total === 1 ? "" : "s"} found
                        </p>
                    </div>

                    <div className="flex items-center gap-2">
                        <button
                            type="button"
                            onClick={goToPreviousPage}
                            disabled={isLoading || result.offset === 0}
                            className="rounded-lg border border-slate-700 px-3 py-2 text-sm text-slate-300 transition hover:border-slate-500 hover:text-white focus:outline-none focus:ring-2 focus:ring-blue-300 disabled:cursor-not-allowed disabled:opacity-50"
                            aria-label="Previous Discovery results page"
                        >
                            Previous
                        </button>
                        <button
                            type="button"
                            onClick={goToNextPage}
                            disabled={isLoading || !result.hasMore}
                            className="rounded-lg border border-slate-700 px-3 py-2 text-sm text-slate-300 transition hover:border-slate-500 hover:text-white focus:outline-none focus:ring-2 focus:ring-blue-300 disabled:cursor-not-allowed disabled:opacity-50"
                            aria-label="Next Discovery results page"
                        >
                            Next
                        </button>
                    </div>
                </div>

                {isLoading ? (
                    <div className="rounded-xl border border-slate-800 bg-slate-900/70 p-6 text-sm text-slate-400">
                        Loading Discovery catalog…
                    </div>
                ) : result.entries.length === 0 && !error ? (
                    <div className="rounded-xl border border-slate-800 bg-slate-900/70 p-6">
                        <p className="font-semibold text-slate-200">
                            {metadata?.catalog_loaded && metadata.entry_count === 0
                                ? "The Discovery catalog is loaded but empty."
                                : "No Discovery items matched these filters."}
                        </p>
                        <p className="mt-2 text-sm text-slate-500">
                            Try clearing filters or using a broader keyword.
                        </p>
                    </div>
                ) : (
                    <div className="grid gap-4 lg:grid-cols-2">
                        {result.entries.map((entry) => (
                            <DiscoveryItemCard key={entry.item.id} entry={entry} />
                        ))}
                    </div>
                )}
            </section>
        </main>
    );
}

async function fetchDiscoveryPage(filters: FilterState, offset: number) {
    const query = toDiscoveryQuery(filters, offset);
    if (filters.query.trim()) {
        const page = await searchDiscoveryItems({
            ...query,
            q: filters.query.trim(),
        });
        return {
            entries: page.results.map((result) => result.entry),
            total: page.total,
            offset: page.offset,
            has_more: page.has_more,
        };
    }

    return listDiscoveryItems(query);
}

function toDiscoveryQuery(filters: FilterState, offset: number): DiscoveryListQuery {
    return {
        limit: PAGE_SIZE,
        offset,
        type: filters.type || undefined,
        status: filters.status || undefined,
        tag: filters.tag.trim() || undefined,
        capability: filters.capability.trim() || undefined,
    };
}

function normalizeFilters(filters: FilterState): FilterState {
    return {
        query: filters.query.trim(),
        type: filters.type,
        status: filters.status,
        tag: filters.tag.trim(),
        capability: filters.capability.trim(),
    };
}

function DiscoveryStatus({
    metadata,
    isLoading,
}: {
    metadata: DiscoveryMetadata | null;
    isLoading: boolean;
}) {
    const label = metadata
        ? metadata.catalog_loaded
            ? metadata.entry_count > 0
                ? "Catalog loaded"
                : "Catalog empty"
            : "Catalog unavailable"
        : isLoading
          ? "Loading catalog"
          : "Catalog status unknown";

    return (
        <div className="grid gap-3 sm:grid-cols-3">
            <StatusTile label="Status" value={label} />
            <StatusTile
                label="Entries"
                value={metadata ? String(metadata.entry_count) : "…"}
            />
            <StatusTile
                label="Schema"
                value={metadata ? `v${metadata.schema_version}` : "…"}
            />
        </div>
    );
}

function StatusTile({ label, value }: { label: string; value: string }) {
    return (
        <div className="rounded-xl border border-slate-800 bg-slate-900/70 p-4">
            <p className="text-xs uppercase tracking-wider text-slate-500">{label}</p>
            <p className="mt-2 text-lg font-semibold text-slate-100">{value}</p>
        </div>
    );
}

function SelectFilter({
    label,
    value,
    onChange,
    options,
}: {
    label: string;
    value: string;
    onChange: (value: string) => void;
    options: { label: string; value: string }[];
}) {
    return (
        <label className="space-y-2 text-sm text-slate-300">
            <span>{label}</span>
            <select
                value={value}
                onChange={(event) => onChange(event.target.value)}
                className="w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-100 outline-none transition focus:border-blue-400 focus:ring-2 focus:ring-blue-500/30"
            >
                <option value="">All</option>
                {options.map((option) => (
                    <option key={option.value} value={option.value}>
                        {option.label}
                    </option>
                ))}
            </select>
        </label>
    );
}

function TextFilter({
    label,
    value,
    placeholder,
    onChange,
}: {
    label: string;
    value: string;
    placeholder: string;
    onChange: (value: string) => void;
}) {
    return (
        <label className="space-y-2 text-sm text-slate-300">
            <span>{label}</span>
            <input
                type="text"
                value={value}
                placeholder={placeholder}
                onChange={(event) => onChange(event.target.value)}
                className="w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-100 outline-none transition focus:border-blue-400 focus:ring-2 focus:ring-blue-500/30"
            />
        </label>
    );
}

function DiscoveryItemCard({ entry }: { entry: DiscoveryCatalogEntry }) {
    const item = entry.item;

    return (
        <article className="rounded-xl border border-slate-800 bg-slate-900/70 p-5 transition hover:border-slate-700">
            <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                    <Link
                        to={`/discovery/items/${encodeURIComponent(item.id)}`}
                        className="text-lg font-semibold text-blue-300 transition hover:text-blue-200 focus:outline-none focus:ring-2 focus:ring-blue-300"
                    >
                        {item.name}
                    </Link>
                    <p className="mt-1 text-xs text-slate-500">{item.id}</p>
                </div>
                <div className="flex flex-wrap gap-2">
                    <Badge>{formatLabel(item.type)}</Badge>
                    <Badge>{formatLabel(item.status)}</Badge>
                </div>
            </div>

            <p className="mt-4 text-sm leading-6 text-slate-400">
                {item.description}
            </p>

            <ChipList label="Capabilities" values={item.capabilities} />
            <ChipList label="Tags" values={item.tags} />
        </article>
    );
}

function ChipList({ label, values }: { label: string; values: string[] }) {
    if (values.length === 0) {
        return null;
    }

    return (
        <div className="mt-4">
            <p className="text-xs uppercase tracking-wider text-slate-500">
                {label}
            </p>
            <div className="mt-2 flex flex-wrap gap-2">
                {values.map((value) => (
                    <span
                        key={value}
                        className="rounded-full border border-slate-700 bg-slate-950 px-2.5 py-1 text-xs text-slate-300"
                    >
                        {value}
                    </span>
                ))}
            </div>
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

function formatLabel(value: string): string {
    return value
        .split("_")
        .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
        .join(" ");
}
