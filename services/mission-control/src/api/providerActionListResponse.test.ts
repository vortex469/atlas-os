import { describe, expect, it } from "vitest";
import fixture from "../test/providerActionList.fixture.json";
import { parseProviderActionList, ProviderActionListResponseError } from "./providerActionListResponse";

const action = fixture[0];
describe("provider action list response", () => {
    it("reads complete native serializer output with defaults and open parameter extensions", () => {
        expect(parseProviderActionList(fixture)).toEqual(fixture);
        expect(parseProviderActionList([])).toEqual([]);
    });
    it("projects public fields and copies mutable parameter dictionaries", () => {
        const source = { ...fixture[1], private: "PRIVATE-ACTION-CANARY" };
        const result = parseProviderActionList([source])[0];
        expect(JSON.stringify(result)).not.toContain("PRIVATE-ACTION-CANARY");
        expect(result.enabled).toBe(false);
        expect(result.destructive).toBe(true);
        expect(result.requires_confirmation).toBe(true);
        expect(result.parameters).toEqual(source.parameters);
        expect(result.parameters).not.toBe(source.parameters);
        expect(result.parameters.model).not.toBe(source.parameters.model);
    });
    it.each([
        { name: "null", value: null }, { name: "object", value: {} },
        { name: "null entry", value: [null] }, { name: "array entry", value: [[]] },
        ...["id", "label", "description", "icon"].map(key => ({ name: `nonstring ${key}`, value: [{ ...action, [key]: {} }] })),
        ...["enabled", "requires_confirmation", "destructive"].flatMap(key => [undefined, null, "false", 0].map(value => ({ name: `invalid ${key}: ${value}`, value: [{ ...action, [key]: value }] }))),
        { name: "empty label", value: [{ ...action, label: "" }] },
        { name: "invalid native ID", value: [{ ...action, id: "run/diagnostics" }] },
        { name: "duplicate identity", value: [action, { ...action, requires_confirmation: true }] },
        { name: "null parameters", value: [{ ...action, parameters: null }] },
        { name: "array parameters", value: [{ ...action, parameters: [] }] },
        ...[null, "schema", []].map(value => ({ name: `unreadable definition ${value}`, value: [{ ...action, parameters: { model: value } }] })),
        ...["type", "description", "example"].map(key => ({ name: `unreadable parameter ${key}`, value: [{ ...action, parameters: { model: { [key]: { private: "PRIVATE-ACTION-CANARY" } } } }] })),
        { name: "unreadable required flag", value: [{ ...action, parameters: { model: { required: "true" } } }] },
    ])("rejects $name instead of publishing controls", ({ value }) => {
        expect(() => parseProviderActionList(value)).toThrow(ProviderActionListResponseError);
        expect(() => parseProviderActionList(value)).toThrow("Provider action list could not be read.");
    });
});
