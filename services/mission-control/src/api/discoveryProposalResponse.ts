import type { DiscoveryProposalNavigation, DiscoveryProposalPage } from "../types/discovery";
import { evidenceTimestamp } from "../utils/healthPresentation";

export class DiscoveryProposalResponseError extends Error {
    constructor() { super("The advisory proposal context could not be read."); }
}
function fail(): never { throw new DiscoveryProposalResponseError(); }
function record(value: unknown): value is Record<string, unknown> { return value !== null && typeof value === "object" && !Array.isArray(value); }
function text(value: unknown): value is string { return typeof value === "string" && value.trim().length > 0; }
function oneOf(value: unknown, choices: string[]): boolean { return typeof value === "string" && choices.includes(value); }
function count(value: unknown, min = 0): boolean { return Number.isSafeInteger(value) && Number(value) >= min; }

// Advisory display and closed navigation only. Never infer an actionable flag,
// select a resource from hints, or supply operational authorization.
export function parseDiscoveryProposal(value: unknown, expectedId?: string): DiscoveryProposalNavigation {
    if (!record(value)) fail();
    const data = { intent_hint: null, target_hints: [], actionable_navigation: false, ...value } as Record<string, unknown>;
    if (typeof data.proposal_id !== "string" || data.proposal_id.length !== "discovery-operator-proposal-".length + 64
        || !/^discovery-operator-proposal-[a-f0-9]{64}$/.test(data.proposal_id)
        || (expectedId !== undefined && data.proposal_id !== expectedId)
        || !text(data.catalog_item_id) || data.catalog_item_id.length > 128 || !/^[a-z0-9]+(?:-[a-z0-9]+)*$/.test(data.catalog_item_id)
        || !oneOf(data.destination_kind, ["discovery_detail", "compatibility_review", "operator_maintenance_selection"])
        || !oneOf(data.catalog_source_type, ["curated", "private", "community", "dynamic"])
        || !oneOf(data.compatibility_status, ["compatible", "compatible_with_warnings", "insufficient_information", "incompatible"])
        || !oneOf(data.status, ["current", "stale", "expired", "not_actionable"])
        || !oneOf(data.reason, ["compatible", "compatibility_warning", "incompatible", "insufficient_information", "unsupported_resource", "source_changed", "source_missing", "evidence_changed", "evidence_missing", "expired", "no_supported_destination"])
        || !count(data.finding_reference_count) || !count(data.evidence_reference_count)
        || typeof data.actionable_navigation !== "boolean" || (data.intent_hint !== null && data.intent_hint !== "restart-service")
        || !Array.isArray(data.target_hints)) fail();
    for (const hint of data.target_hints) {
        if (!record(hint) || ["catalog_target_id", "provider_hint", "resource_type_hint"].some(key => hint[key] !== undefined && hint[key] !== null && !text(hint[key]))) fail();
    }
    const generated = evidenceTimestamp(data.generated_at);
    const expires = evidenceTimestamp(data.expires_at);
    if (generated === null || expires === null || expires <= generated) fail();
    return data as unknown as DiscoveryProposalNavigation;
}

export function parseDiscoveryProposalPage(value: unknown): DiscoveryProposalPage {
    if (!record(value) || !Array.isArray(value.proposals) || !count(value.total) || !count(value.limit, 1) || Number(value.limit) > 100
        || value.proposals.length > Number(value.limit)) fail();
    const proposals = value.proposals.map(row => parseDiscoveryProposal(row));
    if (new Set(proposals.map(row => row.proposal_id)).size !== proposals.length) fail();
    return { ...value, proposals } as DiscoveryProposalPage;
}
