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
    it("keeps the suggestion summary visible and optional details collapsed", () => {
        renderCard(proposal());
        expect(screen.getByText("Suggestion")).toBeVisible();
        expect(screen.getByRole("heading", { name: "Frigate" })).toBeVisible();
        expect(screen.getByText("Suggestion status: Current")).toBeInTheDocument();
        expect(screen.getByText("Compatibility").parentElement).toHaveTextContent("Compatible");
        expect(screen.getByText("Compatibility").parentElement).toBeVisible();
        expect(screen.getByText(/Atlas checks your permission and the current VM details/i)).toBeVisible();
        const details = screen.getByText("More about this suggestion").closest("details");
        expect(details).not.toHaveAttribute("open");
        expect(screen.getByText(/atlas \/ proxmox \/ qemu/)).not.toBeVisible();
        expect(screen.getByText(/Suggestion ID:/)).not.toBeVisible();
        expect(screen.getByRole("link", { name: /Continue to maintenance selection/i })).toHaveAttribute("href", "/operations/request");
        expect(screen.queryByText(/vmgenid|provider action|target fingerprint/i)).not.toBeInTheDocument();
    });

    it("labels proposal timestamps as local time and keeps the exact source values", () => {
        renderCard(proposal());
        const generated = screen.getByText("Generated (local time)").parentElement?.querySelector("time");
        const expires = screen.getByText("Expires (local time)").parentElement?.querySelector("time");
        expect(generated).toHaveAttribute("dateTime", "2026-08-15T00:00:00Z");
        expect(expires).toHaveAttribute("dateTime", "2026-08-15T00:30:00Z");
        expect(generated).not.toHaveTextContent("T00:00:00Z");
    });

    it("shows unavailable time when proposal timestamps are malformed", () => {
        renderCard(proposal({ generated_at: "not-a-time", expires_at: "2026-02-30T00:30:00Z" }));
        expect(screen.getByText("Generated (local time)").parentElement).toHaveTextContent("Time unavailable");
        expect(screen.getByText("Expires (local time)").parentElement).toHaveTextContent("Time unavailable");
        expect(screen.queryByText("Invalid Date")).not.toBeInTheDocument();
    });

    it.each([
        ["stale", "source_changed", "Out of date"],
        ["expired", "expired", "Expired"],
        ["not_actionable", "unsupported_resource", "Review only"],
        ["not_actionable", "evidence_missing", "Review only"],
    ] as const)("renders %s/%s as review only", (status, reason, expectedStatus) => {
        renderCard(proposal({ status, reason, actionable_navigation: false }));
        expect(screen.getByText(`Suggestion status: ${expectedStatus}`)).toBeInTheDocument();
        expect(screen.getByText(/This suggestion can’t be used to request maintenance/i)).toBeVisible();
        expect(screen.getByRole("link", { name: /View catalog item/i })).toBeInTheDocument();
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
