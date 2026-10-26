import { beforeEach, describe, expect, it, vi } from "vitest";
import { atlas } from "./atlas";
import { getDiscoveryMetadata } from "./discovery";
import { DiscoveryMetadataResponseError } from "./discoveryMetadataResponse";
import nativeFixture from "../test/discoveryMetadata.fixture.json";

vi.mock("./atlas", () => ({ atlas: { get: vi.fn() } }));
describe("Discovery summary read contract", () => {
    beforeEach(() => vi.clearAllMocks());
    it("reads the native public DTO fixture and keeps the existing endpoint", async () => {
        vi.mocked(atlas.get).mockResolvedValue({ data: nativeFixture });
        await expect(getDiscoveryMetadata()).resolves.toEqual(nativeFixture);
        expect(atlas.get).toHaveBeenCalledWith("/discovery");
    });
    it("honors the public schema-version default and projects recognized fields", async () => {
        vi.mocked(atlas.get).mockResolvedValue({ data: { catalog_loaded: false, entry_count: 0, extra: "private" } });
        await expect(getDiscoveryMetadata()).resolves.toEqual({ catalog_loaded: false, entry_count: 0, schema_version: 1 });
    });
    it.each([null, [], {}, { ...nativeFixture, catalog_loaded: "false" }, { ...nativeFixture, catalog_loaded: null },
        { ...nativeFixture, entry_count: -1 }, { ...nativeFixture, entry_count: 0.5 }, { ...nativeFixture, entry_count: "2" },
        { ...nativeFixture, entry_count: {} }, { ...nativeFixture, entry_count: Number.MAX_SAFE_INTEGER + 1 },
        { ...nativeFixture, schema_version: null }, { ...nativeFixture, schema_version: "1" },
        { ...nativeFixture, schema_version: 1.5 },
    ])("rejects malformed successful summaries", async value => {
        vi.mocked(atlas.get).mockResolvedValue({ data: value });
        await expect(getDiscoveryMetadata()).rejects.toBeInstanceOf(DiscoveryMetadataResponseError);
    });
    it("retains an explicitly reported integer schema version without inventing compatibility", async () => {
        vi.mocked(atlas.get).mockResolvedValue({ data: { ...nativeFixture, schema_version: 2 } });
        await expect(getDiscoveryMetadata()).resolves.toEqual({ ...nativeFixture, schema_version: 2 });
    });
    it("does not automatically retry a failed read", async () => {
        vi.mocked(atlas.get).mockRejectedValue(new Error("offline"));
        await expect(getDiscoveryMetadata()).rejects.toThrow("offline");
        expect(atlas.get).toHaveBeenCalledTimes(1);
    });
});
