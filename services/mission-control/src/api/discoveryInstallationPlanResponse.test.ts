import { beforeEach, expect, it, vi } from "vitest";
import { atlas } from "./atlas";
import { getDiscoveryInstallationPlan } from "./discovery";
import { FINGERPRINT, homeAssistantGoldenPlan } from "../test/installationPlan.fixture";
vi.mock("./atlas", () => ({ atlas: { get: vi.fn() } }));
const plan = homeAssistantGoldenPlan();
beforeEach(() => vi.clearAllMocks());
it("preserves the existing native fixture and exact fingerprint without repair or reordering", async () => {
    const before = JSON.stringify(plan);
    vi.mocked(atlas.get).mockResolvedValue({ data: plan });
    await expect(getDiscoveryInstallationPlan("home-assistant")).resolves.toBe(plan);
    expect(JSON.stringify(plan)).toBe(before);
    expect(plan.fingerprint.value).toBe(FINGERPRINT);
    expect(atlas.get).toHaveBeenCalledWith("/discovery/items/home-assistant/installation-plan");
});
for (const collection of ["accepted_evidence", "provenance", "compatibility", "prerequisites", "relationships", "assumptions", "blockers", "risks", "missing_facts", "required_operator_confirmations"]) {
    it(`rejects unreadable ${collection} without retry`, async () => {
        vi.mocked(atlas.get).mockResolvedValue({ data: { ...plan, [collection]: null } });
        await expect(getDiscoveryInstallationPlan("home-assistant")).rejects.toThrow("The installation plan could not be read.");
        expect(atlas.get).toHaveBeenCalledTimes(1);
    });
    it(`does not fill missing ${collection} with invented empty facts`, async () => {
        const data = { ...plan } as Record<string, unknown>;
        delete data[collection];
        vi.mocked(atlas.get).mockResolvedValue({ data });
        await expect(getDiscoveryInstallationPlan("home-assistant")).rejects.toThrow("The installation plan could not be read.");
    });
}
for (const [label, value] of [
    ["null", null], ["unknown schema", { ...plan, schema_version: "future" }],
    ["another item", { ...plan, application: { ...plan.application, item_id: "other" } }],
    ["invalid fingerprint", { ...plan, fingerprint: { ...plan.fingerprint, value: "not-a-fingerprint" } }],
    ["unknown canonicalization", { ...plan, fingerprint: { ...plan.fingerprint, canonicalization: "future" } }],
    ["object status", { ...plan, status: {} }],
    ["unknown status", { ...plan, status: "future" }],
    ["excess evidence", { ...plan, accepted_evidence: Array.from({ length: 33 }, () => plan.accepted_evidence[0]) }],
    ["status hides blockers", { ...plan, status: "plan_ready_for_review" }],
    ["missing artifact", { ...plan, deployment_artifact: null }],
    ["object name", { ...plan, application: { ...plan.application, display_name: {} } }],
    ["string relationship flag", { ...plan, relationships: [{ ...plan.relationships[0], required: "false" }] }],
    ["object confirmation prompt", { ...plan, required_operator_confirmations: [{ ...plan.required_operator_confirmations[0], prompt: {} }] }],
    ["object blocker", { ...plan, blockers: [{ code: {}, subject: "home-assistant" }] }],
    ["numeric optional image field", { ...plan, image: { ...plan.image, reference: 1 } }],
    ["string evidence freshness", { ...plan, accepted_evidence: [{ ...plan.accepted_evidence[0], freshness_window_seconds: "60" }] }],
]) it(`rejects ${label} before enabling plan-dependent views`, async () => {
    vi.mocked(atlas.get).mockResolvedValue({ data: value });
    await expect(getDiscoveryInstallationPlan("home-assistant")).rejects.toThrow("The installation plan could not be read.");
    expect(atlas.get).toHaveBeenCalledTimes(1);
});
