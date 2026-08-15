import { describe, expect, it } from "vitest";

import type { DiscoveryProposalNavigation } from "../../types/discovery";
import { resolveProposalNavigation } from "./proposalNavigation";

const proposal: DiscoveryProposalNavigation = {
    proposal_id: "discovery-operator-proposal-" + "a".repeat(64),
    destination_kind: "operator_maintenance_selection",
    catalog_item_id: "frigate",
    catalog_source_type: "curated",
    compatibility_status: "compatible",
    finding_reference_count: 1,
    evidence_reference_count: 2,
    status: "current",
    reason: "compatible",
    intent_hint: "restart-service",
    target_hints: [{ provider_hint: "tampered", resource_type_hint: "tampered" }],
    generated_at: "2026-08-15T00:00:00+00:00",
    expires_at: "2026-08-15T00:30:00+00:00",
    actionable_navigation: true,
};

describe("resolveProposalNavigation", () => {
    it("maps actionable maintenance proposals to the fixed selection page only", () => {
        expect(resolveProposalNavigation(proposal)).toEqual({
            kind: "operator_maintenance_selection",
            proposalId: proposal.proposal_id,
        });
    });

    it.each(["stale", "expired", "not_actionable"] as const)(
        "forces %s proposal navigation back to read-only detail",
        (status) => {
            expect(resolveProposalNavigation({ ...proposal, status })).toEqual({
                kind: "discovery_item",
                itemId: "frigate",
            });
        },
    );

    it("fails closed for an unknown destination", () => {
        expect(() => resolveProposalNavigation({
            ...proposal,
            destination_kind: "https://attacker.invalid" as never,
        })).toThrow("Unsupported Discovery proposal destination");
    });
});
