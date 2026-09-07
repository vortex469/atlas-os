import { beforeEach, describe, expect, it, vi } from "vitest";
import { atlas } from "./atlas";
import { getWorkerActivationRuntimePrerequisite } from "./workerActivationRuntimePrerequisite";
import { parseControlledWorkerQueueReceipt } from "./controlledWorkerQueueReceipt";
import receiptFixture from "../test/controlledWorkerQueueReceipt";
import { runtimeCollection, runtimeResult } from "../test/workerActivationRuntimePrerequisite";
import { CLOSED_RUNTIME_AUTHORITY } from "../types/workerActivationRuntimePrerequisite";
vi.mock("./atlas", () => ({ atlas: { get: vi.fn() } }));
const receipt = parseControlledWorkerQueueReceipt(receiptFixture, runtimeResult.record.candidate_record_id, runtimeResult.record.admission_id, runtimeResult.record.operator_id);
function responses(collection: unknown = runtimeCollection, result: unknown = runtimeResult) {
    vi.mocked(atlas.get).mockResolvedValueOnce({ data: collection }).mockResolvedValueOnce({ data: result });
}
describe("v0.53 guarded runtime prerequisite reader", () => {
    beforeEach(() => vi.resetAllMocks());
    it("lists owned evidence then reads the exact prerequisite status with credentials", async () => {
        responses();
        expect(await getWorkerActivationRuntimePrerequisite(receipt)).toMatchObject({ lifecycle: "active", prerequisiteId: runtimeResult.record.prerequisite_id });
        const path = `/installation/candidate-records/${receipt.candidateId}/worker-activation-runtime-prerequisites`;
        expect(atlas.get).toHaveBeenNthCalledWith(1, path, { withCredentials: true });
        expect(atlas.get).toHaveBeenNthCalledWith(2, `${path}/${runtimeResult.record.prerequisite_id}`, { withCredentials: true });
    });
    it("returns missing without inventing a prerequisite or fetching an item", async () => {
        responses({ ...runtimeCollection, count: 0, items: [] });
        expect(await getWorkerActivationRuntimePrerequisite(receipt)).toBeNull();
        expect(atlas.get).toHaveBeenCalledTimes(1);
    });
    it("preserves historical Core expiry and duplicate evidence", async () => {
        responses(runtimeCollection, { ...runtimeResult, exact_duplicate: true, status: { ...runtimeResult.status, lifecycle: "expired", evaluated_at: runtimeResult.status.valid_until } });
        expect(await getWorkerActivationRuntimePrerequisite(receipt)).toMatchObject({ lifecycle: "expired", exactDuplicate: true });
    });
    it.each(CLOSED_RUNTIME_AUTHORITY)("fails closed for missing, coerced or elevated %s", async (key) => {
        for (const section of ["collection", "record", "result", "status", "listedRecord"] as const) {
            for (const invalid of [true, undefined, 0, "false"]) {
                vi.resetAllMocks();
                const collection = structuredClone(runtimeCollection), result = structuredClone(runtimeResult);
                const target = section === "collection" ? collection : section === "listedRecord" ? collection.items[0] : section === "result" ? result : result[section];
                Object.assign(target, { [key]: invalid });
                responses(collection, result);
                await expect(getWorkerActivationRuntimePrerequisite(receipt)).rejects.toThrow(/unavailable/);
            }
        }
    });
    it("rejects scope, lineage, schema, lifecycle, fingerprint and unknown-field tampering", async () => {
        const changes = [
            { operator_id: "foreign" }, { candidate_record_id: "foreign" }, { admission_id: "foreign" },
            { prerequisite_id: "../escape" }, { schema: "other" }, { blockers: [] },
            { worker_activation_runtime_prerequisite_recorded: false }, { payload_bytes: 1 },
            { recorded_at: "2099-02-30T12:00:44Z" }, { valid_until: "2099-08-27T12:01:44Z" },
            { subject_fingerprint: { algorithm: "sha1", value: "a".repeat(64), canonicalization: "atlas-jcs-nfc-v1" } },
            { prerequisite_record_fingerprint: { ...runtimeResult.record.prerequisite_record_fingerprint, value: "b".repeat(64) } },
            { endpoint: "secret" },
            { controlled_worker_queue_claim_lease_acknowledgement: { ...receiptFixture.record, worker_started: true } },
            { controlled_worker_queue_claim_lease_acknowledgement_status: { ...receiptFixture.status, lifecycle: "expired" } },
        ];
        for (const change of changes) {
            vi.resetAllMocks();
            responses(runtimeCollection, { ...runtimeResult, record: { ...runtimeResult.record, ...change } });
            await expect(getWorkerActivationRuntimePrerequisite(receipt)).rejects.toThrow();
        }
        for (const change of [{ lifecycle: "expired" }, { evaluated_at: "2099-08-27T12:00:42Z" }, { admission_id: "foreign" }, { blockers: [] }, { recorded_at: "2099-08-27T12:00:45Z" }]) {
            vi.resetAllMocks();
            responses(runtimeCollection, { ...runtimeResult, status: { ...runtimeResult.status, ...change } });
            await expect(getWorkerActivationRuntimePrerequisite(receipt)).rejects.toThrow();
        }
    });
    it("rejects foreign, malformed, oversized or ambiguous collections before item reads", async () => {
        for (const change of [
            { operator_id: "foreign" }, { candidate_record_id: "foreign" }, { schema: "other" },
            { count: 0 }, { items: {} }, { count: 17, items: Array(17).fill(runtimeResult.record) },
            { count: 2, items: [runtimeResult.record, runtimeResult.record] },
            { count: 2, items: [runtimeResult.record, { ...runtimeResult.record, prerequisite_id: "00000000-0000-5000-8000-000000000054" }] },
            { items: [{ ...runtimeResult.record, operator_id: "foreign" }] },
        ]) {
            vi.resetAllMocks();
            responses({ ...runtimeCollection, ...change });
            await expect(getWorkerActivationRuntimePrerequisite(receipt)).rejects.toThrow();
            expect(atlas.get).toHaveBeenCalledTimes(1);
        }
    });
    it("binds the immutable parent receipt without comparing regenerated status fingerprints", async () => {
        responses();
        await expect(getWorkerActivationRuntimePrerequisite({ ...receipt, fingerprints: { ...receipt.fingerprints, status: { ...receipt.fingerprints.status, value: "b".repeat(64) } } })).resolves.not.toBeNull();
        vi.resetAllMocks();
        responses();
        await expect(getWorkerActivationRuntimePrerequisite({ ...receipt, fingerprints: { ...receipt.fingerprints, receipt_record: { ...receipt.fingerprints.receipt_record, value: "b".repeat(64) } } })).rejects.toThrow();
        expect(atlas.get).toHaveBeenCalledTimes(1);
    });
    it("rejects invalid request paths before network access", async () => {
        await expect(getWorkerActivationRuntimePrerequisite({ ...receipt, candidateId: "../other" })).rejects.toThrow();
        expect(atlas.get).not.toHaveBeenCalled();
    });
});
