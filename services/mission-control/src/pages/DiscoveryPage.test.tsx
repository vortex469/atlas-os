import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import {
    getDiscoveryMetadata,
    listDiscoveryItems,
    searchDiscoveryItems,
} from "../api/discovery";
import type {
    DiscoveryCatalogEntry,
    DiscoveryCatalogPage,
    DiscoveryMetadata,
    DiscoverySearchPage,
} from "../types/discovery";
import { DiscoveryPage } from "./DiscoveryPage";

vi.mock("../api/atlas", () => ({
    getAtlasErrorMessage: (error: unknown, fallback: string) =>
        error instanceof Error ? error.message : fallback,
}));

vi.mock("../api/discovery", () => ({
    getDiscoveryMetadata: vi.fn(),
    listDiscoveryItems: vi.fn(),
    searchDiscoveryItems: vi.fn(),
}));

const mockedGetDiscoveryMetadata = vi.mocked(getDiscoveryMetadata);
const mockedListDiscoveryItems = vi.mocked(listDiscoveryItems);
const mockedSearchDiscoveryItems = vi.mocked(searchDiscoveryItems);

function metadata(overrides: Partial<DiscoveryMetadata> = {}): DiscoveryMetadata {
    return {
        catalog_loaded: true,
        entry_count: 2,
        schema_version: 1,
        ...overrides,
    };
}

function entry(overrides: Partial<DiscoveryCatalogEntry> = {}): DiscoveryCatalogEntry {
    return {
        schema_version: 1,
        item: {
            id: "home-assistant",
            type: "application",
            status: "active",
            name: "Home Assistant",
            description: "Local-first home automation platform.",
            version: null,
            aliases: ["hass"],
            tags: ["home-automation", "iot"],
            homepage_url: null,
            documentation_url: null,
            capabilities: ["home-automation", "device-integration"],
            requirements: {
                capabilities: [],
                resources: { gpu_required: false },
                platform: {
                    architectures: [],
                    operating_systems: [],
                    runtimes: [],
                    devices: [],
                },
                network: { ports: [] },
            },
            relationships: [],
            metadata: {},
        },
        provenance: {
            source_type: "curated",
            source: "atlas-curated-discovery-catalog",
            entry_id: "d5-home-assistant",
            version: null,
            trust_level: "curated",
        },
        metadata: { reviewed_for_d5: true },
        ...overrides,
    };
}

function page(entries: DiscoveryCatalogEntry[]): DiscoveryCatalogPage {
    return {
        entries,
        total: entries.length,
        limit: 25,
        offset: 0,
        has_more: false,
    };
}

function searchPage(entries: DiscoveryCatalogEntry[]): DiscoverySearchPage {
    return {
        results: entries.map((catalogEntry) => ({
            item: catalogEntry.item,
            entry: catalogEntry,
            evidence: [
                {
                    field: "name",
                    value: catalogEntry.item.name,
                    matched_text: catalogEntry.item.name,
                    match_type: "exact",
                },
            ],
        })),
        total: entries.length,
        limit: 25,
        offset: 0,
        has_more: false,
    };
}

function deferred<T>() {
    let resolve!: (value: T) => void;
    const promise = new Promise<T>((resolvePromise) => { resolve = resolvePromise; });
    return { promise, resolve };
}

function renderPage() {
    return render(
        <MemoryRouter>
            <DiscoveryPage />
        </MemoryRouter>,
    );
}

describe("DiscoveryPage", () => {
    beforeEach(() => {
        vi.resetAllMocks();
        mockedGetDiscoveryMetadata.mockResolvedValue(metadata());
        mockedListDiscoveryItems.mockResolvedValue(page([entry()]));
        mockedSearchDiscoveryItems.mockResolvedValue(searchPage([entry()]));
    });

    it("renders catalog status, plain-language scope, and read-only item cards", async () => {
        const user = userEvent.setup();
        renderPage();

        expect(await screen.findByText("Home Assistant")).toBeInTheDocument();
        expect(screen.getByText("Catalog loaded")).toBeInTheDocument();
        expect(screen.getByText("Catalog total").nextElementSibling).toHaveTextContent("2");
        expect(screen.getByText("1 item listed")).toBeInTheDocument();
        expect(screen.getByRole("heading", { name: "Browse the catalog" })).toBeInTheDocument();
        expect(screen.queryByRole("button", { name: "Clear filters" })).not.toBeInTheDocument();
        expect(screen.getByText(/Listings are reference information; compatibility, install support, and permission to make changes are checked separately/i)).toBeInTheDocument();
        const itemCard = screen.getByRole("link", { name: "Home Assistant" }).closest("article");
        expect(within(itemCard as HTMLElement).getByText("Catalog item ID: home-assistant")).not.toBeVisible();
        expect(within(itemCard as HTMLElement).getAllByText("Home automation")).toHaveLength(2);
        expect(within(itemCard as HTMLElement).getByText("Device integration")).toBeInTheDocument();
        expect(within(itemCard as HTMLElement).queryByText("home-automation", { exact: true })).not.toBeInTheDocument();
        await user.click(within(itemCard as HTMLElement).getByText("Technical details"));
        expect(within(itemCard as HTMLElement).getByText("Catalog item ID: home-assistant")).toBeVisible();
        const metadataDetails = screen.getByText("Catalog format version: v1").closest("details");
        expect(within(metadataDetails as HTMLDetailsElement).getByText("Catalog format version: v1")).not.toBeVisible();
        await user.click(within(metadataDetails as HTMLDetailsElement).getByText("Technical details"));
        expect(within(metadataDetails as HTMLDetailsElement).getByText("Catalog format version: v1")).toBeVisible();
        expect(screen.queryByRole("button", { name: /install/i })).not.toBeInTheDocument();
        expect(screen.getByRole("link", { name: "Home Assistant" })).toHaveAttribute(
            "href",
            "/discovery/items/home-assistant",
        );
    });

    it("uses explicit search submit and sends filters", async () => {
        const user = userEvent.setup();
        renderPage();

        await screen.findByText("Home Assistant");
        await user.type(screen.getByLabelText("Keyword search"), "ollama");
        await user.selectOptions(screen.getByLabelText("Item type"), "service");
        await user.selectOptions(screen.getByLabelText("Status"), "active");
        expect(screen.getByLabelText("Tag")).not.toBeVisible();
        await user.click(screen.getByText("More filters"));
        await user.type(screen.getByLabelText("Tag"), "ai");
        await user.type(screen.getByLabelText("Capability"), "llm-inference");
        expect(screen.getByRole("status")).toHaveTextContent("These filter changes haven't been searched yet. Select Search to update the results.");
        await user.click(screen.getByRole("button", { name: "Search" }));
        expect(screen.queryByText("These filter changes haven't been searched yet. Select Search to update the results.")).not.toBeInTheDocument();
        expect(screen.getByText("More filters · active")).toBeInTheDocument();
        expect(screen.getByRole("heading", { name: "Search results" })).toBeInTheDocument();
        expect(screen.getByText("1 matching item found")).toBeInTheDocument();
        expect(screen.getByRole("button", { name: "Clear filters" })).toBeInTheDocument();

        await waitFor(() =>
            expect(mockedSearchDiscoveryItems).toHaveBeenLastCalledWith({
                q: "ollama",
                limit: 25,
                offset: 0,
                type: "service",
                status: "active",
                tag: "ai",
                capability: "llm-inference",
            }),
        );
        expect(mockedListDiscoveryItems).toHaveBeenCalledTimes(1);
    });

    it("pauses paging while draft filters differ from the displayed results", async () => {
        const firstPage = { ...page([entry()]), total: 26, has_more: true };
        const matchingPage = { ...searchPage([entry()]), total: 26, has_more: true };
        mockedListDiscoveryItems.mockResolvedValueOnce(firstPage);
        mockedSearchDiscoveryItems.mockResolvedValueOnce(matchingPage);
        const user = userEvent.setup();
        renderPage();

        await screen.findByText("Home Assistant");
        const next = screen.getByRole("button", { name: "Next page" });
        expect(next).toBeEnabled();
        await user.type(screen.getByLabelText("Keyword search"), "ollama");
        expect(screen.getByText("These filter changes haven't been searched yet. Select Search to update the results.")).toBeVisible();
        expect(next).toBeDisabled();

        await user.click(screen.getByRole("button", { name: "Search" }));
        await waitFor(() => expect(mockedSearchDiscoveryItems).toHaveBeenCalledWith({
            q: "ollama", limit: 25, offset: 0, type: undefined, status: undefined, tag: undefined, capability: undefined,
        }));
        expect(screen.queryByText("These filter changes haven't been searched yet. Select Search to update the results.")).not.toBeInTheDocument();
        await waitFor(() => expect(next).toBeEnabled());
    });

    it("uses item listing when submitted query is empty", async () => {
        const user = userEvent.setup();
        renderPage();

        await screen.findByText("Home Assistant");
        await user.selectOptions(screen.getByLabelText("Item type"), "application");
        await user.click(screen.getByRole("button", { name: "Search" }));

        await waitFor(() =>
            expect(mockedListDiscoveryItems).toHaveBeenLastCalledWith({
                limit: 25,
                offset: 0,
                type: "application",
                status: undefined,
                tag: undefined,
                capability: undefined,
            }),
        );
        expect(screen.getByRole("heading", { name: "Search results" })).toBeInTheDocument();
        expect(screen.getByText("1 matching item found")).toBeInTheDocument();
        expect(mockedSearchDiscoveryItems).not.toHaveBeenCalled();
    });

    it("shows clear only while draft or submitted filters need clearing", async () => {
        const user = userEvent.setup();
        renderPage();

        await screen.findByText("Home Assistant");
        const query = screen.getByLabelText("Keyword search");
        await user.type(query, "ollama");
        expect(screen.getByRole("button", { name: "Clear filters" })).toBeInTheDocument();
        await user.click(screen.getByRole("button", { name: "Search" }));
        await screen.findByRole("heading", { name: "Search results" });
        await user.click(screen.getByRole("button", { name: "Clear filters" }));

        expect(query).toHaveValue("");
        expect(screen.queryByRole("button", { name: "Clear filters" })).not.toBeInTheDocument();
        await waitFor(() => expect(mockedListDiscoveryItems).toHaveBeenLastCalledWith({
            limit: 25,
            offset: 0,
            type: undefined,
            status: undefined,
            tag: undefined,
            capability: undefined,
        }));
    });

    it("keeps the latest search results when an older request finishes later", async () => {
        const user = userEvent.setup();
        const olderSearch = deferred<DiscoverySearchPage>();
        const latestSearch = deferred<DiscoverySearchPage>();
        mockedSearchDiscoveryItems
            .mockReset()
            .mockReturnValueOnce(olderSearch.promise)
            .mockReturnValueOnce(latestSearch.promise);

        renderPage();
        await screen.findByText("Home Assistant");
        const query = screen.getByLabelText("Keyword search");
        const form = screen.getByRole("form", { name: "Search catalog" });
        await user.type(query, "redis");
        fireEvent.submit(form);
        await waitFor(() => expect(mockedSearchDiscoveryItems).toHaveBeenCalledTimes(1));

        await user.clear(query);
        await user.type(query, "postgres");
        fireEvent.submit(form);
        await waitFor(() => expect(mockedSearchDiscoveryItems).toHaveBeenCalledTimes(2));

        await act(async () => olderSearch.resolve(searchPage([entry({
            item: { ...entry().item, id: "redis", name: "Redis" },
        })])));
        expect(screen.getByText("Loading catalog…")).toBeInTheDocument();
        expect(screen.queryByText("Redis")).not.toBeInTheDocument();

        await act(async () => latestSearch.resolve(searchPage([entry({
            item: { ...entry().item, id: "postgres", name: "PostgreSQL" },
        })])));

        expect(screen.getByText("PostgreSQL")).toBeInTheDocument();
        expect(screen.queryByText("Loading catalog…")).not.toBeInTheDocument();
        expect(screen.queryByText("Redis")).not.toBeInTheDocument();
        expect(mockedSearchDiscoveryItems).toHaveBeenNthCalledWith(1, expect.objectContaining({ q: "redis" }));
        expect(mockedSearchDiscoveryItems).toHaveBeenNthCalledWith(2, expect.objectContaining({ q: "postgres" }));
    });

    it("supports previous-page navigation and respects pagination buttons", async () => {
        const user = userEvent.setup();
        mockedListDiscoveryItems
            .mockResolvedValueOnce({
                ...page([entry()]),
                total: 30,
                offset: 0,
                has_more: true,
            })
            .mockResolvedValueOnce({
                ...page([entry({ item: { ...entry().item, id: "redis", name: "Redis" } })]),
                total: 30,
                offset: 25,
                has_more: false,
            })
            .mockResolvedValueOnce(page([entry()]));

        renderPage();
        await screen.findByText("Home Assistant");
        await user.click(screen.getByRole("button", { name: "Next page" }));

        await waitFor(() =>
            expect(mockedListDiscoveryItems).toHaveBeenLastCalledWith({
                limit: 25,
                offset: 25,
                type: undefined,
                status: undefined,
                tag: undefined,
                capability: undefined,
            }),
        );

        await user.click(screen.getByRole("button", { name: "Previous page" }));
        await waitFor(() =>
            expect(mockedListDiscoveryItems).toHaveBeenLastCalledWith({
                limit: 25,
                offset: 0,
                type: undefined,
                status: undefined,
                tag: undefined,
                capability: undefined,
            }),
        );
    });

    it("distinguishes loaded empty catalog from unavailable catalog", async () => {
        mockedGetDiscoveryMetadata.mockResolvedValue(metadata({ entry_count: 0 }));
        mockedListDiscoveryItems.mockResolvedValue(page([]));

        renderPage();

        expect(await screen.findByText("No catalog items are available.")).toBeInTheDocument();
        expect(screen.getByText("Catalog empty")).toBeInTheDocument();
        expect(screen.queryByText("Clear filters or broaden your search.")).not.toBeInTheDocument();
        expect(screen.queryByRole("button", { name: "Clear filters" })).not.toBeInTheDocument();
    });

    it("offers filter recovery when a search has no matches", async () => {
        const user = userEvent.setup();
        mockedSearchDiscoveryItems.mockResolvedValue(searchPage([]));
        renderPage();

        await screen.findByText("Home Assistant");
        await user.type(screen.getByLabelText("Keyword search"), "not-in-catalog");
        await user.click(screen.getByRole("button", { name: "Search" }));

        expect(await screen.findByText("No items matched these filters.")).toBeInTheDocument();
        expect(screen.getByText("0 matching items found")).toBeInTheDocument();
        expect(screen.getByText("Clear filters or broaden your search.")).toBeInTheDocument();
        expect(screen.getByRole("button", { name: "Clear filters" })).toBeInTheDocument();
    });

    it("points an empty later page back to earlier results", async () => {
        const user = userEvent.setup();
        mockedListDiscoveryItems
            .mockResolvedValueOnce({ ...page([entry()]), total: 30, offset: 0, has_more: true })
            .mockResolvedValueOnce({ ...page([]), total: 30, offset: 25, has_more: false });
        renderPage();

        await screen.findByText("Home Assistant");
        await user.click(screen.getByRole("button", { name: "Next page" }));

        expect(await screen.findByText("No items are on this page.")).toBeInTheDocument();
        expect(screen.getByText("Use Previous to check earlier results.")).toBeInTheDocument();
        expect(screen.getByRole("button", { name: "Previous page" })).toBeEnabled();
    });

    it("retries the initial catalog load and keeps technical errors collapsed", async () => {
        const user = userEvent.setup();
        mockedListDiscoveryItems.mockRejectedValueOnce(new Error("Catalog unavailable"));

        renderPage();

        const alert = await screen.findByRole("alert");
        expect(alert).toHaveTextContent("Catalog could not be loaded");
        expect(alert).toHaveTextContent("Mission Control could not load these catalog results. Your search filters are still selected.");
        expect(screen.getByText("Results unavailable")).toBeInTheDocument();
        expect(screen.getByText("Items unavailable")).toBeInTheDocument();
        const technicalDetails = within(alert).getByText("Technical details").closest("details");
        expect(technicalDetails).not.toHaveAttribute("open");
        expect(within(technicalDetails as HTMLDetailsElement).getByText("Catalog unavailable")).not.toBeVisible();
        await user.click(within(technicalDetails as HTMLDetailsElement).getByText("Technical details"));
        expect(within(technicalDetails as HTMLDetailsElement).getByText("Catalog unavailable")).toBeVisible();
        await user.click(screen.getByRole("button", { name: "Retry catalog load" }));
        expect(await screen.findByText("Home Assistant")).toBeInTheDocument();
        expect(screen.getByText("Catalog loaded")).toBeInTheDocument();
        expect(mockedGetDiscoveryMetadata).toHaveBeenCalledTimes(1);
    });

    it("shows a retryable result state when the catalog contains an unreadable item", async () => {
        const user = userEvent.setup();
        mockedListDiscoveryItems
            .mockResolvedValueOnce({ ...page([]), entries: [null as unknown as DiscoveryCatalogEntry], total: 1 })
            .mockResolvedValueOnce(page([entry()]));

        renderPage();

        const alert = await screen.findByRole("alert");
        expect(alert).toHaveTextContent("Catalog could not be loaded");
        expect(screen.getByText("Results unavailable")).toBeInTheDocument();
        expect(screen.queryByText("Home Assistant")).not.toBeInTheDocument();
        const technicalDetails = within(alert).getByText("Technical details").closest("details");
        expect(technicalDetails).not.toHaveAttribute("open");

        await user.click(screen.getByRole("button", { name: "Retry catalog load" }));

        expect(await screen.findByText("Home Assistant")).toBeInTheDocument();
        expect(screen.queryByRole("alert")).not.toBeInTheDocument();
        expect(mockedListDiscoveryItems).toHaveBeenCalledTimes(2);
    });

    it("keeps catalog results available when status fails and retries status alone", async () => {
        const user = userEvent.setup();
        mockedGetDiscoveryMetadata
            .mockRejectedValueOnce(new Error("Status endpoint unavailable"))
            .mockResolvedValueOnce(metadata());

        renderPage();

        expect(await screen.findByText("Home Assistant")).toBeInTheDocument();
        expect(await screen.findByText("Catalog status could not be checked. Catalog items remain available.")).toBeInTheDocument();
        expect(screen.getByText("Catalog status unavailable")).toBeInTheDocument();
        expect(screen.getByText("Catalog total").nextElementSibling).toHaveTextContent("Unavailable");
        expect(screen.getByText("1 item listed")).toBeInTheDocument();
        expect(screen.queryByRole("alert")).not.toBeInTheDocument();

        await user.click(screen.getByRole("button", { name: "Retry status check" }));

        expect(await screen.findByText("Catalog loaded")).toBeInTheDocument();
        expect(screen.getByText("Home Assistant")).toBeInTheDocument();
        expect(mockedGetDiscoveryMetadata).toHaveBeenCalledTimes(2);
        expect(mockedListDiscoveryItems).toHaveBeenCalledTimes(1);
    });

    it("clears previous results and retries the exact failed search", async () => {
        const user = userEvent.setup();
        mockedSearchDiscoveryItems.mockRejectedValueOnce(new Error("Search unavailable"))
            .mockResolvedValueOnce(searchPage([entry({
                item: { ...entry().item, id: "ollama", name: "Ollama" },
            })]));

        renderPage();
        await screen.findByText("Home Assistant");
        await user.type(screen.getByLabelText("Keyword search"), "ollama");
        await user.click(screen.getByRole("button", { name: "Search" }));

        const alert = await screen.findByRole("alert");
        expect(alert).toHaveTextContent("Your search filters are still selected.");
        expect(screen.queryByText("Home Assistant")).not.toBeInTheDocument();
        expect(screen.queryByText("Ollama")).not.toBeInTheDocument();
        expect(screen.getByText("Results unavailable")).toBeInTheDocument();
        expect(screen.getByText("Items unavailable")).toBeInTheDocument();

        await user.click(screen.getByRole("button", { name: "Retry catalog load" }));
        expect(await screen.findByText("Ollama")).toBeInTheDocument();
        expect(screen.queryByRole("alert")).not.toBeInTheDocument();
        expect(mockedSearchDiscoveryItems).toHaveBeenLastCalledWith(expect.objectContaining({ q: "ollama", offset: 0 }));
    });
});
