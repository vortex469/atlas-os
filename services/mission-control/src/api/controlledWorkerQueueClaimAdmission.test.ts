import { beforeEach, describe, expect, it, vi } from "vitest";

import { atlas } from "./atlas";
import { getControlledWorkerQueueClaimAdmission, listControlledWorkerQueueClaimAdmissions, parseControlledWorkerQueueClaimAdmissionCollection, parseControlledWorkerQueueClaimAdmissionResult } from "./controlledWorkerQueueClaimAdmission";
import { controlledWorkerQueueClaimAdmissionCollectionFixture, controlledWorkerQueueClaimAdmissionResultFixture } from "../test/controlledWorkerQueueClaimAdmission";

vi.mock("./atlas", () => ({ atlas: { get: vi.fn() } }));

describe("controlled worker queue claim admission API", () => {
    beforeEach(() => vi.resetAllMocks());

    it("uses only guarded read endpoints", async () => {
        vi.mocked(atlas.get).mockResolvedValueOnce({ data: controlledWorkerQueueClaimAdmissionCollectionFixture }).mockResolvedValueOnce({ data: controlledWorkerQueueClaimAdmissionResultFixture });
        await listControlledWorkerQueueClaimAdmissions("candidate/id");
        await getControlledWorkerQueueClaimAdmission("candidate/id", "admission/id");
        expect(atlas.get).toHaveBeenNthCalledWith(1, "/installation/candidate-records/candidate%2Fid/controlled-worker-queue-claim-admissions", { withCredentials: true });
        expect(atlas.get).toHaveBeenNthCalledWith(2, "/installation/candidate-records/candidate%2Fid/controlled-worker-queue-claim-admissions/admission%2Fid", { withCredentials: true });
    });

    it("strictly parses success and rejects start, queue, authority, or sensitive drift", () => {
        expect(parseControlledWorkerQueueClaimAdmissionCollection(controlledWorkerQueueClaimAdmissionCollectionFixture).items).toHaveLength(1);
        expect(parseControlledWorkerQueueClaimAdmissionResult(controlledWorkerQueueClaimAdmissionResultFixture).record?.admission_state).toBe("readiness_gated");
        expect(() => parseControlledWorkerQueueClaimAdmissionResult({ ...controlledWorkerQueueClaimAdmissionResultFixture, record: { ...controlledWorkerQueueClaimAdmissionResultFixture.record!, queue_claimed: true } })).toThrow();
        expect(() => parseControlledWorkerQueueClaimAdmissionResult({ ...controlledWorkerQueueClaimAdmissionResultFixture, record: { ...controlledWorkerQueueClaimAdmissionResultFixture.record!, worker_start_admitted: true } })).toThrow();
        expect(() => parseControlledWorkerQueueClaimAdmissionResult({ ...controlledWorkerQueueClaimAdmissionResultFixture, record: { ...controlledWorkerQueueClaimAdmissionResultFixture.record!, store_endpoint: "http://internal" } })).toThrow();
        expect(() => parseControlledWorkerQueueClaimAdmissionResult({ ...controlledWorkerQueueClaimAdmissionResultFixture, status: { ...controlledWorkerQueueClaimAdmissionResultFixture.status!, candidate_record_id: "00000000-0000-4000-8000-000000000099" } })).toThrow();
        expect(() => parseControlledWorkerQueueClaimAdmissionCollection({ ...controlledWorkerQueueClaimAdmissionCollectionFixture, items: Array.from({ length: 101 }, () => controlledWorkerQueueClaimAdmissionCollectionFixture.items[0]), count: 101 })).toThrow();
        expect(() => parseControlledWorkerQueueClaimAdmissionCollection({ ...controlledWorkerQueueClaimAdmissionCollectionFixture, operator_id: "operator-b" })).toThrow();
    });
});
