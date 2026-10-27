import type { DiscoveryImageGroundingProjection } from "../types/discovery";
import { evidenceTimestamp } from "../utils/healthPresentation";

const SCHEMA = "discovery-image-grounding-projection-v1";
const statuses = new Set(["grounded", "no_deployment_binding", "no_strict_release_version", "no_repository_observation", "observation_mismatch", "mutable_observation", "no_image_release_evidence", "evidence_not_trusted", "evidence_version_mismatch", "repository_identity_mismatch", "digest_mismatch", "conflicted"]);
export class DiscoveryImageGroundingResponseError extends Error {
    constructor() { super("The image evidence could not be read. Reload the page to try again."); }
}
function fail(): never { throw new DiscoveryImageGroundingResponseError(); }
function record(value: unknown): value is Record<string, unknown> { return value !== null && typeof value === "object" && !Array.isArray(value); }
function text(value: unknown, max: number): value is string { return typeof value === "string" && value === value.trim() && value.length > 0 && value.length <= max; }
function version(value: unknown): value is string {
    return text(value, 64) && /^(0|[1-9][0-9]{0,9})\.(0|[1-9][0-9]{0,9})\.(0|[1-9][0-9]{0,9})$/.test(value);
}
function image(value: unknown): boolean {
    return record(value) && text(value.image_reference, 512) && value.image_reference.length >= 3
        && /^([a-z0-9._-]+(?::[0-9]+)?\/)?[a-z0-9._-]+(?:\/[a-z0-9._-]+)*(?::[a-z0-9._-]+)?$/.test(value.image_reference)
        && text(value.image_digest, 71) && value.image_digest.length === 71 && /^sha256:[0-9a-f]{64}$/.test(value.image_digest);
}
function binding(value: unknown): Record<string, unknown> | null {
    if (value === null) return null;
    if (!record(value)) fail();
    const result = { mutable_property: "image", deployment_method: "docker-compose", ...value };
    if (result.mutable_property !== "image" || result.deployment_method !== "docker-compose"
        || !text(value.compose_service, 255) || !/^[a-z0-9][a-z0-9_.-]*$/.test(value.compose_service)
        || !text(value.compose_file, 512) || /[\\]/.test(value.compose_file)
        || value.compose_file.startsWith("/") || value.compose_file.startsWith("~") || /^[A-Za-z]:\//.test(value.compose_file)) fail();
    const segments = value.compose_file.split("/");
    if (segments.length > 32 || segments.some(segment => segment === "" || segment === "." || segment === "..")
        || !/\.ya?ml$/.test(segments[segments.length - 1])) fail();
    return result;
}

// Protect the advisory display. Never derive a positive grounding status or
// grant execution authority; Core remains the grounding decision owner.
export function parseDiscoveryImageGrounding(value: unknown, itemId: string): DiscoveryImageGroundingProjection {
    if (!record(value) || value.catalog_item_id !== itemId || typeof value.status !== "string" || !statuses.has(value.status)) fail();
    const data = { schema_version: SCHEMA, release_version: null, deployment_binding: null, observed_image: null, accepted_evidence: [], ...value } as Record<string, unknown>;
    if (data.schema_version !== SCHEMA || (data.release_version !== null && !version(data.release_version))) fail();
    data.deployment_binding = binding(data.deployment_binding);
    if (data.observed_image !== null && !image(data.observed_image)) fail();
    const rows = data.accepted_evidence;
    if (!Array.isArray(rows) || rows.length > 100) fail();
    for (const row of rows) {
        if (!record(row) || !image(row) || !version(row.release_version)
            || typeof row.source_class !== "string" || !["curated", "registry_attested", "upstream_signed"].includes(row.source_class)
            || !text(row.source_id, 256) || evidenceTimestamp(row.attested_at) === null
            || typeof row.attested_at !== "string" || !/(?:Z|[+-]00:00)$/.test(row.attested_at)) fail();
    }
    if (value.status === "grounded") {
        if (!data.deployment_binding || !record(data.observed_image) || !version(data.release_version)) fail();
        const relevant = rows.filter(row => row.release_version === data.release_version);
        if (relevant.length === 0 || relevant.some(row => row.image_reference !== (data.observed_image as Record<string, unknown>).image_reference
            || row.image_digest !== (data.observed_image as Record<string, unknown>).image_digest)) fail();
    }
    return data as unknown as DiscoveryImageGroundingProjection;
}
