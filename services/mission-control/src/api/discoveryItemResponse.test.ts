import { beforeEach, expect, it, vi } from "vitest";
import { atlas } from "./atlas";
import { getDiscoveryItem } from "./discovery";
vi.mock("./atlas", () => ({ atlas: { get: vi.fn() } }));
const entry = { schema_version: 1, item: { id: "sample", name: "Sample", type: "future_type", status: "future_status",
    description: "Example", tags: [], capabilities: [], requirements: { capabilities: [], resources: { gpu_required: false },
        platform: { architectures: [], operating_systems: [], runtimes: [], devices: [] }, network: { ports: [], notes: ["LAN only"] } }, metadata: {} },
    provenance: { source_type: "curated", source: "fixture", trust_level: "curated" }, metadata: {} };
beforeEach(() => vi.clearAllMocks());
it("accepts public network notes arrays and future item labels", async () => {
    vi.mocked(atlas.get).mockResolvedValue({ data: entry });
    await expect(getDiscoveryItem("sample")).resolves.toEqual(entry);
    expect(atlas.get).toHaveBeenCalledWith("/discovery/items/sample");
});
for (const [label, data] of [
    ["missing entry", null], ["missing item", {}],
    ["object tag", { ...entry, item: { ...entry.item, tags: [{}] } }],
    ["missing requirements", { ...entry, item: { ...entry.item, requirements: null } }],
    ["bad platform", { ...entry, item: { ...entry.item, requirements: { ...entry.item.requirements, platform: { architectures: {} } } } }],
    ["bad capabilities", { ...entry, item: { ...entry.item, requirements: { ...entry.item.requirements, capabilities: [null] } } }],
    ["bad provenance", { ...entry, provenance: null }],
    ["object notes", { ...entry, metadata: { catalog_notes: [{}] } }],
    ["string approval-like review flag", { ...entry, metadata: { reviewed_for_d5: "false" } }],
]) it(`rejects ${label} before rendering`, async () => {
    vi.mocked(atlas.get).mockResolvedValue({ data });
    await expect(getDiscoveryItem("sample")).rejects.toThrow("The catalog item could not be read. Reload to try again.");
    expect(atlas.get).toHaveBeenCalledTimes(1);
});

it("uses public DTO defaults without inventing review or compatibility", async () => {
    const data = { schema_version: 1, item: { id: "sample", name: "Sample", type: "application", status: "active" }, provenance: entry.provenance };
    vi.mocked(atlas.get).mockResolvedValue({ data });
    const parsed = await getDiscoveryItem("sample");
    expect(parsed.item.tags).toEqual([]);
    expect(parsed.item.requirements.platform.runtimes).toEqual([]);
    expect(parsed.item.requirements.resources.gpu_required).toBe(false);
    expect(parsed.metadata).toEqual({});
    expect(parsed.metadata.reviewed_for_d5).toBeUndefined();
});
it("keeps the item identity mismatch separate from unreadable fields", async () => {
    vi.mocked(atlas.get).mockResolvedValue({ data: { item: { id: "other" } } });
    await expect(getDiscoveryItem("sample")).rejects.toThrow("does not match this item");
});
it("preserves explicit false review state and additive metadata", async () => {
    vi.mocked(atlas.get).mockResolvedValue({ data: { ...entry, metadata: { reviewed_for_d5: false, future: "retained" } } });
    await expect(getDiscoveryItem("sample")).resolves.toMatchObject({ metadata: { reviewed_for_d5: false, future: "retained" } });
});
for (const [field, value] of [
    ["resources", { gpu_required: "false" }], ["resources", { memory_mb_min: "128" }],
    ["network", { ports: [{ port: 80, protocol: {}, direction: "inbound", required: true }] }],
    ["network", { ports: [{ port: "80", protocol: "tcp", direction: "inbound", required: true }] }],
    ["network", { requires_internet: "false" }], ["network", { notes: [{}] }],
]) it(`rejects malformed requirement ${field} ${JSON.stringify(value)}`, async () => {
    vi.mocked(atlas.get).mockResolvedValue({ data: { ...entry, item: { ...entry.item,
        requirements: { ...entry.item.requirements, [field as string]: value } } } });
    await expect(getDiscoveryItem("sample")).rejects.toThrow("The catalog item could not be read.");
});
