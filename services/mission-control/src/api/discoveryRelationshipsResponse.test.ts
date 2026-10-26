import { beforeEach, describe, expect, it, vi } from "vitest";
import { atlas } from "./atlas";
import { getDiscoveryRelationships } from "./discovery";
import { DiscoveryRelationshipsResponseError, parseDiscoveryRelationships } from "./discoveryRelationshipsResponse";
import nativeFixture from "../test/discoveryRelationships.fixture.json";

vi.mock("./atlas", () => ({ atlas: { get: vi.fn() } }));
const reference = { source_item_id: "frigate", target: "mqtt", resolved: false,
    relationship: { type: "depends_on", target: "mqtt" } };
const response = { item_id: "frigate", outgoing: [reference] };

describe("Discovery relationships response contract", () => {
    beforeEach(() => vi.clearAllMocks());
    it("accepts Core's generated public DTO fixture for all relationship types", () => {
        expect(parseDiscoveryRelationships(nativeFixture, "frigate")).toEqual(nativeFixture);
    });
    it("honors public DTO defaults without inventing a resolved target", () => {
        expect(parseDiscoveryRelationships(response, "frigate")).toEqual({ item_id: "frigate", incoming: [], outgoing: [{
            ...reference, resolved_target_item_id: null, relationship: { ...reference.relationship, required: true,
                minimum_version: null, maximum_version: null, description: "", metadata: {} },
        }] });
        expect(parseDiscoveryRelationships({ item_id: "frigate" }, "frigate")).toEqual({ item_id: "frigate", incoming: [], outgoing: [] });
    });
    it("does not carry additive response properties into the UI projection", () => {
        expect(parseDiscoveryRelationships({ ...response, extra: "private" }, "frigate")).not.toHaveProperty("extra");
    });
    it.each([null, [], {}, { ...response, item_id: "other" }, { ...response, incoming: null },
        { ...response, outgoing: {} }, { ...response, outgoing: [null] },
        { ...response, outgoing: [{ ...reference, relationship: null }] },
    ])("rejects malformed or unrelated collections", value => {
        expect(() => parseDiscoveryRelationships(value, "frigate")).toThrow(DiscoveryRelationshipsResponseError);
    });
    it.each([
        ["source_item_id", 1], ["target", {}], ["resolved", "false"], ["resolved_target_item_id", 1],
    ])("rejects malformed reference field %s", (field, value) => {
        expect(() => parseDiscoveryRelationships({ ...response, outgoing: [{ ...reference, [field]: value }] }, "frigate"))
            .toThrow(DiscoveryRelationshipsResponseError);
    });
    it.each([
        ["type", "unknown"], ["target", {}], ["required", "true"], ["minimum_version", false],
        ["maximum_version", []], ["description", {}], ["metadata", []],
    ])("rejects malformed relationship field %s", (field, value) => {
        expect(() => parseDiscoveryRelationships({ ...response, incoming: [{ ...reference, relationship: { ...reference.relationship, [field]: value } }] }, "frigate"))
            .toThrow(DiscoveryRelationshipsResponseError);
    });
    it("binds SDK reads to the requested item and keeps the existing filter request", async () => {
        vi.mocked(atlas.get).mockResolvedValue({ data: response });
        await expect(getDiscoveryRelationships("frigate", "depends_on")).resolves.toMatchObject({ item_id: "frigate" });
        expect(atlas.get).toHaveBeenCalledWith("/discovery/items/frigate/relationships", { params: { type: "depends_on" } });
        vi.mocked(atlas.get).mockResolvedValue({ data: { ...response, item_id: "other" } });
        await expect(getDiscoveryRelationships("frigate")).rejects.toBeInstanceOf(DiscoveryRelationshipsResponseError);
    });
    it.each([null, { ...response, outgoing: [{ ...reference, relationship: null }] }])("rejects malformed successful SDK responses", async value => {
        vi.mocked(atlas.get).mockResolvedValue({ data: value });
        await expect(getDiscoveryRelationships("frigate")).rejects.toBeInstanceOf(DiscoveryRelationshipsResponseError);
    });
    it("does not retry a failed read automatically", async () => {
        vi.mocked(atlas.get).mockRejectedValue(new Error("offline"));
        await expect(getDiscoveryRelationships("frigate")).rejects.toThrow("offline");
        expect(atlas.get).toHaveBeenCalledTimes(1);
    });
});
