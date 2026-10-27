import { afterEach, expect, it, vi } from "vitest";
import { atlas } from "./atlas";
import { getProviderResources, refreshProviderResources } from "./resources";

const resource = { provider_id: "proxmox", resource_type: "qemu", resource_id: "110", display_name: "Media server", current_state: "running",
    expectation: { value: null, label: "Needs Review", state: "needs_review", allowed_values: [] }, configured: false, missing: false, needs_review: true, metadata: {} };
const inventory = { provider_id: "proxmox", provider_name: "Proxmox", refreshed_at: "2026-10-27T00:00:00Z", resources: [resource],
    summary: { total: 1, configured: 0, needs_review: 1, missing: 0, ignored: 0, by_type: { qemu: 1 }, by_state: { running: 1 } }, metadata: {} };
afterEach(() => vi.restoreAllMocks());
for (const operation of ["read", "refresh"] as const) {
    it.each([
        { name: "invalid display name", value: { ...inventory, resources: [{ ...resource, display_name: { private: "PRIVATE-INVENTORY-CANARY" } }] } },
        { name: "invalid observed state", value: { ...inventory, resources: [{ ...resource, current_state: {} }] } },
        { name: "wrong provider", value: { ...inventory, provider_id: "docker" } },
        { name: "invalid timestamp", value: { ...inventory, refreshed_at: "2026-02-30T12:00:00Z" } },
        { name: "duplicate coordinate", value: { ...inventory, resources: [resource, resource] } },
    ])(`${operation} rejects $name before publishing inventory`, async ({ value }) => {
        vi.spyOn(atlas, operation === "read" ? "get" : "post").mockResolvedValue({ data: value });
        await expect((operation === "read" ? getProviderResources : refreshProviderResources)("proxmox")).rejects.toThrow();
    });
    it(`${operation} keeps the existing provider-scoped request`, async () => {
        const request = vi.spyOn(atlas, operation === "read" ? "get" : "post").mockResolvedValue({ data: inventory });
        expect(await (operation === "read" ? getProviderResources : refreshProviderResources)("proxmox")).toEqual(inventory);
        expect(request).toHaveBeenCalledExactlyOnceWith(operation === "read" ? "/providers/proxmox/resources" : "/providers/proxmox/discovery/refresh");
    });
}
