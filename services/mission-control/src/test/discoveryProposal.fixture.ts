import type { DiscoveryProposalNavigation } from "../types/discovery";

export function discoveryProposalFixture(
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
