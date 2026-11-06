import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

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
    it("leads with the check result and keeps deployment and provenance details collapsed", async () => {
        const user = userEvent.setup();
        renderProjection(projection());

        expect(screen.getByRole("heading", { name: "Image check" })).toBeInTheDocument();
        expect(screen.getByText("Image matches release evidence")).toBeInTheDocument();
        expect(screen.getByText("Read-only check. It does not install, deploy, or run anything.")).toBeInTheDocument();
        expect(screen.getAllByText("2026.8.3")).toHaveLength(2);
        const imageReferences = screen.getAllByText("ghcr.io/home-assistant/home-assistant");
        expect(imageReferences).toHaveLength(2);
        expect(imageReferences[0]).toBeVisible();
        expect(imageReferences[1]).not.toBeVisible();
        const evidenceRow = within(screen.getByRole("list", { name: "Release evidence" })).getByRole("listitem");
        expect(within(evidenceRow).getByText("Registry attestation")).toBeVisible();
        expect(within(evidenceRow).getByText(/Release 2026\.8\.3 · evidence dated .+ UTC/)).toBeVisible();
        const technicalDetails = screen.getByText("Technical details").closest("details")!;
        expect(technicalDetails).not.toHaveAttribute("open");
        expect(within(technicalDetails).getByText("docker-compose")).not.toBeVisible();
        expect(within(technicalDetails).getByText("compose/home-assistant.yaml")).not.toBeVisible();
        expect(within(technicalDetails).getByText("registry:home-assistant:2026.8.3")).not.toBeVisible();
        expect(within(technicalDetails).getByText("2026-08-21T20:54:36Z")).not.toBeVisible();
        within(technicalDetails).getAllByText(DIGEST_A).forEach((element) => expect(element).not.toBeVisible());

        await user.click(screen.getByText("Technical details"));
        expect(within(technicalDetails).getByText("docker-compose")).toBeVisible();
        expect(within(technicalDetails).getByText("compose/home-assistant.yaml")).toBeVisible();
        expect(within(technicalDetails).getByText("registry:home-assistant:2026.8.3")).toBeVisible();
        expect(within(technicalDetails).getByText("2026-08-21T20:54:36Z")).toBeVisible();
        expect(within(technicalDetails).getAllByText(DIGEST_A)).toHaveLength(2);
    });

    it("keeps every source class visibly distinct and preserves evidence order", () => {
        renderProjection(projection({
            accepted_evidence: [
                { release_version: "2026.8.3", image_reference: "example/one", image_digest: DIGEST_A, source_class: "curated", source_id: "first", attested_at: "2026-08-20T00:00:00Z" },
                { release_version: "2026.8.3", image_reference: "example/two", image_digest: DIGEST_B, source_class: "registry_attested", source_id: "second", attested_at: "2026-08-21T00:00:00Z" },
                { release_version: "2026.8.3", image_reference: "example/three", image_digest: DIGEST_A, source_class: "upstream_signed", source_id: "third", attested_at: "2026-08-22T00:00:00Z" },
            ],
        }));

        const rows = within(screen.getByRole("list", { name: "Release evidence" })).getAllByRole("listitem");
        expect(within(rows[0]).getByText("Curated catalog")).toHaveClass("text-blue-200");
        expect(within(rows[1]).getByText("Registry attestation")).toHaveClass("text-emerald-200");
        expect(within(rows[2]).getByText("Signed upstream release")).toHaveClass("text-violet-200");
        expect(rows.map((row) => row.querySelector("span")?.textContent)).toEqual([
            "Curated catalog", "Registry attestation", "Signed upstream release",
        ]);
        expect(within(rows[2]).queryByText("Curated catalog")).not.toBeInTheDocument();
    });

    it.each<[DiscoveryImageGroundingStatus, string]>([
        ["no_deployment_binding", "No deployment mapping"],
        ["no_strict_release_version", "Release version unavailable"],
        ["no_repository_observation", "No image found in the repository"],
        ["observation_mismatch", "Image does not match the deployment mapping"],
        ["mutable_observation", "Image reference can change"],
        ["no_image_release_evidence", "Release evidence is missing"],
        ["evidence_not_trusted", "Evidence source is not accepted"],
        ["evidence_version_mismatch", "Evidence is for a different release"],
        ["repository_identity_mismatch", "Image repository does not match"],
        ["digest_mismatch", "Image contents do not match"],
        ["conflicted", "Evidence conflicts"],
    ])("renders %s as an explicit fail-closed advisory", (status, label) => {
        renderProjection(projection({ status, release_version: null, deployment_binding: null, observed_image: null, accepted_evidence: [] }));
        const state = screen.getAllByText(label).find((element) => element.tagName === "P");
        expect(state).toBeDefined();
        expect(state).toHaveClass("text-amber-200");
        expect(screen.queryByText("Image matches release evidence")).not.toBeInTheDocument();
        expect(screen.getByText("No accepted release evidence is available.")).toBeInTheDocument();
    });

    it.each([
        ["not_found", "No image check is available for this item."],
        ["source_unavailable", "Atlas could not finish checking the image. Try again."],
        ["unavailable", "The image check is unavailable right now."],
    ] as const)("renders bounded %s errors without backend details", (errorKind, copy) => {
        const onRetry = vi.fn();
        render(<DiscoveryImageGroundingPanel projection={null} isLoading={false} errorKind={errorKind} onRetry={onRetry} />);
        expect(screen.getByRole("status")).toHaveTextContent(copy);
        expect(screen.queryByText(/SECRET|token=hidden|private\/repository/)).not.toBeInTheDocument();
        const retryButton = screen.queryByRole("button", { name: "Retry image check" });
        if (errorKind === "not_found") {
            expect(retryButton).not.toBeInTheDocument();
        } else {
            expect(retryButton).toBeInTheDocument();
            retryButton?.click();
            expect(onRetry).toHaveBeenCalledOnce();
        }
    });

    it("renders a bounded loading state and advisory authority copy without actions", () => {
        render(<DiscoveryImageGroundingPanel projection={null} isLoading errorKind={null} />);
        expect(screen.getByText("Checking image and release evidence…")).toBeInTheDocument();
        expect(screen.getByText("Read-only check. It does not install, deploy, or run anything.")).toBeInTheDocument();
        expect(screen.queryByRole("button")).not.toBeInTheDocument();
        expect(screen.queryByRole("link")).not.toBeInTheDocument();
        expect(screen.queryByText(/install readiness|deployment authorization|update authorization|approval authority/i)).not.toBeInTheDocument();
    });
});
