import type { ProviderConnectionField, ProviderConnectionSchema, TestProviderConnectionResult, UpdateProviderConnectionResult } from "../types/connections";
import { evidenceTimestamp } from "../utils/healthPresentation";

export class ConnectionResponseError extends Error {
    constructor() { super("The connection response could not confirm the requested provider data."); }
}
const kinds = new Set(["string", "host", "url", "port", "boolean", "select", "secret", "path"]);
function object(value: unknown): Record<string, unknown> {
    if (value === null || typeof value !== "object" || Array.isArray(value)) throw new ConnectionResponseError();
    return value as Record<string, unknown>;
}
function text(value: unknown, nonempty = false): string {
    if (typeof value !== "string" || (nonempty && !value.length)) throw new ConnectionResponseError();
    return value;
}
function boolean(value: unknown): boolean {
    if (typeof value !== "boolean") throw new ConnectionResponseError();
    return value;
}
function nullableText(value: unknown): string | null { return value === null ? null : text(value); }
function timestamp(value: unknown): string {
    const result = text(value);
    // Core's datetime DTO accepts both zoned and naive ISO datetimes.
    const checked = /(?:Z|[+-]\d{2}:\d{2})$/.test(result) ? result : `${result}Z`;
    if (evidenceTimestamp(checked) === null) throw new ConnectionResponseError();
    return result;
}
function unique(values: string[]): void {
    if (new Set(values).size !== values.length) throw new ConnectionResponseError();
}
function field(value: unknown): ProviderConnectionField {
    const data: Record<string, unknown> = { required: false, editable: true, secret: false, current_value: null,
        secret_state: null, source: null, help_text: "", options: [], validation: {}, ...object(value) };
    if (typeof data.kind !== "string" || !kinds.has(data.kind) || !Array.isArray(data.options)) throw new ConnectionResponseError();
    const options = data.options.map(value => {
        const option: Record<string, unknown> = { description: "", ...object(value) };
        return { value: text(option.value, true), label: text(option.label, true), description: text(option.description) };
    });
    unique(options.map(option => option.value));
    const secret = boolean(data.secret) || data.kind === "secret";
    const secretState = secret && data.secret_state === null ? "missing" : data.secret_state;
    if ((secret && (data.current_value !== null || (secretState !== "missing" && secretState !== "configured")))
        || (!secret && secretState !== null) || (data.kind === "select" && options.length === 0)) throw new ConnectionResponseError();
    const current = data.current_value;
    if (current !== null && typeof current !== "string" && typeof current !== "boolean" && !Number.isSafeInteger(current)) throw new ConnectionResponseError();
    return { key: text(data.key, true), label: text(data.label, true), kind: data.kind as ProviderConnectionField["kind"],
        required: boolean(data.required), editable: boolean(data.editable), secret, current_value: current as ProviderConnectionField["current_value"],
        secret_state: secretState as ProviderConnectionField["secret_state"], source: nullableText(data.source),
        help_text: text(data.help_text), options, validation: object(data.validation) };
}

export function parseConnectionSchema(value: unknown, providerId: string): ProviderConnectionSchema {
    const data: Record<string, unknown> = { fields: [], editable: true, testable: true, updated_at: null, metadata: {}, ...object(value) };
    if (data.provider_id !== providerId || !Array.isArray(data.fields)) throw new ConnectionResponseError();
    const fields = data.fields.map(field);
    unique(fields.map(field => field.key));
    return { provider_id: providerId, provider_name: text(data.provider_name, true), fields,
        editable: boolean(data.editable), testable: boolean(data.testable),
        updated_at: data.updated_at === null ? null : timestamp(data.updated_at), metadata: object(data.metadata) };
}
export function parseConnectionTest(value: unknown, providerId: string): TestProviderConnectionResult {
    const data: Record<string, unknown> = { message: "", latency_ms: null, diagnostics: {}, ...object(value) };
    if (data.provider_id !== providerId || (data.status !== "success" && data.status !== "failure" && data.status !== "degraded")
        || (data.latency_ms !== null && (typeof data.latency_ms !== "number" || !Number.isFinite(data.latency_ms) || data.latency_ms < 0))) throw new ConnectionResponseError();
    return { provider_id: providerId, status: data.status, message: text(data.message), tested_at: timestamp(data.tested_at),
        latency_ms: data.latency_ms as number | null, diagnostics: object(data.diagnostics) };
}
export function parseConnectionSave(value: unknown, providerId: string): UpdateProviderConnectionResult {
    const data: Record<string, unknown> = { message: "", ...object(value) };
    if (data.provider_id !== providerId) throw new ConnectionResponseError();
    return { provider_id: providerId, connection_schema: parseConnectionSchema(data.connection_schema, providerId),
        updated_at: timestamp(data.updated_at), message: text(data.message) };
}
