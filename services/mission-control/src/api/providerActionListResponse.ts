import type { ProviderAction } from "../types/providerAction";

export class ProviderActionListResponseError extends Error {
    constructor() {
        super("Provider action list could not be read.");
        this.name = "ProviderActionListResponseError";
    }
}
function object(value: unknown): Record<string, unknown> {
    if (value === null || typeof value !== "object" || Array.isArray(value)) throw new ProviderActionListResponseError();
    return value as Record<string, unknown>;
}
function string(value: unknown): string {
    if (typeof value !== "string") throw new ProviderActionListResponseError();
    return value;
}
function boolean(value: unknown): boolean {
    if (typeof value !== "boolean") throw new ProviderActionListResponseError();
    return value;
}
function parameters(value: unknown): Record<string, unknown> {
    return Object.fromEntries(Object.entries(object(value)).map(([name, value]) => {
        const definition = object(value);
        // Core leaves parameter metadata open. Check only the fields consumed by this form.
        for (const key of ["type", "description", "example"]) {
            if (Object.hasOwn(definition, key)) string(definition[key]);
        }
        if (Object.hasOwn(definition, "required")) boolean(definition.required);
        return [name, { ...definition }];
    }));
}

export function parseProviderActionList(value: unknown): ProviderAction[] {
    if (!Array.isArray(value)) throw new ProviderActionListResponseError();
    const ids = new Set<string>();
    return value.map(entry => {
        const row = object(entry);
        const id = string(row.id), label = string(row.label);
        if (!/^[a-z0-9]+(?:-[a-z0-9]+)*$/.test(id) || label.length === 0 || ids.has(id)) throw new ProviderActionListResponseError();
        ids.add(id);
        return { id, label, description: string(row.description), icon: string(row.icon),
            enabled: boolean(row.enabled), destructive: boolean(row.destructive), requires_confirmation: boolean(row.requires_confirmation),
            parameters: parameters(row.parameters),
        };
    });
}
