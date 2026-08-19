import { render, screen, within } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import {
    getDiscoveryCompatibility,
    getDiscoveryItemEvidence,
    getDiscoveryItem,
    getDiscoveryRelationships,
    listDiscoveryProposals,
} from "../api/discovery";
import type {
    DiscoveryCatalogEntry,
    DiscoveryCompatibilityAssessment,
    DiscoveryItemEvidence,
    DiscoveryRelationshipCollection,
    DiscoveryProposalNavigation,
} from "../types/discovery";
import { DiscoveryItemPage } from "./DiscoveryItemPage";

vi.mock("../api/atlas", () => ({
    getAtlasErrorMessage: (error: unknown, fallback: string) =>
        error instanceof Error ? error.message : fallback,
}));

vi.mock("../api/discovery", () => ({
    getDiscoveryItem: vi.fn(),
    getDiscoveryRelationships: vi.fn(),
    getDiscoveryCompatibility: vi.fn(),
    getDiscoveryItemEvidence: vi.fn(),
    listDiscoveryProposals: vi.fn(),
}));

const mockedGetDiscoveryItem = vi.mocked(getDiscoveryItem);
const mockedGetDiscoveryRelationships = vi.mocked(getDiscoveryRelationships);
const mockedGetDiscoveryCompatibility = vi.mocked(getDiscoveryCompatibility);
const mockedGetDiscoveryItemEvidence = vi.mocked(getDiscoveryItemEvidence);
const mockedListDiscoveryProposals = vi.mocked(listDiscoveryProposals);

const compatibilityAssessment = (
    overrides: Partial<DiscoveryCompatibilityAssessment> = {},
): DiscoveryCompatibilityAssessment => ({
    item_id: "frigate",
    target_id: "atlas",
    target_type: "atlas_environment",
    status: "compatible",
    checked_at: "2026-08-05T18:00:00.000Z",
    findings: [
        {
            id: "f0001",
            check_type: "catalog",
            severity: "info",
            status: "compatible",
            subject: "item.status",
            message: "Catalog item status is active.",
            evidence_ids: ["e0001"],
        },
    ],
    evidence: [
        {
            id: "e0001",
            check_type: "catalog",
            subject: "item.status",
            status: "compatible",
            message: "Catalog item status is active.",
            source: "catalog",
            requirement: "active",
            observed: "active",
            observed_fact_id: null,
        },
    ],
    unknown_facts: [],
    ...overrides,
});

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

function proposal(): DiscoveryProposalNavigation {
    return {
        proposal_id: `discovery-operator-proposal-${"b".repeat(64)}`,
        destination_kind: "discovery_detail",
        catalog_item_id: "frigate",
        catalog_source_type: "curated",
        compatibility_status: "compatible",
        finding_reference_count: 0,
        evidence_reference_count: 1,
        status: "current",
        reason: "compatible",
        intent_hint: null,
        target_hints: [{ catalog_target_id: "atlas" }],
        generated_at: "2026-08-15T00:00:00Z",
        expires_at: "2026-08-15T00:30:00Z",
        actionable_navigation: false,
    };
}

function itemEvidence(): DiscoveryItemEvidence {
    return {
        schema_version: "discovery-merged-item-v1",
        catalog_item_id: "frigate",
        curated: entry(),
        dynamic_claims: [],
        source_states: [{
            source_id: "frigate-github-latest-release-v1",
            health: null,
            cache_state: "absent",
        }],
        conflict_state: "none",
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
        mockedGetDiscoveryCompatibility.mockResolvedValue(compatibilityAssessment());
        mockedGetDiscoveryItemEvidence.mockResolvedValue(itemEvidence());
        mockedListDiscoveryProposals.mockResolvedValue({ proposals: [], total: 0, limit: 25 });
    });

    it("renders item details, requirements, provenance, approved metadata, and compatibility", async () => {
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

        expect(screen.getByRole("heading", { name: "Compatibility status" })).toBeInTheDocument();
        expect(screen.getByText("Compatible")).toBeInTheDocument();
        expect(screen.getByText("Catalog item status is active.")).toBeInTheDocument();
        expect(screen.getByText("Code: f0001")).toBeInTheDocument();
        expect(screen.getByText("Evidence e0001")).toBeInTheDocument();
        expect(mockedGetDiscoveryCompatibility).toHaveBeenCalledWith("frigate");
    });

    it("loads a bounded related proposal section", async () => {
        mockedListDiscoveryProposals.mockResolvedValue({
            proposals: [proposal(), { ...proposal(), proposal_id: `discovery-operator-proposal-${"c".repeat(64)}`, catalog_item_id: "other" }],
            total: 2,
            limit: 25,
        });
        renderPage();
        expect(await screen.findByRole("heading", { name: "Operator proposals" })).toBeInTheDocument();
        expect(await screen.findByText("Advisory proposal")).toBeInTheDocument();
        expect(mockedListDiscoveryProposals).toHaveBeenCalledWith(25);
        expect(screen.queryByText("other")).not.toBeInTheDocument();
    });

    it("composes read-only evidence without granting mutation or execution controls", async () => {
        mockedGetDiscoveryItemEvidence.mockResolvedValue({
            ...itemEvidence(),
            dynamic_claims: [{
                fact_kind: "latest_stable_release",
                version: "0.16.1",
                published_at: "2026-08-17T09:00:00Z",
                freshness: "fresh",
                provenance: {
                    source_id: "frigate-github-latest-release-v1",
                    source_type: "github_latest_release",
                    trust_tier: "supplemental",
                    repository: "blakeblackshear/frigate",
                    upstream_release_id: 123,
                    retrieved_at: "2026-08-18T09:00:00Z",
                    expires_at: "2026-08-19T09:00:00Z",
                },
            }],
            source_states: [{
                source_id: "frigate-github-latest-release-v1",
                health: "healthy",
                cache_state: "available",
            }],
            conflict_state: "agreement",
        });

        renderPage();

        expect(await screen.findByRole("heading", { name: "Release evidence" })).toBeInTheDocument();
        expect(await screen.findByText("Release 0.16.1")).toBeInTheDocument();
        expect(mockedGetDiscoveryItemEvidence).toHaveBeenCalledWith("frigate");
        expect(screen.queryByRole("button", { name: /apply|execute|fix|remediate|refresh/i })).not.toBeInTheDocument();
    });

    it("keeps curated item content usable when evidence is offline", async () => {
        mockedGetDiscoveryItemEvidence.mockRejectedValue(new Error("Evidence service offline"));

        renderPage();

        expect(await screen.findByRole("heading", { name: "Frigate" })).toBeInTheDocument();
        expect(await screen.findByText("Dynamic evidence unavailable")).toBeInTheDocument();
        expect(screen.getByText(/Showing the curated catalog only/i)).toBeInTheDocument();
        expect(screen.getByText("atlas-curated-discovery-catalog")).toBeInTheDocument();
    });

    it("distinguishes proposal transport failure from provider state", async () => {
        mockedListDiscoveryProposals.mockRejectedValue(new Error("transport unavailable"));
        renderPage();
        expect(await screen.findByRole("alert")).toHaveTextContent("Proposal context is temporarily unavailable");
        expect(screen.getByText(/provider state were not affected/i)).toBeInTheDocument();
    });

    it.each([
        { status: "compatible", expected: "Compatible" },
        { status: "compatible_with_warnings", expected: "Compatible With Warnings" },
        { status: "insufficient_information", expected: "Insufficient Information" },
        { status: "incompatible", expected: "Incompatible" },
    ])("shows status presentation for %s", async ({ status, expected }) => {
        mockedGetDiscoveryCompatibility.mockResolvedValue(
            compatibilityAssessment({ status: status as DiscoveryCompatibilityAssessment["status"] }),
        );

        renderPage();

        expect(await screen.findByRole("heading", { name: "Compatibility status" })).toBeInTheDocument();
        expect(await screen.findByText(expected)).toBeInTheDocument();
    });

    it("shows findings grouped by backend severity and unknown facts", async () => {
        mockedGetDiscoveryCompatibility.mockResolvedValue(
            compatibilityAssessment({
                findings: [
                    {
                        id: "f0001",
                        check_type: "resource",
                        severity: "warning",
                        status: "compatible_with_warnings",
                        subject: "requirements.resources.memory_mb_min",
                        message: "Memory is borderline.",
                        evidence_ids: ["e0001", "e0002"],
                    },
                    {
                        id: "f0002",
                        check_type: "network",
                        severity: "blocker",
                        status: "incompatible",
                        subject: "requirements.network.ports.tcp.443.inbound",
                        message: "Required port is missing.",
                        evidence_ids: ["e0002"],
                    },
                ],
                evidence: [
                    {
                        id: "e0001",
                        check_type: "resource",
                        subject: "requirements.resources.memory_mb_min",
                        status: "compatible_with_warnings",
                        message: "Memory check.",
                        source: "compatibility_context",
                    },
                    {
                        id: "e0002",
                        check_type: "network",
                        subject: "requirements.network.ports.tcp.443.inbound",
                        status: "incompatible",
                        message: "Port check.",
                        source: "compatibility_context",
                    },
                ],
                unknown_facts: ["open_ports", "installed_services"],
            }),
        );

        renderPage();

        expect(await screen.findByText("Findings Warning")).toBeInTheDocument();
        expect(await screen.findByText("Findings Blocker")).toBeInTheDocument();
        expect(screen.getByText("Memory is borderline.")).toBeInTheDocument();
        expect(screen.getByText("Required port is missing.")).toBeInTheDocument();
        expect(screen.getAllByText("Evidence e0002")).toHaveLength(2);
        expect(screen.getAllByText((content) => content.includes("Port check"))).toHaveLength(2);
        expect(screen.getByText("open_ports")).toBeInTheDocument();
        expect(screen.getByText("installed_services")).toBeInTheDocument();
    });

    it("renders compatibility loading state independently", async () => {
        let compatibilityPromise: Promise<DiscoveryCompatibilityAssessment> | undefined;
        let resolveCompatibility: ((value: DiscoveryCompatibilityAssessment) => void) | undefined;
        mockedGetDiscoveryCompatibility.mockImplementation(
            () =>
                (compatibilityPromise = new Promise<DiscoveryCompatibilityAssessment>((resolve) => {
                    resolveCompatibility = resolve;
                })),
        );

        renderPage();

        expect(await screen.findByText("Loading compatibility assessment…")).toBeInTheDocument();
        expect(screen.getByRole("heading", { name: "Compatibility assessment" })).toBeInTheDocument();
        expect(screen.getByRole("heading", { name: "Frigate" })).toBeInTheDocument();

        expect(compatibilityPromise).toBeDefined();
        expect(resolveCompatibility).toBeDefined();
        resolveCompatibility!(compatibilityAssessment());
        expect(await screen.findByText("Compatible")).toBeInTheDocument();
    });

    it("shows compatibility failure without replacing the full item page", async () => {
        mockedGetDiscoveryCompatibility.mockRejectedValue(
            new Error("Temporary compatibility backend failure"),
        );

        renderPage();

        expect(await screen.findByRole("heading", { name: "Frigate" })).toBeInTheDocument();
        expect(await screen.findByText("Compatibility unavailable")).toBeInTheDocument();
        expect(screen.getByText("Retry compatibility check")).toBeInTheDocument();
        expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    });

    it("renders empty compatibility findings, evidence, and unknown facts", async () => {
        mockedGetDiscoveryCompatibility.mockResolvedValue(
            compatibilityAssessment({ findings: [], evidence: [], unknown_facts: [] }),
        );

        renderPage();

        expect(await screen.findByText("No findings were reported.")).toBeInTheDocument();
        expect(screen.getByText("Target ID")).toBeInTheDocument();
        expect(screen.getByText("atlas_environment")).toBeInTheDocument();
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
