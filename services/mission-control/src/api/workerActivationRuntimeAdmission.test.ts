import { beforeEach, describe, expect, it, vi } from "vitest";
import { atlas } from "./atlas";
import { getWorkerActivationRuntimeAdmission } from "./workerActivationRuntimeAdmission";
import { admissionCollection, admissionResult, prerequisite } from "../test/workerActivationRuntimeAdmission";
import { CLOSED_RUNTIME_AUTHORITY } from "../types/workerActivationRuntimePrerequisite";
vi.mock("./atlas", () => ({ atlas: { get: vi.fn() } }));
function responses(collection: unknown = admissionCollection, result: unknown = admissionResult) {
    vi.mocked(atlas.get).mockResolvedValueOnce({ data: collection }).mockResolvedValueOnce({ data: result });
}
describe("v0.54 guarded runtime admission reader", () => {
    beforeEach(() => vi.resetAllMocks());
    it("lists owned evidence then reads the exact runtime admission status with credentials", async () => {
        responses();
        expect(await getWorkerActivationRuntimeAdmission(prerequisite)).toMatchObject({ lifecycle: "active", runtimeAdmissionId: admissionResult.record.runtime_admission_id });
        const path = `/installation/candidate-records/${prerequisite.candidateId}/worker-activation-runtime-admissions`;
        expect(atlas.get).toHaveBeenNthCalledWith(1, path, { withCredentials: true });
        expect(atlas.get).toHaveBeenNthCalledWith(2, `${path}/${admissionResult.record.runtime_admission_id}`, { withCredentials: true });
    });
    it("returns missing without inventing an admission or fetching an item", async () => {
        responses({ ...admissionCollection, count: 0, items: [] });
        expect(await getWorkerActivationRuntimeAdmission(prerequisite)).toBeNull();
        expect(atlas.get).toHaveBeenCalledTimes(1);
    });
    it("preserves historical Core expiry and duplicate evidence", async () => {
        responses(admissionCollection, { ...admissionResult, exact_duplicate: true, status: { ...admissionResult.status, lifecycle: "expired", evaluated_at: admissionResult.status.valid_until } });
        expect(await getWorkerActivationRuntimeAdmission(prerequisite)).toMatchObject({ lifecycle: "expired", exactDuplicate: true });
    });
    it.each(CLOSED_RUNTIME_AUTHORITY)("fails closed for missing, coerced or elevated %s", async (key) => {
        for (const section of ["collection", "record", "result", "status", "listedRecord"] as const) {
            for (const invalid of [true, undefined, 0, "false"]) {
                vi.resetAllMocks();
                const collection = structuredClone(admissionCollection), result = structuredClone(admissionResult);
                const target = section === "collection" ? collection : section === "listedRecord" ? collection.items[0] : section === "result" ? result : result[section];
                Object.assign(target, { [key]: invalid });
                responses(collection, result);
                await expect(getWorkerActivationRuntimeAdmission(prerequisite)).rejects.toThrow(/unavailable/);
            }
        }
    });
    it("rejects scope, lineage, schema, lifecycle, fingerprint and unknown-field tampering", async () => {
        const changes = [
            { operator_id: "foreign" }, { candidate_record_id: "foreign" }, { admission_id: "foreign" },
            { prerequisite_id: "../escape" }, { schema: "other" }, { blockers: [] },
            { worker_activation_runtime_admission_recorded: false }, { payload_bytes: 1 },
            { recorded_at: "2099-02-30T12:00:44Z" }, { valid_until: "2099-08-27T12:01:44Z" },
            { subject_fingerprint: { algorithm: "sha1", value: "a".repeat(64), canonicalization: "atlas-jcs-nfc-v1" } },
            { runtime_admission_record_fingerprint: { ...admissionResult.record.runtime_admission_record_fingerprint, value: "b".repeat(64) } },
            { endpoint: "secret" },
            { worker_activation_runtime_prerequisite: { ...admissionResult.record.worker_activation_runtime_prerequisite, worker_started: true } },
            { worker_activation_runtime_prerequisite_status: { ...admissionResult.record.worker_activation_runtime_prerequisite_status, lifecycle: "expired" } },
        ];
        for (const change of changes) {
            vi.resetAllMocks();
            responses(admissionCollection, { ...admissionResult, record: { ...admissionResult.record, ...change } });
            await expect(getWorkerActivationRuntimeAdmission(prerequisite)).rejects.toThrow();
        }
        for (const change of [{ lifecycle: "expired" }, { evaluated_at: "2099-08-27T12:00:42Z" }, { admission_id: "foreign" }, { blockers: [] }, { recorded_at: "2099-08-27T12:00:45Z" }]) {
            vi.resetAllMocks();
            responses(admissionCollection, { ...admissionResult, status: { ...admissionResult.status, ...change } });
            await expect(getWorkerActivationRuntimeAdmission(prerequisite)).rejects.toThrow();
        }
    });
    it("rejects foreign, malformed, oversized or ambiguous collections before item reads", async () => {
        for (const change of [
            { operator_id: "foreign" }, { candidate_record_id: "foreign" }, { schema: "other" },
            { count: 0 }, { items: {} }, { count: 17, items: Array(17).fill(admissionResult.record) },
            { count: 2, items: [admissionResult.record, admissionResult.record] },
            { count: 2, items: [admissionResult.record, { ...admissionResult.record, runtime_admission_id: "00000000-0000-5000-8000-000000000055" }] },
            { items: [{ ...admissionResult.record, operator_id: "foreign" }] },
        ]) {
            vi.resetAllMocks();
            responses({ ...admissionCollection, ...change });
            await expect(getWorkerActivationRuntimeAdmission(prerequisite)).rejects.toThrow();
            expect(atlas.get).toHaveBeenCalledTimes(1);
        }
    });
    it("binds the immutable parent prerequisite without comparing regenerated status fingerprints", async () => {
        responses();
        await expect(getWorkerActivationRuntimeAdmission({ ...prerequisite, fingerprints: { ...prerequisite.fingerprints, status: { ...prerequisite.fingerprints.status, value: "b".repeat(64) } } })).resolves.not.toBeNull();
        vi.resetAllMocks();
        responses();
        await expect(getWorkerActivationRuntimeAdmission({ ...prerequisite, fingerprints: { ...prerequisite.fingerprints, prerequisite_record: { ...prerequisite.fingerprints.prerequisite_record, value: "b".repeat(64) } } })).rejects.toThrow();
        expect(atlas.get).toHaveBeenCalledTimes(1);
    });
    it("rejects invalid request paths before network access", async () => {
        await expect(getWorkerActivationRuntimeAdmission({ ...prerequisite, candidateId: "../other" })).rejects.toThrow();
        expect(atlas.get).not.toHaveBeenCalled();
    });
});

describe("v0.54 immutable evidence boundary", () => {
    beforeEach(() => vi.resetAllMocks());
    it("rejects changed immutable list/item evidence even with an unchanged record fingerprint", async () => {
        responses(admissionCollection, { ...admissionResult, record: { ...admissionResult.record, subject_fingerprint: { ...admissionResult.record.subject_fingerprint, value: "b".repeat(64) } } });
        await expect(getWorkerActivationRuntimeAdmission(prerequisite)).rejects.toThrow(/unavailable/);
    });
    it("accepts reordered object keys without rewriting lineage", async () => {
        const result = { ...admissionResult, record: Object.fromEntries(Object.entries(admissionResult.record).reverse()) };
        responses(admissionCollection, result);
        expect(await getWorkerActivationRuntimeAdmission(prerequisite)).toMatchObject({ lineage: { record: admissionResult.record.worker_activation_runtime_prerequisite, status: admissionResult.record.worker_activation_runtime_prerequisite_status } });
    });
    it("rejects oversized models before exposing lineage", async () => {
        responses({ ...admissionCollection, padding: "x".repeat(192 * 1024) });
        await expect(getWorkerActivationRuntimeAdmission(prerequisite)).rejects.toThrow(/unavailable/);
        expect(atlas.get).toHaveBeenCalledTimes(1);
    });
    it("validates nested v0.53 authority in both the record and its status", async () => {
        for (const key of CLOSED_RUNTIME_AUTHORITY) {
            for (const field of ["worker_activation_runtime_prerequisite", "worker_activation_runtime_prerequisite_status"] as const) {
                vi.resetAllMocks();
                const result = structuredClone(admissionResult);
                Object.assign(result.record[field], { [key]: true });
                responses(admissionCollection, result);
                await expect(getWorkerActivationRuntimeAdmission(prerequisite)).rejects.toThrow();
            }
        }
    });
    it("rejects mismatched prerequisite status fingerprints and IDs", async () => {
        for (const change of [
            { prerequisite_record_fingerprint: { ...admissionResult.record.worker_activation_runtime_prerequisite_status.prerequisite_record_fingerprint, value: "b".repeat(64) } },
            { prerequisite_id: "00000000-0000-5000-8000-000000000055" },
        ]) {
            vi.resetAllMocks();
            const result = structuredClone(admissionResult);
            Object.assign(result.record.worker_activation_runtime_prerequisite_status, change);
            responses(admissionCollection, result);
            await expect(getWorkerActivationRuntimeAdmission(prerequisite)).rejects.toThrow();
        }
    });
});
