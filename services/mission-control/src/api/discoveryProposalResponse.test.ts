import { beforeEach, expect, it, vi } from "vitest";
import { atlas } from "./atlas";
import { getDiscoveryProposal, listDiscoveryProposals } from "./discovery";
import { discoveryProposalFixture } from "../test/discoveryProposal.fixture";
vi.mock("./atlas", () => ({ atlas: { get: vi.fn() } }));
const proposal = discoveryProposalFixture();
beforeEach(() => vi.clearAllMocks());
for (const list of [true, false]) {
    const read = () => list ? listDiscoveryProposals(25) : getDiscoveryProposal(proposal.proposal_id);
    const wrap = (row: unknown) => list ? { proposals: [row], total: 1, limit: 25 } : row;
    it(`preserves a readable ${list ? "list" : "detail"} proposal`, async () => {
        const data = wrap(proposal);
        vi.mocked(atlas.get).mockResolvedValue({ data });
        await expect(read()).resolves.toEqual(data);
        expect(atlas.get).toHaveBeenCalledTimes(1);
    });
    for (const [label, row] of [
        ["null", null], ["wrong ID format", { ...proposal, proposal_id: "proposal" }],
        ["unknown destination", { ...proposal, destination_kind: "https://example.invalid" }],
        ["unknown status", { ...proposal, status: "approved" }],
        ["object reason", { ...proposal, reason: {} }],
        ["string false", { ...proposal, actionable_navigation: "false" }],
        ["string true", { ...proposal, actionable_navigation: "true" }],
        ["numeric flag", { ...proposal, actionable_navigation: 1 }],
        ["null hints", { ...proposal, target_hints: null }],
        ["object hint", { ...proposal, target_hints: [{ provider_hint: {} }] }],
        ["invalid date", { ...proposal, generated_at: "2026-02-30T00:00:00Z" }],
        ["reversed times", { ...proposal, expires_at: proposal.generated_at }],
        ["string count", { ...proposal, finding_reference_count: "1" }],
    ]) it(`rejects ${list ? "list" : "detail"} ${label} without retry`, async () => {
        vi.mocked(atlas.get).mockResolvedValue({ data: wrap(row) });
        await expect(read()).rejects.toThrow("The advisory proposal context could not be read.");
        expect(atlas.get).toHaveBeenCalledTimes(1);
    });
    it(`uses safe public defaults for ${list ? "list" : "detail"}`, async () => {
        const minimal = { ...proposal } as Record<string, unknown>;
        delete minimal.actionable_navigation; delete minimal.target_hints; delete minimal.intent_hint;
        vi.mocked(atlas.get).mockResolvedValue({ data: wrap(minimal) });
        const expected = { ...proposal, actionable_navigation: false, target_hints: [], intent_hint: null };
        await expect(read()).resolves.toEqual(wrap(expected));
    });
}
it("rejects a different detail identity", async () => {
    vi.mocked(atlas.get).mockResolvedValue({ data: discoveryProposalFixture({ proposal_id: `discovery-operator-proposal-${"b".repeat(64)}` }) });
    await expect(getDiscoveryProposal(proposal.proposal_id)).rejects.toThrow("The advisory proposal context could not be read.");
});
for (const data of [null, { proposals: null, total: 0, limit: 25 }, { proposals: [], total: "0", limit: 25 }, { proposals: [], total: 0, limit: 0 }]) {
    it("rejects an unreadable page envelope", async () => {
        vi.mocked(atlas.get).mockResolvedValue({ data });
        await expect(listDiscoveryProposals(25)).rejects.toThrow("The advisory proposal context could not be read.");
    });
}

for (const status of ["current", "stale", "expired", "not_actionable"] as const) {
    for (const destination_kind of ["discovery_detail", "compatibility_review", "operator_maintenance_selection"] as const) {
        it(`preserves Core's ${status} ${destination_kind} context`, async () => {
            const data = discoveryProposalFixture({ status, destination_kind, actionable_navigation: status === "current" });
            vi.mocked(atlas.get).mockResolvedValue({ data });
            await expect(getDiscoveryProposal(data.proposal_id)).resolves.toEqual(data);
        });
    }
}
it("does not silently deduplicate ambiguous proposal identities", async () => {
    vi.mocked(atlas.get).mockResolvedValue({ data: { proposals: [proposal, proposal], total: 2, limit: 25 } });
    await expect(listDiscoveryProposals(25)).rejects.toThrow("The advisory proposal context could not be read.");
});
