import { beforeEach, describe, expect, it, vi } from "vitest";
import { atlas } from "./atlas";
import { getProviderConnection, testProviderConnection, updateProviderConnection } from "./connections";
import { ConnectionResponseError, parseConnectionSave, parseConnectionSchema, parseConnectionTest } from "./connectionResponse";
import nativeFixture from "../test/connections.fixture.json";

vi.mock("./atlas", () => ({ atlas: { get: vi.fn(), post: vi.fn(), put: vi.fn() } }));
const schema = { provider_id: "proxmox", provider_name: "Proxmox" };
const field = { key: "host", label: "Host", kind: "host" };
const request = { confirmed: true, values: { host: "fixture.invalid" } };

describe("connection response contracts", () => {
    beforeEach(() => vi.clearAllMocks());
    it("accepts native public fixtures for every field kind and all three responses", async () => {
        vi.mocked(atlas.get).mockResolvedValue({ data: nativeFixture.schema });
        vi.mocked(atlas.post).mockResolvedValue({ data: nativeFixture.test });
        vi.mocked(atlas.put).mockResolvedValue({ data: nativeFixture.save });
        await expect(getProviderConnection("proxmox")).resolves.toEqual(nativeFixture.schema);
        await expect(testProviderConnection("proxmox", request)).resolves.toEqual(nativeFixture.test);
        await expect(updateProviderConnection("proxmox", request)).resolves.toEqual(nativeFixture.save);
        expect(atlas.get).toHaveBeenCalledWith("/providers/proxmox/connection");
        expect(atlas.post).toHaveBeenCalledWith("/providers/proxmox/connection/test", request);
        expect(atlas.put).toHaveBeenCalledWith("/providers/proxmox/connection", request);
    });
    it("honors schema/field defaults and keeps secret defaults hidden", () => {
        expect(parseConnectionSchema(schema, "proxmox")).toEqual({ ...schema, fields: [], editable: true, testable: true, updated_at: null, metadata: {} });
        const parsed = parseConnectionSchema({ ...schema, fields: [field, { key: "token", label: "Token", kind: "secret" }] }, "proxmox");
        expect(parsed.fields[0]).toEqual({ ...field, required: false, editable: true, secret: false, current_value: null,
            secret_state: null, source: null, help_text: "", options: [], validation: {} });
        expect(parsed.fields[1]).toMatchObject({ secret: true, current_value: null, secret_state: "missing" });
    });
    it("accepts native optional result defaults and naive ISO datetimes", () => {
        expect(parseConnectionTest({ provider_id: "proxmox", status: "degraded", tested_at: "2026-01-01T00:00:00" }, "proxmox"))
            .toEqual({ provider_id: "proxmox", status: "degraded", tested_at: "2026-01-01T00:00:00", message: "", latency_ms: null, diagnostics: {} });
        expect(parseConnectionSave({ provider_id: "proxmox", connection_schema: schema, updated_at: "2026-01-01T00:00:00Z" }, "proxmox").message).toBe("");
    });
    it("drops additive fields from the displayed projection", () => {
        expect(parseConnectionSchema({ ...schema, extra: "private" }, "proxmox")).not.toHaveProperty("extra");
    });
    it.each([null, [], {}, { ...schema, provider_id: "other" }, { ...schema, provider_name: {} },
        { ...schema, fields: null }, { ...schema, editable: "true" }, { ...schema, testable: 0 },
        { ...schema, metadata: [] }, { ...schema, updated_at: "2026-02-30T00:00:00Z" },
    ].map(value => ({ value })))("rejects malformed or mismatched schemas", ({ value }) => {
        expect(() => parseConnectionSchema(value, "proxmox")).toThrow(ConnectionResponseError);
    });
    it.each([
        ["key", ""], ["label", {}], ["kind", "unknown"], ["required", "true"], ["editable", 0],
        ["secret", "false"], ["current_value", {}], ["source", 0], ["help_text", {}],
        ["validation", null], ["options", {}], ["secret_state", "configured"],
    ])("rejects malformed field %s", (key, value) => {
        expect(() => parseConnectionSchema({ ...schema, fields: [{ ...field, [key]: value }] }, "proxmox")).toThrow(ConnectionResponseError);
    });
    it.each([
        { fields: [field, field] }, { fields: [{ ...field, kind: "select", options: [] }] },
        { fields: [{ ...field, kind: "select", options: [{ value: "x", label: "X" }, { value: "x", label: "X" }] }] },
        { fields: [{ ...field, kind: "select", options: [{ value: "x", label: {} }] }] },
        { fields: [{ ...field, kind: "secret", current_value: "private-secret-canary" }] },
    ])("rejects duplicate, malformed-option or exposed-secret fields", ({ fields }) => {
        expect(() => parseConnectionSchema({ ...schema, fields }, "proxmox")).toThrow(ConnectionResponseError);
    });
    it.each([
        { ...nativeFixture.test, provider_id: "other" }, { ...nativeFixture.test, status: "healthy" },
        { ...nativeFixture.test, message: {} }, { ...nativeFixture.test, latency_ms: -1 },
        { ...nativeFixture.test, diagnostics: null }, { ...nativeFixture.test, tested_at: "invalid" },
    ])("rejects malformed test outcomes", value => {
        expect(() => parseConnectionTest(value, "proxmox")).toThrow(ConnectionResponseError);
    });
    it.each([
        { ...nativeFixture.save, provider_id: "other" }, { ...nativeFixture.save, connection_schema: { ...schema, provider_id: "other" } },
        { ...nativeFixture.save, connection_schema: null }, { ...nativeFixture.save, message: {} },
        { ...nativeFixture.save, updated_at: "invalid" },
    ])("rejects malformed or mismatched save outcomes", value => {
        expect(() => parseConnectionSave(value, "proxmox")).toThrow(ConnectionResponseError);
    });
    it.each(["get", "post", "put"] as const)("validates the %s SDK boundary without replaying requests", async method => {
        vi.mocked(atlas[method]).mockResolvedValue({ data: { provider_id: "other", message: "private-error-canary" } });
        const call = () => method === "get" ? getProviderConnection("proxmox") : method === "post" ? testProviderConnection("proxmox", request) : updateProviderConnection("proxmox", request);
        await expect(call()).rejects.toBeInstanceOf(ConnectionResponseError);
        expect(atlas[method]).toHaveBeenCalledTimes(1);
    });
});
