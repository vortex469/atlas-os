import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type {
    DiscoveryImageGroundingProjection,
    DiscoveryImageGroundingStatus,
} from "../../types/discovery";
import { DiscoveryImageGroundingPanel } from "./DiscoveryImageGroundingPanel";

const DIGEST_A = `sha256:${"1".repeat(64)}`;
const DIGEST_B = `sha256:${"2".repeat(64)}`;

function projection(
    overrides: Partial<DiscoveryImageGroundingProjection> = {},
): DiscoveryImageGroundingProjection {
    return {
        schema_version: "discovery-image-grounding-projection-v1",
        catalog_item_id: "home-assistant",
        status: "grounded",
        release_version: "2026.8.3",
        deployment_binding: {
            compose_file: "compose/home-assistant.yaml",
            compose_service: "home-assistant",
            mutable_property: "image",
            deployment_method: "docker-compose",
        },
        observed_image: {
            image_reference: "ghcr.io/home-assistant/home-assistant",
            image_digest: DIGEST_A,
        },
        accepted_evidence: [{
            release_version: "2026.8.3",
            image_reference: "ghcr.io/home-assistant/home-assistant",
            image_digest: DIGEST_A,
            source_class: "registry_attested",
            source_id: "registry:home-assistant:2026.8.3",
            attested_at: "2026-08-21T20:54:36Z",
        }],
        ...overrides,
    };
}

function renderProjection(value: DiscoveryImageGroundingProjection) {
    return render(<DiscoveryImageGroundingPanel projection={value} isLoading={false} errorKind={null} />);
}

describe("DiscoveryImageGroundingPanel", () => {
    it("renders the grounded projection and all bounded provenance fields", () => {
        renderProjection(projection());

        expect(screen.getByText("Grounded")).toBeInTheDocument();
        expect(screen.getAllByText("2026.8.3")).toHaveLength(2);
        expect(screen.getByText("docker-compose")).toBeInTheDocument();
        expect(screen.getByText("compose/home-assistant.yaml")).toBeInTheDocument();
        expect(screen.getAllByText("ghcr.io/home-assistant/home-assistant")).toHaveLength(2);
        expect(screen.getAllByText(DIGEST_A)).toHaveLength(2);
        expect(screen.getByText("REGISTRY_ATTESTED")).toBeInTheDocument();
        expect(screen.getByText("registry:home-assistant:2026.8.3")).toBeInTheDocument();
        expect(screen.getByText("2026-08-21T20:54:36Z")).toBeInTheDocument();
    });

    it("keeps every source class visibly distinct and preserves evidence order", () => {
        renderProjection(projection({
            accepted_evidence: [
                { release_version: "2026.8.3", image_reference: "example/one", image_digest: DIGEST_A, source_class: "curated", source_id: "first", attested_at: "2026-08-20T00:00:00Z" },
                { release_version: "2026.8.3", image_reference: "example/two", image_digest: DIGEST_B, source_class: "registry_attested", source_id: "second", attested_at: "2026-08-21T00:00:00Z" },
                { release_version: "2026.8.3", image_reference: "example/three", image_digest: DIGEST_A, source_class: "upstream_signed", source_id: "third", attested_at: "2026-08-22T00:00:00Z" },
            ],
        }));

        const rows = screen.getAllByRole("listitem");
        expect(within(rows[0]).getByText("CURATED")).toHaveClass("text-blue-200");
        expect(within(rows[1]).getByText("REGISTRY_ATTESTED")).toHaveClass("text-emerald-200");
        expect(within(rows[2]).getByText("UPSTREAM_SIGNED")).toHaveClass("text-violet-200");
        expect(rows.map((row) => within(row).getByText(/first|second|third/).textContent)).toEqual(["first", "second", "third"]);
        expect(within(rows[2]).queryByText("CURATED")).not.toBeInTheDocument();
    });

    it.each<[DiscoveryImageGroundingStatus, string]>([
        ["no_deployment_binding", "No deployment binding"],
        ["no_strict_release_version", "No strict release version"],
        ["no_repository_observation", "No repository observation"],
        ["observation_mismatch", "Observation mismatch"],
        ["mutable_observation", "Mutable observation"],
        ["no_image_release_evidence", "No image release evidence"],
        ["evidence_not_trusted", "Evidence not trusted"],
        ["evidence_version_mismatch", "Evidence version mismatch"],
        ["repository_identity_mismatch", "Repository identity mismatch"],
        ["digest_mismatch", "Digest mismatch"],
        ["conflicted", "Conflicted"],
    ])("renders %s as an explicit fail-closed advisory", (status, label) => {
        renderProjection(projection({ status, release_version: null, deployment_binding: null, observed_image: null, accepted_evidence: [] }));
        const state = screen.getAllByText(label).find((element) => element.tagName === "P");
        expect(state).toBeDefined();
        expect(state).toHaveClass("text-amber-200");
        expect(screen.queryByText("Grounded")).not.toBeInTheDocument();
        expect(screen.getByText("No accepted image-release evidence.")).toBeInTheDocument();
    });

    it.each([
        ["not_found", "Item grounding projection unavailable or not found."],
        ["source_unavailable", "Image grounding is currently unavailable due to a local source or read failure."],
        ["unavailable", "Image grounding is currently unavailable."],
    ] as const)("renders bounded %s errors without backend details", (errorKind, copy) => {
        render(<DiscoveryImageGroundingPanel projection={null} isLoading={false} errorKind={errorKind} />);
        expect(screen.getByRole("status")).toHaveTextContent(copy);
        expect(screen.queryByText(/SECRET|token=hidden|private\/repository/)).not.toBeInTheDocument();
    });

    it("renders a bounded loading state and advisory authority copy without actions", () => {
        render(<DiscoveryImageGroundingPanel projection={null} isLoading errorKind={null} />);
        expect(screen.getByText("Loading image-grounding context…")).toBeInTheDocument();
        expect(screen.getByText("Image grounding is advisory and grants no deployment or execution authority.")).toBeInTheDocument();
        expect(screen.queryByRole("button")).not.toBeInTheDocument();
        expect(screen.queryByRole("link")).not.toBeInTheDocument();
        expect(screen.queryByText(/install readiness|deployment authorization|update authorization|approval authority/i)).not.toBeInTheDocument();
    });
});
