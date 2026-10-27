import type { AtlasPolicies, PolicySeverity } from "../types/policies";

export class PoliciesResponseError extends Error {
    constructor() {
        super("Policy settings response could not be read.");
        this.name = "PoliciesResponseError";
    }
}

type Row = Record<string, unknown>;
function object(value: unknown): Row {
    if (value === null || typeof value !== "object" || Array.isArray(value)) throw new PoliciesResponseError();
    return value as Row;
}
function choice<T extends string>(value: unknown, options: readonly T[]): T {
    if (typeof value !== "string" || !options.includes(value as T)) throw new PoliciesResponseError();
    return value as T;
}
function severity(value: unknown): PolicySeverity {
    return choice(value, ["info", "warning", "critical"]);
}
function number(value: unknown, minimum: number, integer = false): number {
    if (typeof value !== "number" || !Number.isFinite(value) || value < minimum || (integer && !Number.isSafeInteger(value))) throw new PoliciesResponseError();
    return value;
}
function nullableCount(value: unknown): number | null {
    return value === null ? null : number(value, 1, true);
}
function strings(value: unknown, uniqueNonempty = false): string[] {
    if (!Array.isArray(value) || value.some(item => typeof item !== "string" || (uniqueNonempty && item.length === 0))) throw new PoliciesResponseError();
    if (uniqueNonempty && new Set(value).size !== value.length) throw new PoliciesResponseError();
    return [...value] as string[];
}
function record<T>(value: unknown, parse: (row: Row) => T): Record<string, T> {
    return Object.fromEntries(Object.entries(object(value)).map(([key, entry]) => [key, parse(object(entry))]));
}

// /policies serializes the complete native Policies model, including defaults.
// Validate that public snapshot before exposing any section to the screen.
export function parsePolicies(value: unknown): AtlasPolicies {
    const root = object(value);
    const proxmox = object(root.proxmox);
    const docker = object(root.docker);
    const homeassistant = object(root.homeassistant);
    const opnsense = object(root.opnsense);
    const frigate = object(root.frigate);
    const obsidian = object(root.obsidian);
    const qdrant = object(root.qdrant);
    const n8n = object(root.n8n);
    const intelligence = object(root.intelligence);
    return {
        proxmox: { guests: record(proxmox.guests, row => ({ expected: choice(row.expected, ["running", "stopped", "ignored"]) })) },
        docker: { containers: record(docker.containers, row => ({ expected: choice(row.expected, ["running", "stopped"]) })) },
        homeassistant: { ignored_entities: strings(homeassistant.ignored_entities) },
        opnsense: {
            pending_update_warning_threshold: nullableCount(opnsense.pending_update_warning_threshold),
            reboot_required_severity: severity(opnsense.reboot_required_severity),
        },
        frigate: {
            cameras: record(frigate.cameras, row => ({
                expected: choice(row.expected, ["active", "inactive"]),
                minimum_camera_fps: number(row.minimum_camera_fps, 0),
                minimum_process_fps: number(row.minimum_process_fps, 0),
            })),
            stalled_camera_severity: severity(frigate.stalled_camera_severity),
        },
        obsidian: {
            minimum_note_count: number(obsidian.minimum_note_count, 0, true),
            stale_after_days: nullableCount(obsidian.stale_after_days),
            insufficient_notes_severity: severity(obsidian.insufficient_notes_severity),
            stale_severity: severity(obsidian.stale_severity),
            scan_truncated_severity: severity(obsidian.scan_truncated_severity),
        },
        qdrant: {
            expected_collections: strings(qdrant.expected_collections, true),
            missing_collection_severity: severity(qdrant.missing_collection_severity),
            empty_instance_severity: severity(qdrant.empty_instance_severity),
        },
        n8n: {
            expected_active_workflows: strings(n8n.expected_active_workflows, true),
            inactive_workflow_severity: severity(n8n.inactive_workflow_severity),
            scan_truncated_severity: severity(n8n.scan_truncated_severity),
            empty_instance_severity: severity(n8n.empty_instance_severity),
        },
        intelligence: {
            providers: record(intelligence.providers, row => {
                const maximum = number(row.maximum_collection_duration_ms, 0);
                if (maximum === 0) throw new PoliciesResponseError();
                return { maximum_collection_duration_ms: maximum, severity: severity(row.severity) };
            }),
        },
    };
}
