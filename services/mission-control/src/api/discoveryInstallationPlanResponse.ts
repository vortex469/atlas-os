import type { InstallationPlan } from "../types/installationPlan";

export class DiscoveryInstallationPlanResponseError extends Error {
    constructor() { super("The installation plan could not be read."); }
}
function fail(): never { throw new DiscoveryInstallationPlanResponseError(); }
function record(value: unknown): value is Record<string, unknown> { return value !== null && typeof value === "object" && !Array.isArray(value); }
function text(value: unknown): value is string { return typeof value === "string" && value.trim().length > 0; }
function fields(value: unknown, required: string[], nullable: string[] = []): value is Record<string, unknown> {
    return record(value) && required.every(key => text(value[key]))
        && nullable.every(key => value[key] === null || text(value[key]));
}
function oneOf(value: unknown, values: string[]): boolean { return typeof value === "string" && values.includes(value); }
function rows(value: unknown, max: number, required: string[], nullable: string[] = [], min = 0): Record<string, unknown>[] {
    if (!Array.isArray(value) || value.length < min || value.length > max || !value.every(row => fields(row, required, nullable))) fail();
    return value;
}

// Check fields used by plan review and its dependent views. Do not repair,
// normalize, reorder, rehash or confer approval on a supplied plan. Core owns
// full contract validation and readiness; accepted content passes unchanged.
export function parseDiscoveryInstallationPlan(value: unknown, itemId: string): InstallationPlan {
    if (!record(value) || value.schema_version !== "installation-plan-v1"
        || !fields(value.application, ["item_id", "catalog_entry_id", "display_name"], ["release_version"])
        || value.application.item_id !== itemId || !record(value.fingerprint)
        || value.fingerprint.algorithm !== "sha256" || value.fingerprint.canonicalization !== "atlas-jcs-nfc-v1"
        || typeof value.fingerprint.value !== "string" || value.fingerprint.value.length !== 64
        || !/^[a-f0-9]{64}$/.test(value.fingerprint.value)
        || !oneOf(value.status, ["conflicted", "missing_deployment_artifact", "incompatible", "stale_evidence", "insufficient_information", "plan_ready_for_review"])) fail();
    if (!fields(value.deployment_artifact, ["state", "kind"], ["repository_path", "service", "content_digest"])
        || value.deployment_artifact.kind !== "docker-compose"
        || !oneOf(value.deployment_artifact.state, ["present", "missing", "invalid", "unsafe", "unknown"])
        || !fields(value.image, ["state"], ["reference", "digest", "release_version"])
        || !oneOf(value.image.state, ["grounded", "missing", "mutable", "untrusted", "conflicted", "mismatched", "unknown"])) fail();
    if (value.deployment_artifact.state === "present"
        && [value.deployment_artifact.repository_path, value.deployment_artifact.service, value.deployment_artifact.content_digest].some(value => value === null)) fail();
    if (value.image.state === "grounded" && [value.image.reference, value.image.digest, value.image.release_version].some(value => value === null)) fail();
    const evidence = rows(value.accepted_evidence, 32, ["evidence_id", "source_class", "source_id", "subject", "claim", "immutable_identity", "attested_at", "trust"]);
    if (evidence.some(row => row.observed_at !== null || row.trust !== "accepted"
        || !oneOf(row.source_class, ["curated", "registry_attested", "upstream_signed"])
        || !Number.isSafeInteger(row.freshness_window_seconds) || Number(row.freshness_window_seconds) < 60
        || Number(row.freshness_window_seconds) > 31_536_000)) fail();
    rows(value.provenance, 256, ["claim", "source_class", "source_id", "immutable_identity"], ["observed_at", "attested_at"], 1);
    const compatibility = rows(value.compatibility, 1, ["environment", "result", "reason_code"], [], 1);
    if (compatibility.some(row => row.environment !== "item-scoped"
        || !oneOf(row.result, ["compatible", "compatible_with_warnings", "incompatible", "unknown"]))) fail();
    rows(value.prerequisites, 64, ["prerequisite_id", "kind", "state", "description"]);
    const relationships = rows(value.relationships, 64, ["kind", "item_id"], ["minimum_version", "maximum_version"]);
    if (relationships.some(row => typeof row.required !== "boolean")) fail();
    rows(value.assumptions, 32, ["assumption_id", "kind", "statement"]);
    const blockers = rows(value.blockers, 64, ["code", "subject"]);
    rows(value.risks, 32, ["code", "severity", "subject"]);
    rows(value.missing_facts, 64, ["code", "subject"]);
    rows(value.required_operator_confirmations, 32, ["code", "subject", "prompt"]);
    // Mirror the public status/blocker invariant without deriving a replacement.
    const codes = new Set(blockers.map(row => row.code));
    const expectedStatus = codes.has("provenance_conflict") || codes.has("image_conflict") ? "conflicted"
        : codes.has("missing_deployment_artifact") ? "missing_deployment_artifact"
        : codes.has("incompatible_application_environment") ? "incompatible"
        : codes.has("stale_evidence") ? "stale_evidence"
        : blockers.length ? "insufficient_information" : "plan_ready_for_review";
    if (value.status !== expectedStatus) fail();
    return value as unknown as InstallationPlan;
}
