import { describe, expect, it } from "vitest";
import type { AtlasPolicies } from "../types/policies";
import fixture from "../test/policies.fixture.json";
import { parsePolicies, PoliciesResponseError } from "./policiesResponse";

describe("policy snapshot response", () => {
    it.each(fixture.map((value, index) => ({ value, index })))("reads native public model $index", ({ value }) => {
        expect(parsePolicies(value)).toEqual(value);
    });
    it("preserves legal dictionary keys and ignores extensions without retaining shared references", () => {
        const source = structuredClone(fixture[1]) as AtlasPolicies;
        const input = { ...source, private: "PRIVATE-POLICY-CANARY", docker: { containers: JSON.parse('{"__proto__":{"expected":"running","private":"hidden"}}') } };
        const result = parsePolicies(input);
        expect(Object.keys(result.docker.containers)).toEqual(["__proto__"]);
        expect(Object.getPrototypeOf(result.docker.containers)).toBe(Object.prototype);
        expect(Object.getOwnPropertyDescriptor(result.docker.containers, "__proto__")?.value).toEqual({ expected: "running" });
        expect(JSON.stringify(result)).not.toMatch(/private|hidden|CANARY/);
        source.homeassistant.ignored_entities.push("changed");
        expect(result.homeassistant.ignored_entities).toEqual(["sensor.power"]);
    });
    it.each(Object.keys(fixture[0]).map(section => ({ section })))("rejects missing serialized section $section", ({ section }) => {
        const input: Record<string, unknown> = { ...fixture[0] };
        delete input[section];
        expect(() => parsePolicies(input)).toThrow(PoliciesResponseError);
    });
    it.each([
        { name: "null", value: null },
        { name: "array", value: [] },
        { name: "nested null", value: { ...fixture[0], proxmox: { guests: { "110": null } } } },
        { name: "invalid guest state", value: { ...fixture[0], proxmox: { guests: { "110": { expected: "active" } } } } },
        { name: "ignored container", value: { ...fixture[0], docker: { containers: { atlas: { expected: "ignored" } } } } },
        { name: "entity nonstring", value: { ...fixture[0], homeassistant: { ignored_entities: [null] } } },
        { name: "invalid severity", value: { ...fixture[0], opnsense: { pending_update_warning_threshold: null, reboot_required_severity: "severe" } } },
        { name: "zero update count", value: { ...fixture[0], opnsense: { pending_update_warning_threshold: 0, reboot_required_severity: "warning" } } },
        { name: "fractional count", value: { ...fixture[0], obsidian: { ...fixture[0].obsidian, minimum_note_count: 1.2 } } },
        { name: "unsafe count", value: { ...fixture[0], obsidian: { ...fixture[0].obsidian, minimum_note_count: Number.MAX_SAFE_INTEGER + 1 } } },
        { name: "missing nullable field", value: { ...fixture[0], obsidian: { ...fixture[0].obsidian, stale_after_days: undefined } } },
        { name: "duplicate collections", value: { ...fixture[0], qdrant: { ...fixture[0].qdrant, expected_collections: ["notes", "notes"] } } },
        { name: "empty workflow", value: { ...fixture[0], n8n: { ...fixture[0].n8n, expected_active_workflows: [""] } } },
        ...[null, "10", 0, -1, Infinity, NaN].map(value => ({ name: `invalid duration ${value}`, value: { ...fixture[0], intelligence: { providers: { proxmox: { maximum_collection_duration_ms: value, severity: "info" } } } } })),
        { name: "negative fps", value: { ...fixture[0], frigate: { ...fixture[0].frigate, cameras: { front: { expected: "active", minimum_camera_fps: -1, minimum_process_fps: 0 } } } } },
    ])("rejects $name without reflecting the response", ({ value }) => {
        expect(() => parsePolicies(value)).toThrow("Policy settings response could not be read.");
    });
});
