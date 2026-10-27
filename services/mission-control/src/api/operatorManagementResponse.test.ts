import { describe, expect, it } from "vitest";
import fixture from "../test/operatorManagement.fixture.json";
import { parseProviderManagementV3 } from "./providerManagement";

const descriptor = fixture[0];
const resource = descriptor.resources[0];
const withRow = (change: Record<string, unknown>) => ({ ...descriptor, resources: [{ ...resource, ...change }] });
const withSupport = (change: Record<string, unknown>) => ({ ...descriptor, resource_types: [{ ...descriptor.resource_types[0], ...change }] });

describe("operator management response", () => {
    it.each(fixture.map((value, index) => ({ value, index })))("accepts serialized native snapshot $index", ({ value }) => {
        expect(parseProviderManagementV3(value, "proxmox")).toEqual(value);
    });
    it("returns independent validated collections", () => {
        const parsed = parseProviderManagementV3(descriptor, "proxmox");
        expect(parsed.resources).not.toBe(descriptor.resources);
        expect(parsed.resources[0]).not.toBe(resource);
        expect(parsed.resource_types[0]).not.toBe(descriptor.resource_types[0]);
    });
    it("preserves native Unicode ordering for resource coordinates", () => {
        const value = { ...descriptor, resources: [{ ...resource, resource_id: "\ue000" }, { ...resource, resource_id: "\u{10000}" }] };
        expect(parseProviderManagementV3(value, "proxmox").resources.map(row => row.resource_id)).toEqual(["\ue000", "\u{10000}"]);
    });
    it("binds the descriptor to the requested provider", () => {
        expect(() => parseProviderManagementV3(descriptor, "docker")).toThrow();
    });
    it.each([
        { name: "null", value: null }, { name: "array", value: [] },
        { name: "schema", value: { ...descriptor, schema_version: "provider-management-v2" } },
        { name: "root capability type", value: { ...descriptor, caller_has_provider_intent_update: "false" } },
        { name: "root permission", value: { ...descriptor, grants_permission: true } },
        { name: "root execution", value: { ...descriptor, grants_execution: true } },
        { name: "root extension", value: { ...descriptor, csrf_token: "private" } },
        { name: "sections", value: { ...descriptor, sections: [] } },
        { name: "resources", value: { ...descriptor, resources: {} } },
        { name: "resource types", value: { ...descriptor, resource_types: null } },
        { name: "caller mutation type", value: withRow({ caller_can_mutate: { value: true } }) },
        { name: "editability type", value: withRow({ editable_in_principle: "false" }) },
        { name: "liveness type", value: withRow({ resource_live: 1 }) },
        { name: "support type", value: withRow({ provider_intent_mutation_supported: [] }) },
        { name: "unknown readiness", value: withRow({ mutation_readiness: "maybe" }) },
        { name: "resource permission", value: withRow({ grants_permission: true }) },
        { name: "resource execution", value: withRow({ grants_execution: true }) },
        { name: "resource extension", value: withRow({ extra: false }) },
        { name: "foreign resource", value: withRow({ provider_id: "docker" }) },
        { name: "ambiguous id", value: withRow({ resource_id: "110\u0000qemu" }) },
        { name: "ambiguous type", value: withRow({ resource_type: "qemu\u0000" }) },
        { name: "missing fingerprint", value: withRow({ management_fingerprint: null }) },
        { name: "live missing", value: withRow({ missing: true }) },
        { name: "unsupported readiness", value: withRow({ provider_intent_mutation_supported: false }) },
        { name: "false ready editability", value: withRow({ editable_in_principle: false }) },
        { name: "unsafe ready identity", value: withRow({ identity_assurance: "unavailable", management_fingerprint: null }) },
        { name: "unready mutation", value: withRow({ mutation_readiness: "store_unavailable", editable_in_principle: false }) },
        { name: "root capability disagreement", value: { ...descriptor, caller_has_provider_intent_update: false } },
        { name: "activation disagreement", value: { ...descriptor, provider_intent_activation: "not_activated" } },
        { name: "authority disagreement", value: { ...descriptor, provider_intent_authority_status: "unavailable" } },
        { name: "duplicate rows", value: { ...descriptor, resources: [resource, resource] } },
        { name: "unordered rows", value: { ...descriptor, resources: [{ ...resource, resource_id: "111" }, resource] } },
        { name: "unsafe version", value: { ...fixture[9], resources: [{ ...fixture[9].resources[0], record_version: Number.MAX_SAFE_INTEGER + 1 }] } },
        { name: "invalid display", value: withRow({ display_name: { private: true } }) },
        { name: "invalid history", value: withRow({ replacement_detected: true }) },
        { name: "contradictory reason", value: withRow({ intent_reason: "matching_active_intent" }) },
        { name: "type flag", value: withSupport({ provider_intent_mutation_supported: "true" }) },
        { name: "type extension", value: withSupport({ extra: false }) },
        { name: "foreign type", value: withSupport({ provider_id: "docker" }) },
        { name: "unsupported identity", value: withSupport({ authoritative_identity_supported: false }) },
        { name: "unsupported mutation type", value: withSupport({ resource_type: "lxc" }) },
        { name: "duplicate supported expectations", value: withSupport({ supported_expectations: ["running", "running"] }) },
        { name: "duplicate support", value: { ...descriptor, resource_types: [descriptor.resource_types[0], descriptor.resource_types[0]] } },
    ])("rejects $name", ({ value }) => {
        expect(() => parseProviderManagementV3(value, "proxmox")).toThrow();
    });
});
