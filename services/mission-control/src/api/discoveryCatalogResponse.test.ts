import { beforeEach, expect, it, vi } from "vitest";
import { atlas } from "./atlas";
import { listDiscoveryItems, searchDiscoveryItems } from "./discovery";

vi.mock("./atlas", () => ({ atlas: { get: vi.fn() } }));
const entry = { item: { id: "future-item", name: "Future item", type: "future_type", status: "future_status",
    description: "Description", capabilities: ["future"], tags: [] }, additive: { retained: true } };
const pagination = { total: 1, limit: 25, offset: 0, has_more: false };
beforeEach(() => vi.clearAllMocks());
for (const search of [false, true]) {
    const read = () => search ? searchDiscoveryItems({ q: "future" }) : listDiscoveryItems();
    const response = (entries: unknown[]) => ({ ...pagination, ...(search ? { results: entries.map(entry => ({ entry })) } : { entries }) });
    it(`preserves readable ${search ? "search" : "list"} data and future labels`, async () => {
        const data = response([entry]);
        vi.mocked(atlas.get).mockResolvedValue({ data });
        await expect(read()).resolves.toBe(data);
        expect(atlas.get).toHaveBeenCalledTimes(1);
        expect(atlas.get).toHaveBeenCalledWith(search ? "/discovery/search" : "/discovery/items", {
            params: { q: search ? "future" : undefined, limit: 25, offset: 0,
                type: undefined, status: undefined, tag: undefined, capability: undefined },
        });
    });
    it(`accepts empty ${search ? "search" : "list"} pages`, async () => {
        const data = { ...response([]), total: 0 };
        vi.mocked(atlas.get).mockResolvedValue({ data });
        await expect(read()).resolves.toBe(data);
    });
    for (const [label, data] of [
        ["null page", null], ["missing collection", pagination], ["null entry", response([null])],
        ["missing item", response([{}])], ["object name", response([{ ...entry, item: { ...entry.item, name: {} } }])],
        ["missing capabilities", response([{ ...entry, item: { ...entry.item, capabilities: null } }])],
        ["object tag", response([{ ...entry, item: { ...entry.item, tags: [{}] } }])],
        ["numeric type", response([{ ...entry, item: { ...entry.item, type: 1 } }])],
        ["bad pagination", { ...response([entry]), total: "1" }],
        ["false-string has_more", { ...response([entry]), has_more: "false" }],
        ["negative total", { ...response([entry]), total: -1 }],
        ["zero limit", { ...response([entry]), limit: 0 }],
        ["fractional offset", { ...response([entry]), offset: 0.5 }],
        ["blank identity", response([{ ...entry, item: { ...entry.item, id: " " } }])],
    ]) it(`rejects ${search ? "search" : "list"}: ${label}`, async () => {
        vi.mocked(atlas.get).mockResolvedValue({ data });
        await expect(read()).rejects.toThrow("The catalog results could not be read. Try again.");
        expect(atlas.get).toHaveBeenCalledTimes(1);
    });
}
