import { beforeEach, expect, it, vi } from "vitest";
import { atlas } from "./atlas";
import { getDiscoveryItemEvidence } from "./discovery";
vi.mock("./atlas", () => ({ atlas: { get: vi.fn() } }));
const source = { source_id: "sample-source", health: "healthy", cache_state: "available" };
const provenance = { source_id: "sample-source", source_type: "github_latest_release", trust_tier: "supplemental", repository: "example/sample", upstream_release_id: 1,
    retrieved_at: "2026-10-26T12:00:00Z", expires_at: "2026-10-27T12:00:00Z" };
const claim = { fact_kind: "latest_stable_release", version: "1.2.3", published_at: "2026-10-25T12:00:00Z", freshness: "fresh", provenance };
const response = { schema_version: "discovery-merged-item-v1", catalog_item_id: "sample", curated: { item: { id: "sample" } },
    dynamic_claims: [claim], source_states: [source], conflict_state: "none", additive: "retained" };
beforeEach(() => vi.clearAllMocks());
it("preserves readable evidence and additive metadata", async () => {
    vi.mocked(atlas.get).mockResolvedValue({ data: response });
    await expect(getDiscoveryItemEvidence("sample")).resolves.toEqual(response);
    expect(atlas.get).toHaveBeenCalledWith("/discovery/items/sample/evidence");
});
for (const [label, value] of [
    ["null", null], ["missing identity", {}], ["another item", { ...response, catalog_item_id: "other" }],
    ["another curated item", { ...response, curated: { item: { id: "other" } } }],
    ["unknown schema", { ...response, schema_version: "future" }],
    ["object source states", { ...response, source_states: {} }],
    ["null claims", { ...response, dynamic_claims: null }],
    ["unknown conflict", { ...response, conflict_state: "future" }],
    ["prototype conflict", { ...response, conflict_state: "constructor" }],
    ["unknown health", { ...response, source_states: [{ ...source, health: "future" }] }],
    ["unknown cache", { ...response, source_states: [{ ...source, cache_state: "future" }] }],
    ["duplicate source", { ...response, source_states: [source, source] }],
    ["unavailable claim source", { ...response, source_states: [{ ...source, cache_state: "absent" }] }],
    ["null claim", { ...response, dynamic_claims: [null] }],
    ["unknown freshness", { ...response, dynamic_claims: [{ ...claim, freshness: "future" }] }],
    ["non-release claim", { ...response, dynamic_claims: [{ ...claim, fact_kind: "other" }] }],
    ["object version", { ...response, dynamic_claims: [{ ...claim, version: {} }] }],
    ["unknown source type", { ...response, dynamic_claims: [{ ...claim, provenance: { ...provenance, source_type: "other" } }] }],
    ["wrong trust", { ...response, dynamic_claims: [{ ...claim, provenance: { ...provenance, trust_tier: "authoritative" } }] }],
    ["invalid timestamp", { ...response, dynamic_claims: [{ ...claim, published_at: "2026-02-30T12:00:00Z" }] }],
    ["wrong expiry", { ...response, dynamic_claims: [{ ...claim, provenance: { ...provenance, expires_at: provenance.retrieved_at } }] }],
    ["credential-shaped repository", { ...response, dynamic_claims: [{ ...claim, provenance: { ...provenance, repository: "https://user:canary@example.invalid/repo" } }] }],
    ["object evaluation", { ...response, release_evaluation: [] }],
    ["unknown evaluation", { ...response, release_evaluation: { status: "future" } }],
    ["prototype evaluation", { ...response, release_evaluation: { status: "__proto__" } }],
    ["object baseline", { ...response, release_evaluation: { status: "no_dynamic_evidence", baseline: {} } }],
    ["positive without candidate", { ...response, release_evaluation: { status: "up_to_date" } }],
    ["conflict with positive evaluation", { ...response, conflict_state: "dynamic_conflict", release_evaluation: { status: "up_to_date", latest_candidate: "1.2.3" } }],
]) it(`rejects ${label} without retry`, async () => {
    vi.mocked(atlas.get).mockResolvedValue({ data: value });
    await expect(getDiscoveryItemEvidence("sample")).rejects.toThrow("The release evidence could not be read. Reload the page to try again.");
    expect(atlas.get).toHaveBeenCalledTimes(1);
});
it("uses public defaults for empty supplemental collections", async () => {
    const data = { schema_version: response.schema_version, catalog_item_id: "sample", curated: response.curated, conflict_state: "none" };
    vi.mocked(atlas.get).mockResolvedValue({ data });
    await expect(getDiscoveryItemEvidence("sample")).resolves.toEqual({ ...data, dynamic_claims: [], source_states: [] });
});
for (const status of ["up_to_date", "update_available", "baseline_ahead", "conflicted", "stale_evidence", "no_baseline", "no_dynamic_evidence", "insufficient_information"]) {
    it(`retains supported release evaluation ${status}`, async () => {
        const evaluation = { status, baseline: status === "no_baseline" ? null : { source: "curated", version: status === "insufficient_information" ? "custom-release" : status === "up_to_date" ? "1.2.3" : status === "baseline_ahead" ? "1.2.4" : "1.2.2" },
            latest_candidate: status === "conflicted" || status === "no_dynamic_evidence" ? null : "1.2.3" };
        const data = { ...response, conflict_state: status === "conflicted" ? "curated_conflict" : "none", release_evaluation: evaluation,
            dynamic_claims: status === "no_dynamic_evidence" ? [] : [{ ...claim, freshness: status === "stale_evidence" ? "stale" : "fresh" }] };
        vi.mocked(atlas.get).mockResolvedValue({ data });
        await expect(getDiscoveryItemEvidence("sample")).resolves.toEqual(data);
    });
}
for (const health of [null, "healthy", "degraded", "unavailable"]) {
    for (const cache_state of ["available", "absent", "corrupt"]) it(`retains source ${health}/${cache_state} without inventing a claim`, async () => {
        const data = { ...response, dynamic_claims: [], source_states: [{ ...source, health, cache_state }] };
        vi.mocked(atlas.get).mockResolvedValue({ data });
        await expect(getDiscoveryItemEvidence("sample")).resolves.toEqual(data);
    });
}
