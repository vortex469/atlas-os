import { beforeEach, describe, expect, it, vi } from "vitest";

import { atlas } from "./atlas";
import { getWorkerBindingActivationEvidence, listWorkerBindingActivationEvidences, parseWorkerBindingActivationEvidenceCollection, parseWorkerBindingActivationEvidenceResult } from "./workerBindingActivationEvidence";
import { workerBindingActivationEvidenceCollectionFixture, workerBindingActivationEvidenceResultFixture } from "../test/workerBindingActivationEvidence";

vi.mock("./atlas", () => ({ atlas: { get: vi.fn() } }));

describe("worker binding activation evidence API", () => {
    beforeEach(() => vi.resetAllMocks());

    it("uses only guarded read endpoints", async () => {
        vi.mocked(atlas.get).mockResolvedValueOnce({ data: workerBindingActivationEvidenceCollectionFixture }).mockResolvedValueOnce({ data: workerBindingActivationEvidenceResultFixture });
        await listWorkerBindingActivationEvidences("candidate/id");
        await getWorkerBindingActivationEvidence("candidate/id", "activation/evidence/id");
        expect(atlas.get).toHaveBeenNthCalledWith(1, "/installation/candidate-records/candidate%2Fid/worker-binding-activation-evidence", { withCredentials: true });
        expect(atlas.get).toHaveBeenNthCalledWith(2, "/installation/candidate-records/candidate%2Fid/worker-binding-activation-evidence/activation%2Fevidence%2Fid", { withCredentials: true });
    });

    it("strictly parses success and rejects authority or sensitive drift", () => {
        expect(parseWorkerBindingActivationEvidenceCollection(workerBindingActivationEvidenceCollectionFixture).items).toHaveLength(1);
        expect(parseWorkerBindingActivationEvidenceResult(workerBindingActivationEvidenceResultFixture).record?.activation_evidence_state).toBe("readiness_gated");
        expect(() => parseWorkerBindingActivationEvidenceResult({ ...workerBindingActivationEvidenceResultFixture, record: { ...workerBindingActivationEvidenceResultFixture.record!, worker_activation_runtime_allowed: true } })).toThrow();
        expect(() => parseWorkerBindingActivationEvidenceResult({ ...workerBindingActivationEvidenceResultFixture, record: { ...workerBindingActivationEvidenceResultFixture.record!, store_endpoint: "http://internal" } })).toThrow();
        expect(() => parseWorkerBindingActivationEvidenceResult({ ...workerBindingActivationEvidenceResultFixture, status: { ...workerBindingActivationEvidenceResultFixture.status!, candidate_record_id: "00000000-0000-4000-8000-000000000099" } })).toThrow();
        expect(() => parseWorkerBindingActivationEvidenceCollection({ ...workerBindingActivationEvidenceCollectionFixture, items: Array.from({ length: 101 }, () => workerBindingActivationEvidenceCollectionFixture.items[0]), count: 101 })).toThrow();
        expect(() => parseWorkerBindingActivationEvidenceCollection({ ...workerBindingActivationEvidenceCollectionFixture, operator_id: "operator-b" })).toThrow();
    });
});
