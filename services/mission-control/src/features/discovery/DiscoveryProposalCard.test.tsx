import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";

import type { DiscoveryProposalNavigation } from "../../types/discovery";
import { DiscoveryProposalCard } from "./DiscoveryProposalCard";

import { discoveryProposalFixture as proposal } from "../../test/discoveryProposal.fixture";

function renderCard(value: DiscoveryProposalNavigation) {
    render(<MemoryRouter><DiscoveryProposalCard proposal={value} /></MemoryRouter>);
}

describe("DiscoveryProposalCard", () => {
    it("does not advertise maintenance navigation for a string false flag", () => {
        renderCard(proposal({ actionable_navigation: "false" as never }));
        expect(screen.getByRole("link", { name: "Review Discovery item for frigate" })).toHaveAttribute("href", "/discovery/items/frigate");
        expect(screen.queryByRole("link", { name: "Continue to maintenance selection for frigate" })).not.toBeInTheDocument();
        expect(screen.getByRole("status")).toHaveTextContent("Review only. This proposal cannot continue to maintenance selection.");
    });

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
        expect(screen.getByText(/Review only\. This proposal cannot continue to maintenance selection\./)).toBeInTheDocument();
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
