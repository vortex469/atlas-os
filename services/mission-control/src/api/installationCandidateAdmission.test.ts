import { beforeEach, describe, expect, it, vi } from "vitest";

import { atlas } from "./atlas";
import { getInstallationCandidateAdmission, parseInstallationCandidateAdmission } from "./installationCandidateAdmission";

vi.mock("./atlas", () => ({ atlas: { get: vi.fn() } }));

const response = {
    schema: "installation-candidate-admission-v1",
    plan_fingerprint: "plan", selection_fingerprint: "selection",
    selected_destination_fingerprint: "destination", current_destination_fingerprint: "destination",
    capability_assessment_fingerprint: "assessment", provider_fact_set_fingerprint: "facts",
    evaluated_at: "2026-08-27T12:00:00Z", status: "not_admitted",
    reason_codes: ["installation_plan_not_review_ready"], candidate_record: null,
    approved: false, executable: false, deployable: false, dispatchable: false,
    agent_execution_supported: false, candidate_creation_allowed: false,
    admission_fingerprint: "admission",
};

describe("installation candidate admission API", () => {
    beforeEach(() => vi.resetAllMocks());

    it("uses only the authenticated GET projection and parses its closed response", async () => {
        vi.mocked(atlas.get).mockResolvedValueOnce({ data: response });
        await expect(getInstallationCandidateAdmission("home assistant", "selection/id")).resolves.toMatchObject({ status: "not_admitted" });
        expect(atlas.get).toHaveBeenCalledWith(
            "/installation/candidate-admissions/home%20assistant/selection%2Fid",
            { withCredentials: true },
        );
    });

    it("rejects extra data, true authority, inconsistent records, and unordered reasons", () => {
        expect(() => parseInstallationCandidateAdmission({ ...response, raw_provider_payload: { address: "10.0.0.1" } })).toThrow(/invalid/i);
        expect(() => parseInstallationCandidateAdmission({ ...response, executable: true })).toThrow(/non-authorizing/i);
        expect(() => parseInstallationCandidateAdmission({ ...response, status: "admitted_but_non_executable", reason_codes: [] })).toThrow(/inconsistent/i);
        expect(() => parseInstallationCandidateAdmission({ ...response, reason_codes: ["destination_selection_expired", "installation_plan_not_review_ready"] })).toThrow(/ordered/i);
    });
});
