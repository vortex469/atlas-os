import { describe, expect, it } from "vitest";
import fixture from "../test/resourceInventory.fixture.json";
import { parseResourceInventory, ResourceInventoryResponseError } from "./resourceInventoryResponse";

const inventory = fixture[0], resource = inventory.resources[0];
describe("observed resource inventory response", () => {
    it.each(fixture.map((value, index) => ({ value, index })))("reads native public model $index as a read-only projection", ({ value }) => {
        const result = parseResourceInventory(value, "proxmox");
        expect(value).toMatchObject(result);
        expect(result).not.toHaveProperty("intent_authority");
        for (const row of result.resources) {
            expect(row.expectation).not.toHaveProperty("mutation_available");
            expect(row).not.toHaveProperty("identity");
        }
    });
    it("copies metadata and discards unknown public extensions", () => {
        const value = { ...inventory, private: "PRIVATE-INVENTORY-CANARY", resources: [{ ...resource, private: "PRIVATE-INVENTORY-CANARY" }] };
        const result = parseResourceInventory(value, "proxmox");
        expect(JSON.stringify(result)).not.toContain("PRIVATE-INVENTORY-CANARY");
        expect(result.metadata).not.toBe(value.metadata);
        expect(result.resources[0].metadata).not.toBe(resource.metadata);
    });
    it("accepts the native unavailable expectation without deriving editing authority", () => {
        const result = parseResourceInventory(fixture[2], "proxmox");
        expect(result.resources[0].expectation.state).toBe("unavailable");
        expect(result.resources[0].expectation.value).toBeNull();
    });
    it.each([
        { name: "null", value: null }, { name: "array", value: [] },
        { name: "wrong provider", value: { ...inventory, provider_id: "docker" } },
        { name: "foreign row", value: { ...inventory, resources: [{ ...resource, provider_id: "docker" }] } },
        ...["provider_id", "resource_type", "resource_id"].map(key => ({ name: `ambiguous coordinate ${key}`, value: { ...inventory, resources: [{ ...resource, [key]: `bad\u0000coordinate` }] } })),
        { name: "duplicate coordinate", value: { ...inventory, resources: [resource, resource] } },
        { name: "invalid date", value: { ...inventory, refreshed_at: "2026-02-30T12:00:00Z" } },
        { name: "zero year", value: { ...inventory, refreshed_at: "0000-01-01T00:00:00Z" } },
        { name: "null resources", value: { ...inventory, resources: null } },
        { name: "null row", value: { ...inventory, resources: [null] } },
        ...["resource_type", "resource_id", "display_name", "current_state"].map(key => ({ name: `invalid ${key}`, value: { ...inventory, resources: [{ ...resource, [key]: { private: "PRIVATE-INVENTORY-CANARY" } }] } })),
        { name: "empty state", value: { ...inventory, resources: [{ ...resource, current_state: "" }] } },
        ...["configured", "missing", "needs_review"].map(key => ({ name: `nonboolean ${key}`, value: { ...inventory, resources: [{ ...resource, [key]: "false" }] } })),
        { name: "invalid expectation state", value: { ...inventory, resources: [{ ...resource, expectation: { ...resource.expectation, state: "future_state" } }] } },
        { name: "invalid expectation value", value: { ...inventory, resources: [{ ...resource, expectation: { ...resource.expectation, value: {} } }] } },
        { name: "invalid option flag", value: { ...inventory, resources: [{ ...resource, expectation: { ...resource.expectation, allowed_values: [{ value: "running", label: "Running", description: "", terminal: "false" }] } }] } },
        { name: "duplicate options", value: { ...inventory, resources: [{ ...resource, expectation: { ...resource.expectation, allowed_values: [...resource.expectation.allowed_values, ...resource.expectation.allowed_values] } }] } },
        { name: "null metadata", value: { ...inventory, metadata: null } },
        { name: "null row metadata", value: { ...inventory, resources: [{ ...resource, metadata: null }] } },
        { name: "unsafe count", value: { ...inventory, summary: { ...inventory.summary, total: Number.MAX_SAFE_INTEGER + 1 } } },
        { name: "negative count", value: { ...inventory, summary: { ...inventory.summary, configured: -1 } } },
        { name: "fractional grouped count", value: { ...inventory, summary: { ...inventory.summary, by_type: { qemu: 0.5 } } } },
        { name: "nonfinite count", value: { ...inventory, summary: { ...inventory.summary, total: Infinity } } },
    ])("rejects $name with a controlled error", ({ value }) => {
        expect(() => parseResourceInventory(value, "proxmox")).toThrow(ResourceInventoryResponseError);
        expect(() => parseResourceInventory(value, "proxmox")).toThrow("Observed resource inventory could not be read.");
    });
});
