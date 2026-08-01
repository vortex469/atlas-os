import { render, screen, within } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { getDiscoveryItem, getDiscoveryRelationships } from "../api/discovery";
import type {
    DiscoveryCatalogEntry,
    DiscoveryRelationshipCollection,
} from "../types/discovery";
import { DiscoveryItemPage } from "./DiscoveryItemPage";

vi.mock("../api/atlas", () => ({
    getAtlasErrorMessage: (error: unknown, fallback: string) =>
        error instanceof Error ? error.message : fallback,
}));

vi.mock("../api/discovery", () => ({
    getDiscoveryItem: vi.fn(),
    getDiscoveryRelationships: vi.fn(),
}));

const mockedGetDiscoveryItem = vi.mocked(getDiscoveryItem);
const mockedGetDiscoveryRelationships = vi.mocked(getDiscoveryRelationships);

function entry(overrides: Partial<DiscoveryCatalogEntry> = {}): DiscoveryCatalogEntry {
    return {
        schema_version: 1,
        item: {
            id: "frigate",
            type: "application",
            status: "active",
            name: "Frigate",
            description: "Network video recorder with local object detection.",
            version: null,
            aliases: [],
            tags: ["nvr", "video"],
            homepage_url: null,
            documentation_url: null,
            capabilities: ["video-ingest", "object-detection"],
            requirements: {
                capabilities: [{ id: "container-orchestration" }],
                resources: { gpu_required: false },
                platform: {
                    architectures: [],
                    operating_systems: [],
                    runtimes: ["docker"],
                    devices: [],
                },
                network: {
                    ports: [
                        {
                            port: 8971,
                            protocol: "tcp",
                            direction: "inbound",
                            required: false,
                            description: "Common Frigate web interface port.",
                        },
                    ],
                },
            },
            relationships: [],
            metadata: { catalog_notes: ["Ignored item metadata note."] },
        },
        provenance: {
            source_type: "curated",
            source: "atlas-curated-discovery-catalog",
            entry_id: "d5-frigate",
            version: null,
            trust_level: "curated",
        },
        metadata: {
            reviewed_for_d5: true,
            catalog_notes: ["Hardware acceleration is optional."],
        },
        ...overrides,
    };
}

function relationships(): DiscoveryRelationshipCollection {
    return {
        item_id: "frigate",
        incoming: [
            {
                source_item_id: "mission-control",
                target: "frigate",
                resolved_target_item_id: "frigate",
                resolved: true,
                relationship: {
                    type: "integrates_with",
                    target: "frigate",
                    required: false,
                    minimum_version: null,
                    maximum_version: null,
                    description: "Displays catalog facts.",
                    metadata: {},
                },
            },
        ],
        outgoing: [
            {
                source_item_id: "frigate",
                target: "mqtt",
                resolved_target_item_id: "mqtt",
                resolved: true,
                relationship: {
                    type: "integrates_with",
                    target: "mqtt",
                    required: false,
                    minimum_version: null,
                    maximum_version: null,
                    description: "Can publish events.",
                    metadata: {},
                },
            },
            {
                source_item_id: "frigate",
                target: "future-accelerator",
                resolved_target_item_id: null,
                resolved: false,
                relationship: {
                    type: "requires",
                    target: "future-accelerator",
                    required: false,
                    minimum_version: null,
                    maximum_version: null,
                    description: "Optional unresolved future accelerator.",
                    metadata: {},
                },
            },
        ],
    };
}

function renderPage(path = "/discovery/items/frigate") {
    return render(
        <MemoryRouter initialEntries={[path]}>
            <Routes>
                <Route path="/discovery/items/:itemId" element={<DiscoveryItemPage />} />
            </Routes>
        </MemoryRouter>,
    );
}

describe("DiscoveryItemPage", () => {
    beforeEach(() => {
        vi.resetAllMocks();
        mockedGetDiscoveryItem.mockResolvedValue(entry());
        mockedGetDiscoveryRelationships.mockResolvedValue(relationships());
    });

    it("renders item details, requirements, provenance, and approved metadata", async () => {
        renderPage();

        expect(await screen.findByRole("heading", { name: "Frigate" })).toBeInTheDocument();
        expect(screen.getByText("Application")).toBeInTheDocument();
        expect(screen.getByText("Active")).toBeInTheDocument();
        expect(screen.getByText("video-ingest")).toBeInTheDocument();
        expect(screen.getByText("nvr")).toBeInTheDocument();
        expect(screen.getByText("Runtime: docker")).toBeInTheDocument();
        expect(screen.getByText(/TCP 8971 inbound optional/i)).toBeInTheDocument();
        expect(screen.getByText("atlas-curated-discovery-catalog")).toBeInTheDocument();
        expect(screen.getByText("Reviewed for D5: Yes")).toBeInTheDocument();
        expect(screen.getByText("Hardware acceleration is optional.")).toBeInTheDocument();
        expect(screen.queryByText("Ignored item metadata note.")).not.toBeInTheDocument();
        expect(screen.queryByRole("button", { name: /install/i })).not.toBeInTheDocument();
    });

    it("renders incoming and outgoing relationships separately with links and labels", async () => {
        renderPage();

        const outgoing = await screen.findByRole("heading", {
            name: "Outgoing relationships",
        });
        const outgoingPanel = outgoing.closest("section");
        expect(outgoingPanel).not.toBeNull();
        expect(within(outgoingPanel!).getByRole("link", { name: "mqtt" })).toHaveAttribute(
            "href",
            "/discovery/items/mqtt",
        );
        expect(within(outgoingPanel!).getAllByText("Optional")).toHaveLength(2);
        expect(within(outgoingPanel!).getByText("Unresolved")).toBeInTheDocument();

        const incoming = screen.getByRole("heading", {
            name: "Incoming relationships",
        });
        const incomingPanel = incoming.closest("section");
        expect(incomingPanel).not.toBeNull();
        expect(within(incomingPanel!).getByText("Displays catalog facts.")).toBeInTheDocument();
    });

    it("renders empty relationship states", async () => {
        mockedGetDiscoveryRelationships.mockResolvedValue({
            item_id: "frigate",
            incoming: [],
            outgoing: [],
        });

        renderPage();

        expect(await screen.findByText("No outgoing relationships.")).toBeInTheDocument();
        expect(screen.getByText("No incoming relationships.")).toBeInTheDocument();
    });

    it("renders not found state", async () => {
        mockedGetDiscoveryItem.mockRejectedValue(new Error("Discovery item not found"));

        renderPage();

        expect(
            await screen.findByRole("heading", { name: "Discovery item not found" }),
        ).toBeInTheDocument();
        expect(screen.getByText(/could not find a catalog entry/i)).toBeInTheDocument();
    });

    it("renders unavailable state", async () => {
        mockedGetDiscoveryItem.mockRejectedValue(new Error("Catalog unavailable"));

        renderPage();

        const alert = await screen.findByRole("alert");
        expect(within(alert).getByText("Discovery catalog unavailable")).toBeInTheDocument();
        expect(within(alert).getByText("Catalog unavailable")).toBeInTheDocument();
    });
});
