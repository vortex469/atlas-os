import { beforeEach, describe, expect, it, vi } from "vitest";

import { atlas } from "./atlas";
import { getInstallationCapabilityAssessment, parseInstallationCapabilityAssessment } from "./installationCapability";

vi.mock("./atlas", () => ({ atlas: { get: vi.fn() } }));

const response = {
    schema_version: "installation-capability-assessment-v1",
    plan: {}, selection: {}, current_destination: {},
    provider_facts: {
        schema_version: "provider-installation-capability-facts-v1", provider: "proxmox", resource_type: "qemu",
        placement_kind: "existing-guest", resource_id: "101", destination_fingerprint: "b".repeat(64),
        observed_at: "2026-08-27T12:00:00Z", fresh_until: "2026-08-27T12:05:00Z", facts: [],
    },
    comparisons: [], reason_codes: [], assessment_status: "blocked",
    evaluated_at: "2026-08-27T12:00:00Z", assessment_fingerprint: "a".repeat(64),
    candidate_eligibility_evaluated: false, candidate_creation_allowed: false,
    agent_execution_supported: false, provider_mutation_allowed: false,
};

describe("installation capability API", () => {
    beforeEach(() => vi.resetAllMocks());

    it("uses only the authenticated GET projection and parses the closed response", async () => {
        vi.mocked(atlas.get).mockResolvedValueOnce({ data: response });
        await expect(getInstallationCapabilityAssessment("home assistant", "selection/id")).resolves.toMatchObject({ assessment_status: "blocked" });
        expect(atlas.get).toHaveBeenCalledWith(
            "/installation/capability-assessments/home%20assistant/selection%2Fid",
            { withCredentials: true },
        );
    });

    it("rejects malformed or authority-bearing responses", () => {
        expect(() => parseInstallationCapabilityAssessment({ ...response, schema_version: "raw-provider-payload" })).toThrow();
        expect(() => parseInstallationCapabilityAssessment({ ...response, provider_mutation_allowed: true })).toThrow(/non-authorizing/);
        expect(() => parseInstallationCapabilityAssessment({ ...response, comparisons: {} })).toThrow();
        expect(() => parseInstallationCapabilityAssessment({ ...response, raw_provider_payload: { address: "10.0.0.1" } })).toThrow(/unexpected fields/);
    });
});
