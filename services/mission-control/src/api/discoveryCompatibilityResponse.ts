import type { DiscoveryCompatibilityAssessment } from "../types/discovery";

export class DiscoveryCompatibilityResponseError extends Error {
    constructor() { super("The compatibility result could not be read. Try again."); }
}
function record(value: unknown): value is Record<string, unknown> {
    return value !== null && typeof value === "object" && !Array.isArray(value);
}
function strings(value: unknown): value is string[] {
    return Array.isArray(value) && value.every(item => typeof item === "string");
}
function fields(value: Record<string, unknown>, keys: string[]): boolean {
    return keys.every(key => typeof value[key] === "string" && (value[key] as string).trim().length > 0);
}
function uniqueIds(values: Record<string, unknown>[]): boolean {
    return new Set(values.map(value => value.id)).size === values.length;
}

// Guard the read-only assessment's rendered fields. Future labels and additive
// metadata remain intact; this does not validate installation or execution.
export function parseDiscoveryCompatibility(value: unknown, itemId: string, targetId: string): DiscoveryCompatibilityAssessment {
    if (!record(value) || value.item_id !== itemId || value.target_id !== targetId
        || !fields(value, ["target_type", "status", "checked_at"])) throw new DiscoveryCompatibilityResponseError();
    const findings = value.findings === undefined ? [] : value.findings;
    const evidence = value.evidence === undefined ? [] : value.evidence;
    const unknownFacts = value.unknown_facts === undefined ? [] : value.unknown_facts;
    if (!Array.isArray(findings) || !Array.isArray(evidence) || !strings(unknownFacts)
        || !findings.every(finding => record(finding)
            && fields(finding, ["id", "check_type", "severity", "status"])
            && typeof finding.subject === "string" && typeof finding.message === "string"
            && strings(finding.evidence_ids))
        || !evidence.every(item => record(item) && fields(item, ["id", "check_type", "status"])
            && ["subject", "message", "source"].every(key => typeof item[key] === "string"))
        || !uniqueIds(findings) || !uniqueIds(evidence)) throw new DiscoveryCompatibilityResponseError();
    return { ...value, findings, evidence, unknown_facts: unknownFacts } as DiscoveryCompatibilityAssessment;
}
