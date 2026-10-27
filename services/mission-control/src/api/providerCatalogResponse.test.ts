import { describe, expect, it } from "vitest";
import fixture from "../test/providerCatalog.fixture.json";
import { parseProviderCatalog, ProviderCatalogResponseError } from "./providerCatalogResponse";

const provider = fixture[0];

describe("provider detail catalog response", () => {
    it("reads the complete native model including defaults and open native strings", () => {
        expect(parseProviderCatalog(fixture)).toEqual(fixture);
        expect(parseProviderCatalog([])).toEqual([]);
        const futureProvider = { ...provider, id: "future-provider-2", name: "  Future provider ✓  " };
        expect(parseProviderCatalog([futureProvider])[0]).toEqual(futureProvider);
    });
    it("projects known fields without sharing mutable capability or detail dictionaries", () => {
        const source = { ...fixture[1], private: "PRIVATE-CATALOG-CANARY", capabilities: ["resources"], health: { ...fixture[1].health, private: "PRIVATE-CATALOG-CANARY" } };
        const result = parseProviderCatalog([source])[0];
        expect(JSON.stringify(result)).not.toContain("PRIVATE-CATALOG-CANARY");
        expect(result.health.details).toEqual(source.health.details);
        expect(result.health.details).not.toBe(source.health.details);
        source.capabilities.push("changed");
        expect(result.capabilities).toEqual(["resources"]);
    });
    it.each([null, [], { status: {}, message: {}, latency_ms: Infinity, http_status: -1, details: null }].map(health => ({ health })))("preserves the unknown-health fallback for $health", ({ health }) => {
        expect(parseProviderCatalog([{ ...provider, health }])[0].health).toEqual({ status: "unknown", latency_ms: null, http_status: null, message: null, details: {} });
    });
    it.each([
        { name: "null", value: null }, { name: "object", value: {} },
        { name: "null provider", value: [null] }, { name: "array provider", value: [[]] },
        ...["id", "name", "workspace", "priority", "version", "description", "icon"].map(field => ({ name: `invalid ${field}`, value: [{ ...provider, [field]: { private: "PRIVATE-CATALOG-CANARY" } }] })),
        { name: "missing name", value: [{ ...provider, name: undefined }] },
        ...["", " ", "a/b", "..", "UPPER", "provider\n", "\ud800"].map(id => ({ name: `invalid identity ${JSON.stringify(id)}`, value: [{ ...provider, id }] })),
        ...["", " \t\n"].map(name => ({ name: `blank name ${JSON.stringify(name)}`, value: [{ ...provider, name }] })),
        { name: "missing capabilities", value: [{ ...provider, capabilities: undefined }] },
        { name: "null capabilities", value: [{ ...provider, capabilities: null }] },
        { name: "string capabilities", value: [{ ...provider, capabilities: "resources" }] },
        { name: "nonstring capability", value: [{ ...provider, capabilities: ["resources", {}] }] },
        { name: "duplicate identity", value: [provider, { ...provider, name: "Different provider" }] },
    ])("rejects $name with a controlled error", ({ value }) => {
        expect(() => parseProviderCatalog(value)).toThrow(ProviderCatalogResponseError);
        expect(() => parseProviderCatalog(value)).toThrow("Provider catalog response could not be read.");
    });
});
