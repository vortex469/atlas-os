import { beforeEach, expect, it, vi } from "vitest";
import { atlas } from "./atlas";
import { getDiscoveryCompatibility } from "./discovery";
vi.mock("./atlas", () => ({ atlas: { get: vi.fn() } }));
const finding = { id: "f1", check_type: "future_check", severity: "future_severity", status: "future_status", subject: "host", message: "Unknown host state", evidence_ids: ["e1"] };
const evidence = { id: "e1", check_type: "future_check", subject: "host", status: "future_status", message: "Reported fact", source: "fixture" };
const assessment = { item_id: "sample", target_id: "atlas", target_type: "atlas", status: "future_status", checked_at: "2026-10-27T12:00:00Z", findings: [finding], evidence: [evidence], unknown_facts: ["Host unknown"], additive: "retained" };
beforeEach(() => vi.clearAllMocks());
it("preserves readable future labels and additive metadata", async () => {
    vi.mocked(atlas.get).mockResolvedValue({ data: assessment });
    await expect(getDiscoveryCompatibility("sample")).resolves.toEqual(assessment);
    expect(atlas.get).toHaveBeenCalledWith("/discovery/items/sample/compatibility", { params: undefined });
});
for (const [label, value] of [
    ["null", null], ["array", []], ["missing identity", {}],
    ["another item", { ...assessment, item_id: "other" }],
    ["another target", { ...assessment, target_id: "other" }],
    ["object status", { ...assessment, status: {} }],
    ["null findings", { ...assessment, findings: null }],
    ["object evidence", { ...assessment, evidence: {} }],
    ["object unknown fact", { ...assessment, unknown_facts: [{}] }],
    ["null finding", { ...assessment, findings: [null] }],
    ["null evidence", { ...assessment, evidence: [null] }],
    ["missing evidence IDs", { ...assessment, findings: [{ ...finding, evidence_ids: null }] }],
    ["object severity", { ...assessment, findings: [{ ...finding, severity: {} }] }],
    ["object evidence message", { ...assessment, evidence: [{ ...evidence, message: {} }] }],
    ["duplicate finding identity", { ...assessment, findings: [finding, finding] }],
    ["duplicate evidence identity", { ...assessment, evidence: [evidence, evidence] }],
]) it(`rejects ${label} without retry`, async () => {
    vi.mocked(atlas.get).mockResolvedValue({ data: value });
    await expect(getDiscoveryCompatibility("sample")).rejects.toThrow("The compatibility result could not be read. Try again.");
    expect(atlas.get).toHaveBeenCalledTimes(1);
});
it("honors public empty-array defaults", async () => {
    const minimal = Object.fromEntries(Object.entries(assessment).filter(([key]) => !["findings", "evidence", "unknown_facts"].includes(key)));
    vi.mocked(atlas.get).mockResolvedValue({ data: minimal });
    await expect(getDiscoveryCompatibility("sample")).resolves.toEqual({ ...minimal, findings: [], evidence: [], unknown_facts: [] });
});
it("binds the normalized requested target without changing the request", async () => {
    vi.mocked(atlas.get).mockResolvedValue({ data: { ...assessment, target_id: "lab" } });
    await expect(getDiscoveryCompatibility("sample", " lab ")).resolves.toMatchObject({ target_id: "lab" });
    expect(atlas.get).toHaveBeenCalledWith("/discovery/items/sample/compatibility", { params: { target: "lab" } });
});
