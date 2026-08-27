import { beforeEach, describe, expect, it, vi } from "vitest";

import { atlas } from "./atlas";
import {
    deleteInstallationCandidateRecord,
    getInstallationCandidateRecord,
    listInstallationCandidateRecords,
    parseInstallationCandidateRecordEnvelope,
    preserveInstallationCandidateRecord,
} from "./installationCandidateLifecycle";

vi.mock("./atlas", () => ({ atlas: { get: vi.fn(), post: vi.fn(), delete: vi.fn() } }));

const candidate = {
    schema: "installation-candidate-record-v1", item_id: "example", catalog_entry_id: "catalog-example",
    plan_fingerprint: "plan", selection_id: "00000000-0000-4000-8000-000000000001",
    selected_destination_fingerprint: "selected", current_destination_fingerprint: "current",
    capability_assessment_fingerprint: "assessment", provider_fact_set_fingerprint: "facts",
    evaluated_at: "2026-08-27T12:00:00Z", valid_until: "2026-08-27T12:05:00Z",
    approved: false, executable: false, deployable: false, dispatchable: false,
    agent_execution_supported: false, record_fingerprint: "candidate-fingerprint",
};
const envelope = {
    schema: "installation-candidate-record-envelope-v1", candidate_record_id: "00000000-0000-4000-8000-000000000002",
    created_at: "2026-08-27T12:00:01Z", admission_fingerprint: "admission-fingerprint", candidate_record: candidate,
    envelope_fingerprint: "envelope-fingerprint", lifecycle_state: "active",
};

describe("installation candidate lifecycle API", () => {
    beforeEach(() => vi.resetAllMocks());

    it("parses the closed envelope and rejects leaked fields, unknown states, and authority", () => {
        expect(parseInstallationCandidateRecordEnvelope(envelope)).toMatchObject({ lifecycle_state: "active" });
        expect(() => parseInstallationCandidateRecordEnvelope({ ...envelope, raw_provider_payload: "secret" })).toThrow(/invalid/i);
        expect(() => parseInstallationCandidateRecordEnvelope({ ...envelope, lifecycle_state: "deleted" })).toThrow(/invalid/i);
        expect(() => parseInstallationCandidateRecordEnvelope({ ...envelope, candidate_record: { ...candidate, approved: true } })).toThrow(/non-executable/i);
    });

    it("uses only guarded list/get/preserve/delete lifecycle calls", async () => {
        vi.mocked(atlas.get).mockResolvedValueOnce({ data: { records: [envelope] } }).mockResolvedValueOnce({ data: envelope });
        vi.mocked(atlas.post).mockResolvedValueOnce({ data: envelope });
        vi.mocked(atlas.delete).mockResolvedValueOnce({});
        await expect(listInstallationCandidateRecords()).resolves.toHaveLength(1);
        await getInstallationCandidateRecord("record/id");
        await preserveInstallationCandidateRecord({ item_id: "example", selection_id: "selection" }, "csrf", "key");
        await deleteInstallationCandidateRecord("record/id", "csrf");
        expect(atlas.get).toHaveBeenNthCalledWith(1, "/installation/candidate-records", { withCredentials: true });
        expect(atlas.get).toHaveBeenNthCalledWith(2, "/installation/candidate-records/record%2Fid", { withCredentials: true });
        expect(atlas.post).toHaveBeenCalledWith("/installation/candidate-records", { item_id: "example", selection_id: "selection" }, {
            withCredentials: true, headers: { "X-Atlas-CSRF-Token": "csrf", "Idempotency-Key": "key" },
        });
        expect(atlas.delete).toHaveBeenCalledWith("/installation/candidate-records/record%2Fid", {
            withCredentials: true, headers: { "X-Atlas-CSRF-Token": "csrf" },
        });
    });
});
