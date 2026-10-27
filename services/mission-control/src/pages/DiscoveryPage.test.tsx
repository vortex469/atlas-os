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

    it("hides old results after a failed search and retries submitted filters instead of draft edits", async () => {
        const user = userEvent.setup();
        mockedSearchDiscoveryItems.mockRejectedValueOnce(new Error("Search offline"));
        renderPage();
        await screen.findByText("Home Assistant");
        await user.type(screen.getByLabelText("Keyword search"), "redis");
        await user.click(screen.getByRole("button", { name: /^Search$/ }));
        await screen.findByText("Search offline");
        expect(screen.queryByText("Home Assistant")).not.toBeInTheDocument();
        expect(screen.queryByText("1 item found")).not.toBeInTheDocument();
        expect(screen.getByText("Results unavailable")).toBeInTheDocument();
        await user.clear(screen.getByLabelText("Keyword search"));
        await user.type(screen.getByLabelText("Keyword search"), "draft-change");
        mockedSearchDiscoveryItems.mockResolvedValue(searchPage([entry({ item: { ...entry().item, id: "redis", name: "Redis" } })]));
        await user.click(screen.getByRole("button", { name: "Retry catalog request" }));
        expect(await screen.findByText("Redis")).toBeInTheDocument();
        expect(mockedSearchDiscoveryItems).toHaveBeenLastCalledWith(expect.objectContaining({ q: "redis", offset: 0 }));
        expect(screen.getByLabelText("Keyword search")).toHaveValue("draft-change");
    });

    it("retries the failed page offset instead of jumping back to the first page", async () => {
        const user = userEvent.setup();
        mockedListDiscoveryItems.mockResolvedValueOnce({ ...page([entry()]), total: 30, has_more: true })
            .mockRejectedValueOnce(new Error("Next page offline"))
            .mockResolvedValueOnce({ ...page([entry({ item: { ...entry().item, id: "redis", name: "Redis" } })]), total: 30, offset: 25 });
        renderPage();
        await screen.findByText("Home Assistant");
        await user.click(screen.getByRole("button", { name: "Next Discovery results page" }));
        await screen.findByText("Next page offline");
        expect(screen.queryByText("Home Assistant")).not.toBeInTheDocument();
        expect(screen.getByRole("button", { name: "Next Discovery results page" })).toBeDisabled();
        await user.click(screen.getByRole("button", { name: "Retry catalog request" }));
        expect(await screen.findByText("Redis")).toBeInTheDocument();
        expect(mockedListDiscoveryItems).toHaveBeenLastCalledWith(expect.objectContaining({ offset: 25 }));
    });

    it("ignores an earlier request that finishes after a newer search", async () => {
        const user = userEvent.setup();
        let finish!: (value: DiscoveryCatalogPage) => void;
        mockedListDiscoveryItems.mockReturnValueOnce(new Promise(resolve => { finish = resolve; }));
        mockedSearchDiscoveryItems.mockResolvedValue(searchPage([entry({ item: { ...entry().item, id: "redis", name: "Redis" } })]));
        renderPage();
        await waitFor(() => expect(mockedListDiscoveryItems).toHaveBeenCalledTimes(1));
        await user.type(screen.getByLabelText("Keyword search"), "redis");
        fireEvent.submit(screen.getByRole("form", { name: "Search Discovery catalog" }));
        await screen.findByText("Redis");
        await act(async () => finish(page([entry()])));
        expect(screen.queryByText("Home Assistant")).not.toBeInTheDocument();
        expect(screen.getByText("Redis")).toBeInTheDocument();
    });

    it("does not let an older summary overwrite a later catalog read", async () => {
        const user = userEvent.setup();
        let finish!: (value: DiscoveryMetadata) => void;
        mockedGetDiscoveryMetadata.mockReturnValueOnce(new Promise(resolve => { finish = resolve; }));
        renderPage();
        await screen.findByText("Home Assistant");
        await user.type(screen.getByLabelText("Keyword search"), "redis");
        await user.click(screen.getByRole("button", { name: /^Search$/ }));
        await screen.findByText("Catalog loaded");
        await act(async () => finish(metadata({ entry_count: 999 })));
        expect(screen.queryByText("999")).not.toBeInTheDocument();
        expect(screen.getByText("2")).toBeInTheDocument();
    });

    it("renders catalog status, disclaimer, and read-only item cards", async () => {
        renderPage();

        expect(await screen.findByText("Home Assistant")).toBeInTheDocument();
        expect(screen.getByText("Catalog loaded")).toBeInTheDocument();
        expect(screen.getByText("2")).toBeInTheDocument();
        expect(screen.getByRole("heading", { name: "Browse the catalog" })).toBeVisible();
        expect(screen.getByText("v1")).not.toBeVisible();
        fireEvent.click(screen.getByText("Catalog details"));
        expect(screen.getByText("v1")).toBeVisible();
        expect(
            screen.getByText(/does not mean compatibility, support, installability/i),
        ).toBeInTheDocument();
        expect(screen.getAllByText("home-automation").length).toBeGreaterThan(0);
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
        expect(screen.getByLabelText("Item type")).not.toBeVisible();
        await user.click(screen.getByText("More filters"));
        await user.type(screen.getByLabelText("Keyword search"), "ollama");
        expect(screen.getByText("Search to apply your changes.")).toBeVisible();
        expect(screen.queryByText("Filters applied to these results.")).not.toBeInTheDocument();
        await user.selectOptions(screen.getByLabelText("Item type"), "service");
        await user.selectOptions(screen.getByLabelText("Status"), "active");
        await user.type(screen.getByLabelText("Tag"), "ai");
        await user.type(screen.getByLabelText("Capability"), "llm-inference");
        await user.click(screen.getByRole("button", { name: "Search" }));

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
        expect(await screen.findByText("Filters applied to these results.")).toBeVisible();
        expect(screen.queryByText("Search to apply your changes.")).not.toBeInTheDocument();
        await user.click(screen.getByText("More filters"));
        expect(screen.getByLabelText("Item type")).not.toBeVisible();
        expect(screen.getByText("Filters applied to these results.")).toBeVisible();
    });

    it("uses item listing when submitted query is empty", async () => {
        const user = userEvent.setup();
        renderPage();

        await screen.findByText("Home Assistant");
        await user.click(screen.getByText("More filters"));
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
        expect(mockedSearchDiscoveryItems).not.toHaveBeenCalled();
    });

    it("resets offset when filters are cleared and respects pagination buttons", async () => {
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
        await user.click(screen.getByRole("button", { name: "Next Discovery results page" }));

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

        await user.click(screen.getByRole("button", { name: "Clear Discovery filters" }));
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
        const user = userEvent.setup();
        mockedGetDiscoveryMetadata.mockResolvedValue(metadata({ entry_count: 0 }));
        mockedListDiscoveryItems.mockResolvedValue(page([]));

        renderPage();

        expect(
            await screen.findByText("The Discovery catalog is loaded but empty."),
        ).toBeInTheDocument();
        expect(screen.getByText("Catalog empty")).toBeInTheDocument();
        expect(screen.getByText("Check again after entries have been added to the catalog.")).toBeVisible();
        expect(screen.queryByText("Try clearing filters or using a broader keyword.")).not.toBeInTheDocument();
        mockedGetDiscoveryMetadata.mockResolvedValue(metadata({ catalog_loaded: false, entry_count: 0 }));
        await user.click(screen.getByRole("button", { name: "Clear Discovery filters" }));
        expect(await screen.findByText("The Discovery catalog is unavailable.")).toBeVisible();
        expect(screen.queryByText("No Discovery items matched these filters.")).not.toBeInTheDocument();
    });

    it("keeps items visible when the summary fails and retries only the summary", async () => {
        const user = userEvent.setup();
        mockedGetDiscoveryMetadata.mockRejectedValueOnce(new Error("private-summary-error"));
        renderPage();
        expect(await screen.findByText("Home Assistant")).toBeInTheDocument();
        const alert = await screen.findByRole("alert");
        expect(within(alert).getByText("Catalog summary unavailable. Item results are shown separately.")).toBeInTheDocument();
        expect(document.body.textContent).not.toContain("private-summary-error");
        expect(screen.queryByText("Discovery catalog unavailable")).not.toBeInTheDocument();
        await user.click(screen.getByRole("button", { name: "Retry catalog summary" }));
        expect(await screen.findByText("Catalog loaded")).toBeInTheDocument();
        expect(screen.queryByRole("alert")).not.toBeInTheDocument();
        expect(mockedGetDiscoveryMetadata).toHaveBeenCalledTimes(2);
        expect(mockedListDiscoveryItems).toHaveBeenCalledTimes(1);
    });

    it("shows items and allows searching while the catalog summary is still pending", async () => {
        let finish!: (value: DiscoveryMetadata) => void;
        mockedGetDiscoveryMetadata.mockReturnValueOnce(new Promise(resolve => { finish = resolve; }));
        renderPage();
        expect(await screen.findByText("Home Assistant")).toBeInTheDocument();
        expect(screen.getByRole("button", { name: /^Search$/ })).toBeEnabled();
        expect(screen.getByText("Loading catalog summary")).toBeInTheDocument();
        await act(async () => finish(metadata()));
        expect(screen.getByText("Catalog loaded")).toBeInTheDocument();
    });
});
