import { render, screen, waitFor, within } from "@testing-library/react";
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

    it("renders catalog status, disclaimer, and read-only item cards", async () => {
        renderPage();

        expect(await screen.findByText("Home Assistant")).toBeInTheDocument();
        expect(screen.getByText("Catalog loaded")).toBeInTheDocument();
        expect(screen.getByText("2")).toBeInTheDocument();
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
        await user.type(screen.getByLabelText("Keyword search"), "ollama");
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
        mockedGetDiscoveryMetadata.mockResolvedValue(metadata({ entry_count: 0 }));
        mockedListDiscoveryItems.mockResolvedValue(page([]));

        renderPage();

        expect(
            await screen.findByText("The Discovery catalog is loaded but empty."),
        ).toBeInTheDocument();
        expect(screen.getByText("Catalog empty")).toBeInTheDocument();
    });

    it("shows a recoverable unavailable state", async () => {
        mockedGetDiscoveryMetadata.mockRejectedValue(new Error("Catalog unavailable"));

        renderPage();

        const alert = await screen.findByRole("alert");
        expect(within(alert).getByText("Discovery catalog unavailable")).toBeInTheDocument();
        expect(within(alert).getByText("Catalog unavailable")).toBeInTheDocument();
    });
});
