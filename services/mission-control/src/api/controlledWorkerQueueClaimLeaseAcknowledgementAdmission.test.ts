import { beforeEach, describe, expect, it, vi } from "vitest";

import { atlas } from "./atlas";
import { getControlledWorkerQueueClaimLeaseAcknowledgementAdmission, listControlledWorkerQueueClaimLeaseAcknowledgementAdmissions, parseControlledWorkerQueueClaimLeaseAcknowledgementAdmissionCollection, parseControlledWorkerQueueClaimLeaseAcknowledgementAdmissionResult } from "./controlledWorkerQueueClaimLeaseAcknowledgementAdmission";
import { controlledWorkerQueueClaimLeaseAcknowledgementAdmissionCollectionFixture, controlledWorkerQueueClaimLeaseAcknowledgementAdmissionResultFixture } from "../test/controlledWorkerQueueClaimLeaseAcknowledgementAdmission";

vi.mock("./atlas", () => ({ atlas: { get: vi.fn() } }));

describe("controlled worker queue claim lease acknowledgement admission API", () => {
    beforeEach(() => vi.resetAllMocks());

    it("uses only guarded read endpoints", async () => {
        vi.mocked(atlas.get).mockResolvedValueOnce({ data: controlledWorkerQueueClaimLeaseAcknowledgementAdmissionCollectionFixture }).mockResolvedValueOnce({ data: controlledWorkerQueueClaimLeaseAcknowledgementAdmissionResultFixture });
        await listControlledWorkerQueueClaimLeaseAcknowledgementAdmissions("candidate/id");
        await getControlledWorkerQueueClaimLeaseAcknowledgementAdmission("candidate/id", "admission/id");
        expect(atlas.get).toHaveBeenNthCalledWith(1, "/installation/candidate-records/candidate%2Fid/controlled-worker-queue-claim-lease-acknowledgement-admissions", { withCredentials: true });
        expect(atlas.get).toHaveBeenNthCalledWith(2, "/installation/candidate-records/candidate%2Fid/controlled-worker-queue-claim-lease-acknowledgement-admissions/admission%2Fid", { withCredentials: true });
    });

    it("strictly parses success and rejects authority, sensitive material, and ownership drift", () => {
        expect(parseControlledWorkerQueueClaimLeaseAcknowledgementAdmissionCollection(controlledWorkerQueueClaimLeaseAcknowledgementAdmissionCollectionFixture).items).toHaveLength(1);
        expect(parseControlledWorkerQueueClaimLeaseAcknowledgementAdmissionResult(controlledWorkerQueueClaimLeaseAcknowledgementAdmissionResultFixture).record?.admission_state).toBe("recorded");
        expect(() => parseControlledWorkerQueueClaimLeaseAcknowledgementAdmissionResult({ ...controlledWorkerQueueClaimLeaseAcknowledgementAdmissionResultFixture, record: { ...controlledWorkerQueueClaimLeaseAcknowledgementAdmissionResultFixture.record!, queue_claimed: true } })).toThrow();
        expect(() => parseControlledWorkerQueueClaimLeaseAcknowledgementAdmissionResult({ ...controlledWorkerQueueClaimLeaseAcknowledgementAdmissionResultFixture, record: { ...controlledWorkerQueueClaimLeaseAcknowledgementAdmissionResultFixture.record!, queue_adapter_defined: true } })).toThrow();
        expect(() => parseControlledWorkerQueueClaimLeaseAcknowledgementAdmissionResult({ ...controlledWorkerQueueClaimLeaseAcknowledgementAdmissionResultFixture, record: { ...controlledWorkerQueueClaimLeaseAcknowledgementAdmissionResultFixture.record!, claim_token: "secret-token" } })).toThrow();
        expect(() => parseControlledWorkerQueueClaimLeaseAcknowledgementAdmissionResult({ ...controlledWorkerQueueClaimLeaseAcknowledgementAdmissionResultFixture, status: { ...controlledWorkerQueueClaimLeaseAcknowledgementAdmissionResultFixture.status!, candidate_record_id: "00000000-0000-4000-8000-000000000099" } })).toThrow();
        expect(() => parseControlledWorkerQueueClaimLeaseAcknowledgementAdmissionCollection({ ...controlledWorkerQueueClaimLeaseAcknowledgementAdmissionCollectionFixture, items: Array.from({ length: 101 }, () => controlledWorkerQueueClaimLeaseAcknowledgementAdmissionCollectionFixture.items[0]), count: 101 })).toThrow();
        expect(() => parseControlledWorkerQueueClaimLeaseAcknowledgementAdmissionCollection({ ...controlledWorkerQueueClaimLeaseAcknowledgementAdmissionCollectionFixture, operator_id: "operator-b" })).toThrow();
    });
});
