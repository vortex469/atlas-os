import { beforeEach, expect, it, vi } from "vitest";
import { atlas } from "./atlas";
import { getDiscoveryImageGrounding } from "./discovery";
vi.mock("./atlas", () => ({ atlas: { get: vi.fn() } }));
const digest = `sha256:${"1".repeat(64)}`;
const binding = { compose_file: "compose/app.yaml", compose_service: "app", mutable_property: "image", deployment_method: "docker-compose" };
const observed = { image_reference: "ghcr.io/example/app", image_digest: digest };
const evidence = { ...observed, release_version: "1.2.3", source_class: "curated", source_id: "fixture", attested_at: "2026-10-27T12:00:00Z" };
const response = { schema_version: "discovery-image-grounding-projection-v1", catalog_item_id: "sample", status: "grounded", release_version: "1.2.3",
    deployment_binding: binding, observed_image: observed, accepted_evidence: [evidence], additive: "retained" };
beforeEach(() => vi.clearAllMocks());
it("preserves a readable grounded report without adding authority", async () => {
    vi.mocked(atlas.get).mockResolvedValue({ data: response });
    await expect(getDiscoveryImageGrounding("sample")).resolves.toEqual(response);
    expect(atlas.get).toHaveBeenCalledWith("/discovery/items/sample/image-grounding");
});
for (const [label, value] of [
    ["null", null], ["missing item", {}], ["another item", { ...response, catalog_item_id: "other" }],
    ["future schema", { ...response, schema_version: "future" }],
    ["future status", { ...response, status: "future" }], ["prototype status", { ...response, status: "__proto__" }],
    ["object release", { ...response, release_version: {} }],
    ["unreviewed binding", { ...response, deployment_binding: null }],
    ["path traversal", { ...response, deployment_binding: { ...binding, compose_file: "../app.yaml" } }],
    ["unsupported deployment method", { ...response, deployment_binding: { ...binding, deployment_method: "shell" } }],
    ["object service", { ...response, deployment_binding: { ...binding, compose_service: {} } }],
    ["missing observation", { ...response, observed_image: null }],
    ["mutable digest", { ...response, observed_image: { ...observed, image_digest: "latest" } }],
    ["credential reference", { ...response, observed_image: { ...observed, image_reference: "https://user:canary@example.invalid/app" } }],
    ["object evidence", { ...response, accepted_evidence: {} }],
    ["missing evidence", { ...response, accepted_evidence: [] }],
    ["null row", { ...response, accepted_evidence: [null] }],
    ["unknown source class", { ...response, accepted_evidence: [{ ...evidence, source_class: "future" }] }],
    ["array source class", { ...response, accepted_evidence: [{ ...evidence, source_class: ["curated"] }] }],
    ["non-strict release", { ...response, release_version: "01.2.3" }],
    ["excess evidence", { ...response, accepted_evidence: Array.from({ length: 101 }, () => evidence) }],
    ["object source", { ...response, accepted_evidence: [{ ...evidence, source_id: {} }] }],
    ["invalid timestamp", { ...response, accepted_evidence: [{ ...evidence, attested_at: "2026-02-30T00:00:00Z" }] }],
    ["non-UTC attestation", { ...response, accepted_evidence: [{ ...evidence, attested_at: "2026-10-27T12:00:00+01:00" }] }],
    ["other release", { ...response, accepted_evidence: [{ ...evidence, release_version: "1.2.4" }] }],
    ["other digest", { ...response, accepted_evidence: [{ ...evidence, image_digest: `sha256:${"2".repeat(64)}` }] }],
    ["other reference", { ...response, accepted_evidence: [{ ...evidence, image_reference: "example/other" }] }],
    ["conflicting evidence", { ...response, accepted_evidence: [evidence, { ...evidence, image_digest: `sha256:${"2".repeat(64)}` }] }],
]) it(`rejects ${label} without retry`, async () => {
    vi.mocked(atlas.get).mockResolvedValue({ data: value });
    await expect(getDiscoveryImageGrounding("sample")).rejects.toThrow("The image evidence could not be read.");
    expect(atlas.get).toHaveBeenCalledTimes(1);
});
it("honors public defaults for an unavailable binding", async () => {
    vi.mocked(atlas.get).mockResolvedValue({ data: { catalog_item_id: "sample", status: "no_deployment_binding" } });
    await expect(getDiscoveryImageGrounding("sample")).resolves.toEqual({ schema_version: response.schema_version, catalog_item_id: "sample", status: "no_deployment_binding",
        release_version: null, deployment_binding: null, observed_image: null, accepted_evidence: [] });
});
for (const status of ["no_deployment_binding", "no_strict_release_version", "no_repository_observation", "observation_mismatch", "mutable_observation", "no_image_release_evidence", "evidence_not_trusted", "evidence_version_mismatch", "repository_identity_mismatch", "digest_mismatch", "conflicted"]) {
    it(`preserves ${status} without promoting it to grounded`, async () => {
        const data = { ...response, status };
        vi.mocked(atlas.get).mockResolvedValue({ data });
        await expect(getDiscoveryImageGrounding("sample")).resolves.toEqual(data);
    });
}
for (const source_class of ["curated", "registry_attested", "upstream_signed"]) it(`retains ${source_class} and unrelated-release evidence in order`, async () => {
    const data = { ...response, accepted_evidence: [{ ...evidence, release_version: "1.0.0", image_digest: `sha256:${"2".repeat(64)}` }, { ...evidence, source_class }] };
    vi.mocked(atlas.get).mockResolvedValue({ data });
    await expect(getDiscoveryImageGrounding("sample")).resolves.toEqual(data);
});

it("honors the public deployment binding literal defaults", async () => {
    vi.mocked(atlas.get).mockResolvedValue({ data: { ...response, deployment_binding: { compose_file: binding.compose_file, compose_service: binding.compose_service } } });
    await expect(getDiscoveryImageGrounding("sample")).resolves.toEqual(response);
});
