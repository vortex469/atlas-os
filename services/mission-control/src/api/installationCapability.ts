import { atlas } from "./atlas";
import type { InstallationCapabilityAssessmentV1 } from "../types/installationCapability";

function isRecord(value: unknown): value is Record<string, unknown> {
    return typeof value === "object" && value !== null && !Array.isArray(value);
}

function hasOnlyKeys(value: Record<string, unknown>, keys: readonly string[]): boolean {
    return Object.keys(value).every((key) => keys.includes(key)) && keys.every((key) => key in value);
}

export function parseInstallationCapabilityAssessment(value: unknown): InstallationCapabilityAssessmentV1 {
    if (!isRecord(value) || value.schema_version !== "installation-capability-assessment-v1") {
        throw new Error("Invalid installation capability assessment response.");
    }
    if (!hasOnlyKeys(value, [
        "schema_version", "plan", "selection", "current_destination", "provider_facts", "comparisons",
        "assessment_status", "reason_codes", "evaluated_at", "candidate_eligibility_evaluated",
        "candidate_creation_allowed", "agent_execution_supported", "provider_mutation_allowed", "assessment_fingerprint",
    ])) throw new Error("Installation capability assessment contained unexpected fields.");
    const requiredObjects = ["plan", "selection", "current_destination", "provider_facts"];
    if (requiredObjects.some((key) => !isRecord(value[key])) || !Array.isArray(value.comparisons) || !Array.isArray(value.reason_codes)) {
        throw new Error("Invalid installation capability assessment response.");
    }
    const statuses = ["blocked", "insufficient_provider_facts", "requirements_satisfied_but_non_authorizing"];
    if (!statuses.includes(String(value.assessment_status)) || value.candidate_eligibility_evaluated !== false || value.candidate_creation_allowed !== false || value.agent_execution_supported !== false || value.provider_mutation_allowed !== false) {
        throw new Error("Invalid non-authorizing installation capability assessment response.");
    }
    const facts = value.provider_facts as Record<string, unknown>;
    if (facts.schema_version !== "provider-installation-capability-facts-v1" || !Array.isArray(facts.facts)) {
        throw new Error("Invalid installation capability provider facts response.");
    }
    if (!hasOnlyKeys(facts, ["schema_version", "provider", "resource_type", "placement_kind", "resource_id", "destination_fingerprint", "observed_at", "fresh_until", "facts"])) {
        throw new Error("Installation capability provider facts contained unexpected fields.");
    }
    return value as InstallationCapabilityAssessmentV1;
}

export async function getInstallationCapabilityAssessment(itemId: string, selectionId: string): Promise<InstallationCapabilityAssessmentV1> {
    const response = await atlas.get<unknown>(
        `/installation/capability-assessments/${encodeURIComponent(itemId)}/${encodeURIComponent(selectionId)}`,
        { withCredentials: true },
    );
    return parseInstallationCapabilityAssessment(response.data);
}
