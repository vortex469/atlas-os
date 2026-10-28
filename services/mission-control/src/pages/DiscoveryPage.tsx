import { useCallback, useEffect, useRef, useState } from "react";
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

type DiscoveryRequest = {
    filters: FilterState;
    offset: number;
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
    const [metadataError, setMetadataError] = useState<string | null>(null);
    const [isMetadataLoading, setIsMetadataLoading] = useState(true);
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
    const [catalogError, setCatalogError] = useState<string | null>(null);
    const requestGeneration = useRef(0);
    const metadataGeneration = useRef(0);
    const lastRequestedQuery = useRef<DiscoveryRequest>({ filters: emptyFilters, offset: 0 });

    const loadMetadata = useCallback(async () => {
        const generation = ++metadataGeneration.current;
        setIsMetadataLoading(true);
        setMetadataError(null);

        try {
            const nextMetadata = await getDiscoveryMetadata();
            if (generation === metadataGeneration.current) setMetadata(nextMetadata);
        } catch (requestError) {
            if (generation === metadataGeneration.current) {
                setMetadataError(
                    getAtlasErrorMessage(requestError, "Mission Control could not load catalog status."),
                );
            }
        } finally {
            if (generation === metadataGeneration.current) setIsMetadataLoading(false);
        }
    }, []);

    const loadCatalog = useCallback(
        async (nextFilters: FilterState, offset: number) => {
            const generation = ++requestGeneration.current;
            lastRequestedQuery.current = { filters: { ...nextFilters }, offset };
            setIsLoading(true);
            setCatalogError(null);
            setResult({ entries: [], total: 0, offset, hasMore: false });

            try {
                const page = await fetchDiscoveryPage(nextFilters, offset);
                if (!isDisplayableDiscoveryPage(page)) {
                    throw new Error("The catalog response included an item that Mission Control could not display.");
                }

                if (generation === requestGeneration.current) {
                    setResult({
                        entries: page.entries,
                        total: page.total,
                        offset: page.offset,
                        hasMore: page.has_more,
                    });
                }
            } catch (requestError) {
                if (generation === requestGeneration.current) {
                    console.error("Unable to load Discovery catalog:", requestError);
                    setCatalogError(
                        getAtlasErrorMessage(
                            requestError,
                            "Mission Control could not load the catalog.",
                        ),
                    );
                }
            } finally {
                if (generation === requestGeneration.current) {
                    setIsLoading(false);
                }
            }
        },
        [],
    );

    useEffect(() => {
        let active = true;
        void Promise.resolve().then(() => {
            if (active) {
                void loadMetadata();
                void loadCatalog(emptyFilters, 0);
            }
        });
        return () => {
            active = false;
            requestGeneration.current += 1;
            metadataGeneration.current += 1;
        };
    }, [loadCatalog, loadMetadata]);

    const hasSubmittedFilters = Object.values(submittedFilters).some((value) => value.trim().length > 0);
    const hasFiltersToClear = hasSubmittedFilters || Object.values(filters).some((value) => value.trim().length > 0);
    const hasAdvancedFilters = Boolean(submittedFilters.tag || submittedFilters.capability);
    const hasUnappliedFilters = !filtersEqual(normalizeFilters(filters), submittedFilters);
    const catalogIsEmpty = metadata?.catalog_loaded === true && metadata.entry_count === 0;
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

    function retryLastSearch() {
        void loadCatalog(lastRequestedQuery.current.filters, lastRequestedQuery.current.offset);
    }

    const resultSummary = isLoading
        ? "Loading items…"
        : catalogError
          ? "Items unavailable"
          : `${result.total} ${hasSubmittedFilters ? "matching " : ""}item${result.total === 1 ? "" : "s"} ${hasSubmittedFilters ? "found" : "listed"}`;

    return (
        <main className="mx-auto max-w-7xl space-y-8 p-4 sm:p-8">
            <header className="space-y-4">
                <div>
                    <h1 className="mt-3 text-3xl font-bold text-white">
                        Browse the catalog
                    </h1>
                    <p className="mt-3 max-w-3xl text-sm leading-6 text-slate-400">
                        Find applications, services, container images, AI models,
                        integrations, devices, and deployment methods. Listings are
                        reference information; compatibility, install support, and
                        permission to make changes are checked separately.
                    </p>
                </div>

                <DiscoveryStatus
                    metadata={metadata}
                    error={metadataError}
                    isLoading={isMetadataLoading}
                    onRetry={() => void loadMetadata()}
                />
            </header>

            {catalogError && (
                <div
                    role="alert"
                    className="rounded-xl border border-red-500/30 bg-red-500/10 p-5"
                >
                    <p className="font-semibold text-red-300">
                        Catalog could not be loaded
                    </p>
                    <p className="mt-1 text-sm text-red-200/80">Mission Control could not load these catalog results. Your search filters are still selected.</p>
                    <button type="button" onClick={retryLastSearch} disabled={isLoading} className="mt-4 rounded-lg border border-red-300/40 px-3 py-2 text-sm font-semibold text-red-100 transition hover:bg-red-500/10 focus:outline-none focus:ring-2 focus:ring-red-200 disabled:cursor-not-allowed disabled:opacity-50">
                        Retry catalog load
                    </button>
                    <details className="mt-3">
                        <summary className="cursor-pointer text-sm font-medium text-slate-300 focus:outline-none focus:ring-2 focus:ring-blue-300">Technical details</summary>
                        <p className="mt-2 break-words text-sm text-slate-400">{catalogError}</p>
                    </details>
                </div>
            )}

            <section className="rounded-xl border border-slate-800 bg-slate-900/70 p-5">
                <form
                    className="space-y-4"
                    onSubmit={submitFilters}
                    aria-label="Search catalog"
                >
                    <div className="grid gap-4 lg:grid-cols-[2fr_repeat(2,1fr)_auto]">
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

                        <div className="flex items-end gap-2">
                            <button
                                type="submit"
                                className="rounded-lg bg-blue-500 px-4 py-2 text-sm font-semibold text-white transition hover:bg-blue-400 focus:outline-none focus:ring-2 focus:ring-blue-300 disabled:cursor-not-allowed disabled:opacity-50"
                                disabled={isLoading}
                            >
                                Search
                            </button>
                            {hasFiltersToClear && (
                                <button
                                    type="button"
                                    onClick={clearFilters}
                                    disabled={isLoading}
                                    className="rounded-lg border border-slate-700 px-4 py-2 text-sm font-semibold text-slate-300 transition hover:border-slate-500 hover:text-white focus:outline-none focus:ring-2 focus:ring-blue-300 disabled:cursor-not-allowed disabled:opacity-50"
                                >
                                    Clear filters
                                </button>
                            )}
                        </div>
                    </div>
                    <details className="rounded-lg border border-slate-800 px-4 py-3">
                        <summary className="cursor-pointer text-sm font-medium text-slate-300 focus:outline-none focus:ring-2 focus:ring-blue-300">
                            More filters{hasAdvancedFilters ? " · active" : ""}
                        </summary>
                        <div className="mt-4 grid gap-4 sm:grid-cols-2">
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
                                    setFilters((current) => ({ ...current, capability: value }))
                                }
                            />
                        </div>
                    </details>
                </form>
            </section>

            <section className="space-y-4" aria-live="polite">
                {hasUnappliedFilters && (
                    <p role="status" className="rounded-lg border border-blue-500/30 bg-blue-500/10 px-4 py-3 text-sm text-blue-100">
                        These filter changes haven&apos;t been searched yet. Select Search to update the results.
                    </p>
                )}
                <div className="flex flex-wrap items-center justify-between gap-3">
                    <div>
                        <h2 className="text-xl font-semibold text-white">
                            {hasSubmittedFilters ? "Search results" : "Catalog items"}
                        </h2>
                        <p className="mt-1 text-sm text-slate-500">
                            {resultSummary}
                        </p>
                    </div>

                    <div className="flex items-center gap-2">
                        <button
                            type="button"
                            onClick={goToPreviousPage}
                            disabled={isLoading || hasUnappliedFilters || result.offset === 0}
                            className="rounded-lg border border-slate-700 px-3 py-2 text-sm text-slate-300 transition hover:border-slate-500 hover:text-white focus:outline-none focus:ring-2 focus:ring-blue-300 disabled:cursor-not-allowed disabled:opacity-50"
                            aria-label="Previous page"
                        >
                            Previous
                        </button>
                        <button
                            type="button"
                            onClick={goToNextPage}
                            disabled={isLoading || hasUnappliedFilters || !result.hasMore}
                            className="rounded-lg border border-slate-700 px-3 py-2 text-sm text-slate-300 transition hover:border-slate-500 hover:text-white focus:outline-none focus:ring-2 focus:ring-blue-300 disabled:cursor-not-allowed disabled:opacity-50"
                            aria-label="Next page"
                        >
                            Next
                        </button>
                    </div>
                </div>

                {isLoading ? (
                    <div className="rounded-xl border border-slate-800 bg-slate-900/70 p-6 text-sm text-slate-400">
                        Loading catalog…
                    </div>
                ) : catalogError ? (
                    <div className="rounded-xl border border-slate-800 bg-slate-900/70 p-6">
                        <p className="font-semibold text-slate-200">Results unavailable</p>
                        <p className="mt-2 text-sm text-slate-500">Retry catalog load above to try this search again.</p>
                    </div>
                ) : result.entries.length === 0 ? (
                    <div className="rounded-xl border border-slate-800 bg-slate-900/70 p-6">
                        <p className="font-semibold text-slate-200">
                            {catalogIsEmpty
                                ? "No catalog items are available."
                                : hasSubmittedFilters
                                  ? "No items matched these filters."
                                  : result.offset > 0
                                    ? "No items are on this page."
                                    : "No catalog items were returned."}
                        </p>
                        {!catalogIsEmpty && <p className="mt-2 text-sm text-slate-500">
                            {hasSubmittedFilters
                                ? "Clear filters or broaden your search."
                                : result.offset > 0
                                  ? "Use Previous to check earlier results."
                                  : "Use Search to check the catalog again."}
                        </p>}
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

function isDisplayableDiscoveryPage(value: unknown): value is {
    entries: DiscoveryCatalogEntry[];
    total: number;
    offset: number;
    has_more: boolean;
} {
    if (typeof value !== "object" || value === null || Array.isArray(value)) return false;
    const page = value as Record<string, unknown>;
    return Array.isArray(page.entries)
        && page.entries.every(isDisplayableDiscoveryEntry)
        && typeof page.total === "number" && Number.isInteger(page.total) && page.total >= 0
        && typeof page.offset === "number" && Number.isInteger(page.offset) && page.offset >= 0
        && typeof page.has_more === "boolean";
}

function isDisplayableDiscoveryEntry(value: unknown): value is DiscoveryCatalogEntry {
    if (typeof value !== "object" || value === null || Array.isArray(value)) return false;
    const entry = value as Record<string, unknown>;
    if (typeof entry.item !== "object" || entry.item === null || Array.isArray(entry.item)) return false;
    const item = entry.item as Record<string, unknown>;
    return typeof item.id === "string"
        && typeof item.name === "string"
        && typeof item.type === "string"
        && typeof item.status === "string"
        && typeof item.description === "string"
        && Array.isArray(item.capabilities) && item.capabilities.every((value) => typeof value === "string")
        && Array.isArray(item.tags) && item.tags.every((value) => typeof value === "string");
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

function filtersEqual(left: FilterState, right: FilterState): boolean {
    return left.query === right.query
        && left.type === right.type
        && left.status === right.status
        && left.tag === right.tag
        && left.capability === right.capability;
}

function DiscoveryStatus({
    metadata,
    error,
    isLoading,
    onRetry,
}: {
    metadata: DiscoveryMetadata | null;
    error: string | null;
    isLoading: boolean;
    onRetry: () => void;
}) {
    const label = metadata
        ? metadata.catalog_loaded
            ? metadata.entry_count > 0
                ? "Catalog loaded"
                : "Catalog empty"
            : "Catalog unavailable"
        : isLoading
          ? "Checking catalog status"
          : error
            ? "Catalog status unavailable"
            : "Catalog status unknown";

    return (
        <>
            <div className="grid gap-3 sm:grid-cols-2">
                <StatusTile label="Status" value={label} />
                <StatusTile
                    label="Catalog total"
                    value={metadata ? String(metadata.entry_count) : isLoading ? "Loading" : "Unavailable"}
                />
            </div>
            {error && (
                <div className="mt-3 rounded-xl border border-amber-500/30 bg-amber-500/10 p-4">
                    <p className="text-sm text-amber-100">Catalog status could not be checked. Catalog items remain available.</p>
                    <button type="button" onClick={onRetry} disabled={isLoading} className="mt-3 rounded-lg border border-amber-300/40 px-3 py-2 text-sm font-semibold text-amber-100 disabled:cursor-not-allowed disabled:opacity-50">
                        Retry status check
                    </button>
                    <details className="mt-3">
                        <summary className="cursor-pointer text-sm font-medium text-slate-300">Technical details</summary>
                        <p className="mt-2 break-words text-sm text-slate-400">{error}</p>
                    </details>
                </div>
            )}
            <details className="mt-3 rounded-xl border border-slate-800 bg-slate-900/70 p-4">
                <summary className="cursor-pointer text-sm font-medium text-slate-300">
                    Technical details
                </summary>
                <p className="mt-3 text-sm text-slate-400">
                    Catalog format version: {metadata ? `v${metadata.schema_version}` : "Not available"}
                </p>
            </details>
        </>
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
                </div>
                <div className="flex flex-wrap gap-2">
                    <Badge>{formatLabel(item.type)}</Badge>
                    <Badge>{formatLabel(item.status)}</Badge>
                </div>
            </div>

            <p className="mt-4 text-sm leading-6 text-slate-400">
                {item.description}
            </p>

            <ChipList label="Capabilities" values={item.capabilities} formatValue={formatCapability} />
            <ChipList label="Tags" values={item.tags} formatValue={formatCapability} />
            <details className="mt-4 border-t border-slate-800 pt-3">
                <summary className="cursor-pointer text-sm text-slate-300 focus:outline-none focus:ring-2 focus:ring-blue-300">Technical details</summary>
                <p className="mt-2 break-all text-sm text-slate-400">Catalog item ID: {item.id}</p>
            </details>
        </article>
    );
}

function ChipList({ label, values, formatValue }: { label: string; values: string[]; formatValue: (value: string) => string }) {
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
                        {formatValue(value)}
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
        .split(/[_-]+/)
        .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
        .join(" ");
}

function formatCapability(value: string): string {
    const words = value.replace(/[_-]+/g, " ").trim();
    return words ? words.charAt(0).toUpperCase() + words.slice(1) : value;
}
