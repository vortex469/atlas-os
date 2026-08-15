import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";

import type { DiscoveryProposalNavigation } from "../../types/discovery";
import { DiscoveryProposalCard } from "./DiscoveryProposalCard";

function proposal(
    overrides: Partial<DiscoveryProposalNavigation> = {},
): DiscoveryProposalNavigation {
    return {
        proposal_id: `discovery-operator-proposal-${"a".repeat(64)}`,
        destination_kind: "operator_maintenance_selection",
        catalog_item_id: "frigate",
        catalog_source_type: "curated",
        compatibility_status: "compatible",
        finding_reference_count: 1,
        evidence_reference_count: 2,
        status: "current",
        reason: "compatible",
        intent_hint: "restart-service",
        target_hints: [{ catalog_target_id: "atlas", provider_hint: "proxmox", resource_type_hint: "qemu" }],
        generated_at: "2026-08-15T00:00:00Z",
        expires_at: "2026-08-15T00:30:00Z",
        actionable_navigation: true,
        ...overrides,
    };
}

function renderCard(value: DiscoveryProposalNavigation) {
    render(<MemoryRouter><DiscoveryProposalCard proposal={value} /></MemoryRouter>);
}

describe("DiscoveryProposalCard", () => {
    it("renders sanitized current proposal context and advisory authority warning", () => {
        renderCard(proposal());
        expect(screen.getByText("Status: Current")).toBeInTheDocument();
        expect(screen.getByText("1")).toBeInTheDocument();
        expect(screen.getByText("2")).toBeInTheDocument();
        expect(screen.getByText("atlas / proxmox / qemu")).toBeInTheDocument();
        expect(screen.getByText(/re-check your permission/i)).toBeInTheDocument();
        expect(screen.getByRole("link", { name: /Continue to maintenance selection/i })).toHaveAttribute("href", "/operations/request");
        expect(screen.queryByText(/vmgenid|provider action|target fingerprint/i)).not.toBeInTheDocument();
    });

    it.each([
        ["stale", "source_changed"],
        ["expired", "expired"],
        ["not_actionable", "unsupported_resource"],
        ["not_actionable", "evidence_missing"],
    ] as const)("renders %s/%s as review only", (status, reason) => {
        renderCard(proposal({ status, reason, actionable_navigation: false }));
        expect(screen.getByText(/Review only: operational navigation is disabled/i)).toBeInTheDocument();
        expect(screen.getByRole("link", { name: /Review Discovery item/i })).toBeInTheDocument();
        expect(screen.queryByRole("link", { name: /maintenance selection/i })).not.toBeInTheDocument();
    });

    it.each([
        ["incompatible", "incompatible"],
        ["insufficient_information", "insufficient_information"],
    ] as const)("keeps %s compatibility proposals on evidence review", (compatibility, reason) => {
        renderCard(proposal({
            destination_kind: "compatibility_review",
            compatibility_status: compatibility,
            reason,
            actionable_navigation: false,
        }));
        expect(screen.getByRole("link", { name: /Review compatibility evidence/i })).toBeInTheDocument();
        expect(screen.queryByRole("link", { name: /maintenance selection/i })).not.toBeInTheDocument();
    });
});
