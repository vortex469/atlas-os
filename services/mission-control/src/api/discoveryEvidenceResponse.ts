import type { DiscoveryItemEvidence } from "../types/discovery";
import { evidenceTimestamp } from "../utils/healthPresentation";

export class DiscoveryEvidenceResponseError extends Error {
    constructor() { super("The release evidence could not be read. Reload the page to try again."); }
}
function record(value: unknown): value is Record<string, unknown> {
    return value !== null && typeof value === "object" && !Array.isArray(value);
}
function text(value: unknown): value is string { return typeof value === "string" && value.trim().length > 0; }
function oneOf(value: unknown, values: string[]): boolean { return typeof value === "string" && values.includes(value); }
function fail(): never { throw new DiscoveryEvidenceResponseError(); }

// Guard fields rendered by release evidence, including labels whose meaning is
// fixed in the UI. This is not a complete projection or execution validator.
export function parseDiscoveryEvidence(value: unknown, itemId: string): DiscoveryItemEvidence {
    if (!record(value) || value.schema_version !== "discovery-merged-item-v1" || value.catalog_item_id !== itemId
        || !record(value.curated) || !record(value.curated.item) || value.curated.item.id !== itemId
        || !oneOf(value.conflict_state, ["none", "agreement", "dynamic_conflict", "curated_conflict"])) fail();
    const claims = value.dynamic_claims === undefined ? [] : value.dynamic_claims;
    const sources = value.source_states === undefined ? [] : value.source_states;
    if (!Array.isArray(claims) || !Array.isArray(sources)) fail();
    const sourceIds = new Set<string>();
    const availableIds = new Set<string>();
    for (const source of sources) {
        if (!record(source) || !text(source.source_id) || sourceIds.has(source.source_id)
            || (source.health !== undefined && source.health !== null && !oneOf(source.health, ["healthy", "degraded", "unavailable"]))
            || !oneOf(source.cache_state, ["available", "absent", "corrupt"])) fail();
        sourceIds.add(source.source_id);
        if (source.cache_state === "available") availableIds.add(source.source_id);
    }
    for (const claim of claims) {
        if (!record(claim) || claim.fact_kind !== "latest_stable_release" || !text(claim.version)
            || !/^[0-9]+\.[0-9]+\.[0-9]+$/.test(claim.version) || claim.version.length > 64
            || evidenceTimestamp(claim.published_at) === null || !oneOf(claim.freshness, ["fresh", "stale"])
            || !record(claim.provenance)) fail();
        const provenance = claim.provenance;
        const retrieved = evidenceTimestamp(provenance.retrieved_at);
        const expires = evidenceTimestamp(provenance.expires_at);
        if (!text(provenance.source_id) || !availableIds.has(provenance.source_id)
            || provenance.source_type !== "github_latest_release" || provenance.trust_tier !== "supplemental"
            || !text(provenance.repository) || provenance.repository !== provenance.repository.trim()
            || provenance.repository.length > 256 || /[:?@#\\]/.test(provenance.repository)
            || [...provenance.repository].some(character => character.charCodeAt(0) < 32 || character.charCodeAt(0) === 127)
            || provenance.repository.startsWith("/") || !Number.isSafeInteger(provenance.upstream_release_id)
            || Number(provenance.upstream_release_id) < 1 || retrieved === null || expires === null
            || expires - retrieved !== 86_400_000) fail();
    }
    if (claims.length === 0 && value.conflict_state !== "none") fail();
    const evaluation = value.release_evaluation;
    if (evaluation !== undefined && evaluation !== null) {
        if (!record(evaluation) || !oneOf(evaluation.status, ["up_to_date", "update_available", "baseline_ahead", "conflicted",
            "stale_evidence", "no_baseline", "no_dynamic_evidence", "insufficient_information"])) fail();
        if (evaluation.baseline !== undefined && evaluation.baseline !== null
            && (!record(evaluation.baseline) || !text(evaluation.baseline.version)
                || !oneOf(evaluation.baseline.source, ["curated", "item_version"]))) fail();
        if (evaluation.latest_candidate !== undefined && evaluation.latest_candidate !== null && !text(evaluation.latest_candidate)) fail();
        const conflict = value.conflict_state === "dynamic_conflict" || value.conflict_state === "curated_conflict";
        if (conflict !== (evaluation.status === "conflicted")
            || (conflict && evaluation.latest_candidate != null)
            || (oneOf(evaluation.status, ["up_to_date", "update_available", "baseline_ahead"]) && !text(evaluation.latest_candidate))) fail();
    }
    return { ...value, dynamic_claims: claims, source_states: sources } as DiscoveryItemEvidence;
}
