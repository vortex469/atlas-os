import { act, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { createMemoryRouter, MemoryRouter, Route, RouterProvider, Routes, useNavigate } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import {
    getDiscoveryCompatibility,
    getDiscoveryItemEvidence,
    getDiscoveryImageGrounding,
    getDiscoveryInstallationPlan,
    getDiscoveryItem,
    getDiscoveryRelationships,
    listDiscoveryProposals,
} from "../api/discovery";
import type {
    DiscoveryCatalogEntry,
    DiscoveryCompatibilityAssessment,
    DiscoveryItemEvidence,
    DiscoveryImageGroundingProjection,
    DiscoveryRelationshipCollection,
    DiscoveryProposalNavigation,
} from "../types/discovery";
import type { InstallationPlan } from "../types/installationPlan";
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
    getDiscoveryImageGrounding: vi.fn(),
    getDiscoveryInstallationPlan: vi.fn(),
    listDiscoveryProposals: vi.fn(),
}));

const mockedGetDiscoveryItem = vi.mocked(getDiscoveryItem);
const mockedGetDiscoveryRelationships = vi.mocked(getDiscoveryRelationships);
const mockedGetDiscoveryCompatibility = vi.mocked(getDiscoveryCompatibility);
const mockedGetDiscoveryItemEvidence = vi.mocked(getDiscoveryItemEvidence);
const mockedGetDiscoveryImageGrounding = vi.mocked(getDiscoveryImageGrounding);
const mockedGetDiscoveryInstallationPlan = vi.mocked(getDiscoveryInstallationPlan);
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

function imageGrounding(): DiscoveryImageGroundingProjection {
    return {
        schema_version: "discovery-image-grounding-projection-v1",
        catalog_item_id: "frigate",
        status: "no_deployment_binding",
        release_version: null,
        deployment_binding: null,
        observed_image: null,
        accepted_evidence: [],
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

function installationPlan(itemId: string): InstallationPlan {
    return {
        schema_version: "installation-plan-v1",
        fingerprint: { algorithm: "sha256", canonicalization: "atlas-jcs-nfc-v1", value: itemId.padEnd(64, "0") },
        application: { item_id: itemId, catalog_entry_id: `catalog-${itemId}`, display_name: `${itemId} plan details`, release_version: null },
        status: "missing_deployment_artifact",
        deployment_artifact: { state: "missing", kind: "docker-compose", repository_path: null, service: null, content_digest: null },
        image: { state: "missing", reference: null, digest: null, release_version: null },
        accepted_evidence: [],
        provenance: [],
        compatibility: [{ environment: "item-scoped", result: "unknown", reason_code: "compatibility_fact_missing" }],
        prerequisites: [], relationships: [], assumptions: [],
        blockers: [{ code: "missing_deployment_artifact", subject: itemId }],
        risks: [], missing_facts: [{ code: "deployment_artifact", subject: itemId }],
        required_operator_confirmations: [],
    };
}

function deferred<T>() {
    let resolve!: (value: T) => void;
    let reject!: (reason?: unknown) => void;
    const promise = new Promise<T>((resolvePromise, rejectPromise) => {
        resolve = resolvePromise;
        reject = rejectPromise;
    });
    return { promise, resolve, reject };
}

function RouteDriver() {
    const navigate = useNavigate();
    return <button onClick={() => navigate("/discovery/items/item-b")}>Show item B</button>;
}

function renderNavigablePage() {
    mockedGetDiscoveryItem.mockImplementation(async (id) => ({ ...entry(), item: { ...entry().item, id } }));
    mockedGetDiscoveryRelationships.mockImplementation(async (item_id) => ({ ...relationships(), item_id }));
    mockedGetDiscoveryCompatibility.mockImplementation(async (item_id) => compatibilityAssessment({ item_id }));
    mockedGetDiscoveryItemEvidence.mockImplementation(async (catalog_item_id) => ({ ...itemEvidence(), catalog_item_id, curated: { ...entry(), item: { ...entry().item, id: catalog_item_id } } }));
    mockedGetDiscoveryImageGrounding.mockImplementation(async (catalog_item_id) => ({ ...imageGrounding(), catalog_item_id }));
    return render(
        <MemoryRouter initialEntries={["/discovery/items/item-a"]}>
            <RouteDriver />
            <Routes><Route path="/discovery/items/:itemId" element={<DiscoveryItemPage />} /></Routes>
        </MemoryRouter>,
    );
}

function httpError(status: number, detail: string) {
    return {
        isAxiosError: true,
        message: detail,
        response: { status, data: { error: { message: detail } } },
    };
}

describe("DiscoveryItemPage", () => {
    it("clears the previous item's details as soon as the URL changes", async () => {
        const nextRequest = deferred<DiscoveryCatalogEntry>();
        mockedGetDiscoveryItem.mockResolvedValueOnce(entry()).mockReturnValueOnce(nextRequest.promise);
        mockedGetDiscoveryRelationships.mockImplementation(async (item_id) => ({ ...relationships(), item_id }));
        const router = createMemoryRouter([{ path: "/discovery/items/:itemId", element: <DiscoveryItemPage /> }], { initialEntries: ["/discovery/items/frigate"] });
        render(<RouterProvider router={router} />);
        await screen.findByRole("heading", { name: "Frigate" });
        await act(() => router.navigate("/discovery/items/next-item"));
        expect(screen.queryByRole("heading", { name: "Frigate" })).not.toBeInTheDocument();
        expect(screen.getByText("Loading catalog item…")).toBeInTheDocument();
        await act(async () => nextRequest.resolve({ ...entry(), item: { ...entry().item, id: "next-item", name: "Next item" } }));
        expect(await screen.findByRole("heading", { name: "Next item" })).toBeInTheDocument();
        expect(screen.queryByRole("heading", { name: "Frigate" })).not.toBeInTheDocument();
    });

    it("refuses catalog data for a different item", async () => {
        mockedGetDiscoveryItem
            .mockResolvedValueOnce({ ...entry(), item: { ...entry().item, id: "other" } })
            .mockResolvedValueOnce(entry());
        renderPage();
        expect(await screen.findByRole("alert")).toHaveTextContent("does not match this item");
        expect(screen.queryByRole("heading", { name: "Frigate" })).not.toBeInTheDocument();
        await userEvent.setup().click(screen.getByRole("button", { name: "Try again" }));
        expect(await screen.findByRole("heading", { name: "Frigate" })).toBeInTheDocument();
        expect(mockedGetDiscoveryItem).toHaveBeenCalledTimes(2);
    });

    it("does not show relationships returned for a different catalog item", async () => {
        mockedGetDiscoveryRelationships.mockResolvedValue({ ...relationships(), item_id: "other" });
        renderPage();

        expect(await screen.findByRole("heading", { name: "Frigate" })).toBeInTheDocument();
        const section = screen.getByRole("region", { name: "Catalog relationships" });
        expect(await within(section).findByRole("alert")).toHaveTextContent("Relationships unavailable");
        expect(screen.queryByRole("link", { name: "mqtt" })).not.toBeInTheDocument();
        expect(screen.queryByText(/— other/)).not.toBeInTheDocument();
        expect(within(section).getByRole("button", { name: "Retry relationships" })).toBeInTheDocument();
    });

    it.each(["compatibility", "evidence", "grounding", "plan"])("does not display unrelated %s evidence", async (source) => {
        if (source === "compatibility") mockedGetDiscoveryCompatibility.mockResolvedValue(compatibilityAssessment({ item_id: "other" }));
        if (source === "evidence") mockedGetDiscoveryItemEvidence.mockResolvedValue({ ...itemEvidence(), catalog_item_id: "other" });
        if (source === "grounding") mockedGetDiscoveryImageGrounding.mockResolvedValue({ ...imageGrounding(), catalog_item_id: "other" });
        if (source === "plan") mockedGetDiscoveryInstallationPlan.mockResolvedValue(installationPlan("other"));
        renderPage();
        await screen.findByRole("heading", { name: "Frigate" });
        const message = source === "compatibility" ? "Could not check compatibility" : source === "evidence" ? "Release information unavailable" : source === "grounding" ? "The image check is unavailable right now." : "Installation plan is currently unavailable.";
        expect(await screen.findByText(message)).toBeInTheDocument();
        expect(screen.queryByText(/— other/)).not.toBeInTheDocument();
    });

    it("keeps catalog details available and retries a failed relationships read", async () => {
        mockedGetDiscoveryRelationships.mockRejectedValueOnce(httpError(404, "Relationships not found"))
            .mockResolvedValueOnce(relationships());
        renderPage();
        expect(await screen.findByRole("heading", { name: "Frigate" })).toBeInTheDocument();
        expect(screen.queryByRole("heading", { name: "Catalog item not found" })).not.toBeInTheDocument();
        const section = screen.getByRole("region", { name: "Catalog relationships" });
        expect(await within(section).findByRole("alert")).toHaveTextContent("The catalog item is available, but its related items could not be checked.");
        expect(within(section).queryByText("No links from this item.")).not.toBeInTheDocument();
        await userEvent.setup().click(within(section).getByRole("button", { name: "Retry relationships" }));
        expect(await within(section).findByRole("heading", { name: "Links from this item" })).toBeInTheDocument();
        expect(within(section).getByRole("link", { name: "mqtt" })).toBeInTheDocument();
        expect(mockedGetDiscoveryRelationships).toHaveBeenCalledTimes(2);
        expect(mockedGetDiscoveryItem).toHaveBeenCalledTimes(1);
    });

    it("does not infer a missing item from error prose", async () => {
        mockedGetDiscoveryItem.mockRejectedValue(new Error("Proxy not found while reading catalog"));
        renderPage();
        const alert = await screen.findByRole("alert");
        expect(alert).toHaveTextContent("Mission Control could not load this catalog item. Its current details are unknown.");
        const technicalDetails = within(alert).getByText("Technical details").closest("details");
        expect(technicalDetails).not.toHaveAttribute("open");
        const readError = within(technicalDetails as HTMLDetailsElement).getByText("Proxy not found while reading catalog");
        expect(readError).not.toBeVisible();
        await userEvent.setup().click(within(technicalDetails as HTMLDetailsElement).getByText("Technical details"));
        expect(readError).toBeVisible();
        expect(screen.queryByRole("heading", { name: "Catalog item not found" })).not.toBeInTheDocument();
    });

    beforeEach(() => {
        vi.resetAllMocks();
        mockedGetDiscoveryItem.mockResolvedValue(entry());
        mockedGetDiscoveryRelationships.mockResolvedValue(relationships());
        mockedGetDiscoveryCompatibility.mockResolvedValue(compatibilityAssessment());
        mockedGetDiscoveryItemEvidence.mockResolvedValue(itemEvidence());
        mockedGetDiscoveryImageGrounding.mockResolvedValue(imageGrounding());
        mockedGetDiscoveryInstallationPlan.mockRejectedValue(new Error("Plan unavailable"));
        mockedListDiscoveryProposals.mockResolvedValue({ proposals: [], total: 0, limit: 25 });
    });

    it("renders item details, requirements, provenance, approved metadata, and compatibility", async () => {
        const user = userEvent.setup();
        renderPage();

        const itemHeading = await screen.findByRole("heading", { name: "Frigate" });
        const itemHeadingDetails = within(itemHeading.closest("div") as HTMLElement).getByText("Technical details").closest("details");
        expect(within(itemHeadingDetails as HTMLDetailsElement).getByText("Catalog item ID: frigate")).not.toBeVisible();
        await user.click(within(itemHeadingDetails as HTMLDetailsElement).getByText("Technical details"));
        expect(within(itemHeadingDetails as HTMLDetailsElement).getByText("Catalog item ID: frigate")).toBeVisible();
        expect(screen.getByText("Application")).toBeInTheDocument();
        expect(screen.getByText("Active")).toBeInTheDocument();
        expect(screen.getByRole("heading", { name: "What it supports" })).toBeInTheDocument();
        expect(screen.getByText("Video ingest")).toBeInTheDocument();
        expect(screen.getByText("Object detection")).toBeInTheDocument();
        expect(screen.getByText("nvr")).toBeInTheDocument();
        expect(screen.getByText("Runtime: docker")).toBeInTheDocument();
        expect(screen.getByText(/TCP 8971 inbound optional/i)).toBeInTheDocument();
        const sourceDetails = screen.getByText("Catalog source details").closest("details");
        expect(sourceDetails).not.toHaveAttribute("open");
        expect(within(sourceDetails as HTMLDetailsElement).getByText("atlas-curated-discovery-catalog")).not.toBeVisible();
        await user.click(within(sourceDetails as HTMLDetailsElement).getByText("Catalog source details"));
        expect(within(sourceDetails as HTMLDetailsElement).getByText("atlas-curated-discovery-catalog")).toBeVisible();
        expect(screen.getByText("Reviewed for D5: Yes")).toBeInTheDocument();
        expect(screen.getByText("Hardware acceleration is optional.")).toBeInTheDocument();
        expect(screen.queryByText("Ignored item metadata note.")).not.toBeInTheDocument();
        expect(screen.queryByRole("button", { name: /install/i })).not.toBeInTheDocument();

        expect(
            await screen.findByRole("heading", { name: "Compatibility summary" }),
        ).toBeInTheDocument();
        const summary = screen.getByRole("heading", { name: "Compatibility summary" }).closest("section");
        expect(within(summary as HTMLElement).getByText("Compatible")).toBeInTheDocument();
        expect(screen.getByText("Catalog item status is active.")).toBeInTheDocument();
        expect(screen.getByText("Checked against")).toBeInTheDocument();
        expect(within(summary as HTMLElement).getByText("Atlas Environment")).toBeInTheDocument();
        expect(screen.getByText("Last checked")).toBeInTheDocument();
        const checkTime = screen.getByText("Last checked").parentElement?.querySelector("time");
        expect(checkTime).toHaveAttribute("datetime", "2026-08-05T18:00:00.000Z");
        expect(checkTime).toHaveTextContent(new Date("2026-08-05T18:00:00.000Z").toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" }));
        expect(screen.queryByText("2026-08-05T18:00:00.000Z")).not.toBeVisible();
        const compatibilityDetails = within(summary as HTMLElement).getByText("Technical details").closest("details");
        expect(compatibilityDetails).not.toHaveAttribute("open");
        expect(within(compatibilityDetails as HTMLDetailsElement).getByText("atlas")).not.toBeVisible();
        await user.click(within(compatibilityDetails as HTMLDetailsElement).getByText("Technical details"));
        expect(within(compatibilityDetails as HTMLDetailsElement).getByText("atlas")).toBeVisible();
        const finding = screen.getByText("Catalog item status is active.").closest("article");
        const technicalDetails = within(finding as HTMLElement).getByText("Evidence details").closest("details");
        expect(technicalDetails).not.toHaveAttribute("open");
        expect(within(technicalDetails as HTMLDetailsElement).getByText("Finding code: f0001")).not.toBeVisible();
        await user.click(within(technicalDetails as HTMLDetailsElement).getByText("Evidence details"));
        expect(within(technicalDetails as HTMLDetailsElement).getByText("Finding code: f0001")).toBeVisible();
        expect(within(technicalDetails as HTMLDetailsElement).getByText("Evidence e0001")).toBeVisible();
        expect(mockedGetDiscoveryCompatibility).toHaveBeenCalledWith("frigate");
        expect(await screen.findByRole("heading", { name: "Image check" })).toBeInTheDocument();
        expect(mockedGetDiscoveryImageGrounding).toHaveBeenCalledWith("frigate");
    });

    it("does not present malformed compatibility check time as verified local time", async () => {
        mockedGetDiscoveryCompatibility.mockResolvedValue(
            compatibilityAssessment({ checked_at: "2026-02-30T12:00:00Z" }),
        );
        renderPage();

        expect(await screen.findByText("Last checked")).toBeInTheDocument();
        const checkTime = screen.getByText("Last checked").parentElement;
        expect(checkTime).toHaveTextContent("Time unavailable");
        expect(checkTime?.querySelector("time")).toBeNull();
    });

    it("shows loading and failure without plan details", async () => {
        const request = deferred<InstallationPlan>();
        mockedGetDiscoveryInstallationPlan.mockReturnValueOnce(request.promise);
        renderPage();

        expect(await screen.findByText("Loading installation plan…")).toBeInTheDocument();
        expect(await screen.findByRole("heading", { name: "Frigate" })).toBeInTheDocument();
        await waitFor(() => expect(mockedGetDiscoveryInstallationPlan).toHaveBeenCalledWith("frigate"));
        expect(screen.queryByText(/— item-a/)).not.toBeInTheDocument();
        await act(async () => request.reject(new Error("unavailable")));
        expect(await screen.findByText("Installation plan is currently unavailable.")).toBeInTheDocument();
        expect(screen.queryByText(/— item-a/)).not.toBeInTheDocument();
    });

    it.each(["success", "failure"])(
        "never presents item A's plan as item B's plan when B ends in %s",
        async (outcome) => {
            const itemARequest = deferred<InstallationPlan>();
            const itemBRequest = deferred<InstallationPlan>();
            mockedGetDiscoveryInstallationPlan.mockImplementation((itemId) =>
                itemId === "item-a" ? itemARequest.promise : itemBRequest.promise,
            );
            renderNavigablePage();
            expect(await screen.findByRole("heading", { name: "Frigate" })).toBeInTheDocument();
            await waitFor(() => expect(mockedGetDiscoveryInstallationPlan).toHaveBeenCalledWith("item-a"));

            await act(async () => screen.getByRole("button", { name: "Show item B" }).click());
            expect(await screen.findByText("Loading installation plan…")).toBeInTheDocument();
            await waitFor(() => expect(mockedGetDiscoveryInstallationPlan).toHaveBeenCalledWith("item-b"));

            await act(async () => itemARequest.resolve(installationPlan("item-a")));
            expect(screen.queryByText(/— item-a/)).not.toBeInTheDocument();
            expect(screen.getByText("Loading installation plan…")).toBeInTheDocument();

            if (outcome === "success") {
                await act(async () => itemBRequest.resolve(installationPlan("item-b")));
                expect((await screen.findAllByText(/— item-b/)).length).toBeGreaterThan(0);
            } else {
                await act(async () => itemBRequest.reject(new Error("B unavailable")));
                expect(await screen.findByText("Installation plan is currently unavailable.")).toBeInTheDocument();
            }
            expect(screen.queryByText(/— item-a/)).not.toBeInTheDocument();
        },
    );

    it("loads a bounded related proposal section", async () => {
        mockedListDiscoveryProposals.mockResolvedValue({
            proposals: [proposal(), { ...proposal(), proposal_id: `discovery-operator-proposal-${"c".repeat(64)}`, catalog_item_id: "other" }],
            total: 2,
            limit: 25,
        });
        renderPage();
        expect(await screen.findByRole("heading", { name: "Suggestions" })).toBeInTheDocument();
        expect(await screen.findByText("Suggestion")).toBeInTheDocument();
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

    it("presents the bounded release evaluation without mutation or execution controls", async () => {
        mockedGetDiscoveryItemEvidence.mockResolvedValue({
            ...itemEvidence(),
            release_evaluation: {
                status: "update_available",
                baseline: { version: "0.15.0", source: "item_version" },
                latest_candidate: "0.16.1",
                reason: null,
            },
        });

        renderPage();

        expect(await screen.findByText("Version comparison")).toBeInTheDocument();
        expect(screen.getByText("Newer release reported")).toBeInTheDocument();
        expect(screen.getByText("0.15.0")).toBeInTheDocument();
        expect(screen.getByText("Item version")).toBeInTheDocument();
        expect(screen.getByText("0.16.1")).toBeInTheDocument();
        expect(
            screen.queryByRole("button", {
                name: /apply|update|execute|fix|remediate|restart|refresh|approve/i,
            }),
        ).not.toBeInTheDocument();
    });

    it("keeps curated item content usable when evidence is offline", async () => {
        mockedGetDiscoveryItemEvidence.mockRejectedValue(new Error("Evidence service offline"));

        renderPage();

        expect(await screen.findByRole("heading", { name: "Frigate" })).toBeInTheDocument();
        expect(await screen.findByText("Release information unavailable")).toBeInTheDocument();
        expect(screen.getByText("The catalog information is still available and unchanged.")).toBeInTheDocument();
        expect(screen.getByText("atlas-curated-discovery-catalog")).toBeInTheDocument();
    });

    it("retries source evidence without reloading the catalog item", async () => {
        const user = userEvent.setup();
        mockedGetDiscoveryItemEvidence.mockRejectedValueOnce(new Error("Evidence service offline"))
            .mockResolvedValueOnce(itemEvidence());

        renderPage();

        expect(await screen.findByText("Release information unavailable")).toBeInTheDocument();
        await user.click(screen.getByRole("button", { name: "Retry release check" }));

        expect(await screen.findByText("Only catalog information is available")).toBeInTheDocument();
        expect(mockedGetDiscoveryItemEvidence).toHaveBeenCalledTimes(2);
        expect(mockedGetDiscoveryItem).toHaveBeenCalledTimes(1);
    });

    it("retries temporary image-grounding failures without reloading the catalog item", async () => {
        const user = userEvent.setup();
        mockedGetDiscoveryImageGrounding.mockRejectedValueOnce(httpError(503, "Source temporarily unavailable"))
            .mockResolvedValueOnce(imageGrounding());

        renderPage();

        expect(await screen.findByText("Atlas could not finish checking the image. Try again.")).toBeInTheDocument();
        await user.click(screen.getByRole("button", { name: "Retry image check" }));

        const deploymentBindingLabels = await screen.findAllByText("No deployment mapping");
        expect(deploymentBindingLabels.some((element) => element.tagName === "P")).toBe(true);
        expect(mockedGetDiscoveryImageGrounding).toHaveBeenCalledTimes(2);
        expect(mockedGetDiscoveryItem).toHaveBeenCalledTimes(1);
    });

    it.each([
        [404, "No image check is available for this item."],
        [503, "Atlas could not finish checking the image. Try again."],
        [500, "The image check is unavailable right now."],
    ])("bounds image-grounding HTTP %s without exposing backend details", async (status, copy) => {
        mockedGetDiscoveryImageGrounding.mockRejectedValue(
            httpError(status, "SECRET token=hidden /private/repository"),
        );

        renderPage();

        expect(await screen.findByText(copy)).toBeInTheDocument();
        expect(screen.queryByText(/SECRET|token=hidden|private\/repository/)).not.toBeInTheDocument();
        expect(screen.getByRole("heading", { name: "Frigate" })).toBeInTheDocument();
    });

    it("distinguishes proposal transport failure from provider state", async () => {
        mockedListDiscoveryProposals.mockRejectedValue(new Error("transport unavailable"));
        renderPage();
        expect(await screen.findByRole("alert")).toHaveTextContent("Suggestions are temporarily unavailable");
        expect(screen.getByText(/catalog item is still available/i)).toBeInTheDocument();
    });

    it("retries the related proposal read without reloading the catalog item", async () => {
        const user = userEvent.setup();
        mockedListDiscoveryProposals.mockRejectedValueOnce(new Error("Proposal service unavailable"))
            .mockResolvedValueOnce({ proposals: [], total: 0, limit: 25 });

        renderPage();

        expect(await screen.findByRole("alert")).toHaveTextContent("Suggestions are temporarily unavailable");
        await user.click(screen.getByRole("button", { name: "Retry suggestions" }));

        expect(await screen.findByText("No suggestions are available.")).toBeInTheDocument();
        expect(mockedListDiscoveryProposals).toHaveBeenCalledTimes(2);
        expect(mockedGetDiscoveryItem).toHaveBeenCalledTimes(1);
    });

    it.each([
        { status: "compatible", expected: "Compatible" },
        { status: "compatible_with_warnings", expected: "Compatible with warnings" },
        { status: "insufficient_information", expected: "Not enough information" },
        { status: "incompatible", expected: "Not compatible" },
    ])("shows status presentation for %s", async ({ status, expected }) => {
        mockedGetDiscoveryCompatibility.mockResolvedValue(
            compatibilityAssessment({ status: status as DiscoveryCompatibilityAssessment["status"] }),
        );

        renderPage();

        const summary = await screen.findByRole("heading", { name: "Compatibility summary" });
        expect(within(summary.closest("section") as HTMLElement).getByText(expected)).toBeInTheDocument();
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

        expect(await screen.findByText("Warnings")).toBeInTheDocument();
        expect(await screen.findByText("Blocking issues")).toBeInTheDocument();
        expect(screen.getByText("Memory is borderline.")).toBeInTheDocument();
        expect(screen.getByText("Required port is missing.")).toBeInTheDocument();
        const warning = screen.getByText("Memory is borderline.").closest("article");
        const blocker = screen.getByText("Required port is missing.").closest("article");
        expect(within(warning as HTMLElement).getByText("Compatible with warnings")).toBeInTheDocument();
        expect(within(blocker as HTMLElement).getByText("Not compatible")).toBeInTheDocument();
        expect(screen.getByText("Open ports")).toBeInTheDocument();
        expect(screen.getByText("Installed services")).toBeInTheDocument();
        expect(screen.queryByText(/Checked field: requirements\.resources\.memory_mb_min/)).not.toBeVisible();
        const technicalDetails = within(warning as HTMLElement).getByText("Evidence details").closest("details");
        expect(technicalDetails).not.toHaveAttribute("open");
        expect(within(technicalDetails as HTMLDetailsElement).queryByText("Evidence e0002")).not.toBeVisible();
        await userEvent.setup().click(within(technicalDetails as HTMLDetailsElement).getByText("Evidence details"));
        expect(within(technicalDetails as HTMLDetailsElement).getByText("Evidence e0001")).toBeVisible();
        expect(within(technicalDetails as HTMLDetailsElement).getByText("Evidence e0002")).toBeVisible();
        expect(within(technicalDetails as HTMLDetailsElement).getByText("Checked field: requirements.resources.memory_mb_min")).toBeVisible();
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

        expect(await screen.findByText("Checking compatibility…")).toBeInTheDocument();
        expect(await screen.findByRole("heading", { name: "Compatibility check" })).toBeInTheDocument();
        expect(await screen.findByRole("heading", { name: "Frigate" })).toBeInTheDocument();

        await waitFor(() => {
            expect(compatibilityPromise).toBeDefined();
            expect(resolveCompatibility).toBeDefined();
        });
        resolveCompatibility!(compatibilityAssessment());
        const summary = await screen.findByRole("heading", { name: "Compatibility summary" });
        expect(within(summary.closest("section") as HTMLElement).getByText("Compatible")).toBeInTheDocument();
    });

    it("shows compatibility failure without replacing the full item page", async () => {
        mockedGetDiscoveryCompatibility.mockRejectedValue(
            new Error("Temporary compatibility backend failure"),
        );

        renderPage();

        expect(await screen.findByRole("heading", { name: "Frigate" })).toBeInTheDocument();
        expect(await screen.findByText("Could not check compatibility")).toBeInTheDocument();
        expect(screen.getByText("Atlas could not confirm whether this item fits the selected environment.")).toBeInTheDocument();
        const error = screen.getByText("Could not check compatibility").closest("div");
        const technicalDetails = within(error as HTMLElement).getByText("Technical details").closest("details");
        expect(technicalDetails).not.toHaveAttribute("open");
        expect(within(technicalDetails as HTMLDetailsElement).getByText("Temporary compatibility backend failure")).not.toBeVisible();
        await userEvent.setup().click(within(technicalDetails as HTMLDetailsElement).getByText("Technical details"));
        expect(within(technicalDetails as HTMLDetailsElement).getByText("Temporary compatibility backend failure")).toBeVisible();
        expect(screen.getByText("Retry check")).toBeInTheDocument();
        expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    });

    it("renders empty compatibility findings, evidence, and unknown facts", async () => {
        mockedGetDiscoveryCompatibility.mockResolvedValue(
            compatibilityAssessment({ findings: [], evidence: [], unknown_facts: [] }),
        );

        renderPage();

        expect(await screen.findByText("No issues or notes were found.")).toBeInTheDocument();
        expect(screen.getByText("Atlas Environment")).toBeInTheDocument();
        expect(screen.getByText("Unconfirmed details")).toBeInTheDocument();
    });

    it("renders incoming and outgoing relationships separately with links and labels", async () => {
        renderPage();

        const outgoing = await screen.findByRole("heading", {
            name: "Links from this item",
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
            name: "Items linking to this item",
        });
        const incomingPanel = incoming.closest("section");
        expect(incomingPanel).not.toBeNull();
        expect(within(incomingPanel!).getByText("Displays catalog facts.")).toBeInTheDocument();
        expect(within(incomingPanel!).getByRole("link", { name: "Mission Control" })).toHaveAttribute(
            "href",
            "/discovery/items/mission-control",
        );
        expect(within(incomingPanel!).getByText("Frigate")).toBeInTheDocument();
        expect(within(incomingPanel!).getByText("Integrates With")).toBeInTheDocument();
        expect(within(incomingPanel!).queryByRole("link", { name: "Frigate" })).not.toBeInTheDocument();
        expect(within(incomingPanel!).queryByText("Resolved")).not.toBeInTheDocument();
    });

    it("renders empty relationship states", async () => {
        mockedGetDiscoveryRelationships.mockResolvedValue({
            item_id: "frigate",
            incoming: [],
            outgoing: [],
        });

        renderPage();

        expect(await screen.findByText("No links from this item.")).toBeInTheDocument();
        expect(screen.getByText("No items link to this item.")).toBeInTheDocument();
    });

    it("renders not found state", async () => {
        mockedGetDiscoveryItem.mockRejectedValue(httpError(404, "Discovery item not found"));

        renderPage();

        expect(
            await screen.findByRole("heading", { name: "Catalog item not found" }),
        ).toBeInTheDocument();
        expect(screen.getByText("This catalog item is no longer available. Return to the catalog and choose a current item.")).toBeInTheDocument();
        const technicalDetails = screen.getByText("Technical details").closest("details");
        expect(within(technicalDetails as HTMLDetailsElement).getByText("Catalog item ID: frigate")).not.toBeVisible();
        await userEvent.setup().click(within(technicalDetails as HTMLDetailsElement).getByText("Technical details"));
        expect(within(technicalDetails as HTMLDetailsElement).getByText("Catalog item ID: frigate")).toBeVisible();
        expect(mockedGetDiscoveryRelationships).not.toHaveBeenCalled();
        expect(mockedGetDiscoveryCompatibility).not.toHaveBeenCalled();
        expect(mockedGetDiscoveryItemEvidence).not.toHaveBeenCalled();
        expect(mockedGetDiscoveryImageGrounding).not.toHaveBeenCalled();
        expect(mockedGetDiscoveryInstallationPlan).not.toHaveBeenCalled();
        expect(mockedListDiscoveryProposals).not.toHaveBeenCalled();
    });

    it("renders unavailable state", async () => {
        mockedGetDiscoveryItem.mockRejectedValue(new Error("Catalog unavailable"));

        renderPage();

        const alert = await screen.findByRole("alert");
        expect(alert).toHaveTextContent("Catalog could not be loaded");
    });
});
