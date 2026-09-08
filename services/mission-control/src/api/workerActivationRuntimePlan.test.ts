import { beforeEach, describe, expect, it, vi } from "vitest";
import { atlas } from "./atlas";
import { getWorkerActivationRuntimePlan } from "./workerActivationRuntimePlan";
import { planCollection, planResult, admission as parentAdmission } from "../test/workerActivationRuntimePlan";
import { CLOSED_RUNTIME_AUTHORITY } from "../types/workerActivationRuntimePrerequisite";
vi.mock("./atlas", () => ({ atlas: { get: vi.fn() } }));
function responses(collection: unknown = planCollection, result: unknown = planResult) {
    vi.mocked(atlas.get).mockResolvedValueOnce({ data: collection }).mockResolvedValueOnce({ data: result });
}
describe("v0.55 guarded runtime plan reader", () => {
    beforeEach(() => vi.resetAllMocks());
    it("lists owned evidence then reads the exact runtime plan status with credentials", async () => {
        responses();
        expect(await getWorkerActivationRuntimePlan(parentAdmission)).toMatchObject({ lifecycle: "active", runtimePlanId: planResult.record.runtime_plan_id });
        const path = `/installation/candidate-records/${parentAdmission.candidateId}/worker-activation-runtime-plans`;
        expect(atlas.get).toHaveBeenNthCalledWith(1, path, { withCredentials: true });
        expect(atlas.get).toHaveBeenNthCalledWith(2, `${path}/${planResult.record.runtime_plan_id}`, { withCredentials: true });
    });
    it("returns missing without inventing a plan or fetching an item", async () => {
        responses({ ...planCollection, count: 0, items: [] });
        expect(await getWorkerActivationRuntimePlan(parentAdmission)).toBeNull();
        expect(atlas.get).toHaveBeenCalledTimes(1);
    });
    it("preserves historical Core expiry and duplicate evidence", async () => {
        responses(planCollection, { ...planResult, exact_duplicate: true, status: { ...planResult.status, lifecycle: "expired", evaluated_at: planResult.status.valid_until } });
        expect(await getWorkerActivationRuntimePlan(parentAdmission)).toMatchObject({ lifecycle: "expired", exactDuplicate: true });
    });
    it.each(CLOSED_RUNTIME_AUTHORITY)("fails closed for missing, coerced or elevated %s", async (key) => {
        for (const section of ["collection", "record", "result", "status", "listedRecord", "design"] as const) {
            for (const invalid of [true, undefined, 0, "false"]) {
                vi.resetAllMocks();
                const collection = structuredClone(planCollection), result = structuredClone(planResult);
                const target = section === "design" ? result.record.design : section === "collection" ? collection : section === "listedRecord" ? collection.items[0] : section === "result" ? result : result[section];
                Object.assign(target, { [key]: invalid });
                responses(collection, result);
                await expect(getWorkerActivationRuntimePlan(parentAdmission)).rejects.toThrow(/unavailable/);
            }
        }
    });
    it("rejects scope, lineage, schema, lifecycle, fingerprint and unknown-field tampering", async () => {
        const changes = [
            { operator_id: "foreign" }, { candidate_record_id: "foreign" }, { admission_id: "foreign" },
            { runtime_admission_id: "../escape" }, { schema: "other" }, { blockers: [] },
            { worker_activation_runtime_admission_recorded: false }, { payload_bytes: 1 },
            { recorded_at: "2099-02-30T12:00:44Z" }, { valid_until: "2099-08-27T12:01:44Z" },
            { subject_fingerprint: { algorithm: "sha1", value: "a".repeat(64), canonicalization: "atlas-jcs-nfc-v1" } },
            { runtime_plan_record_fingerprint: { ...planResult.record.runtime_plan_record_fingerprint, value: "b".repeat(64) } },
            { endpoint: "secret" },
            { worker_activation_runtime_admission: { ...planResult.record.worker_activation_runtime_admission, worker_started: true } },
            { worker_activation_runtime_admission_status: { ...planResult.record.worker_activation_runtime_admission_status, lifecycle: "expired" } },
        ];
        for (const change of changes) {
            vi.resetAllMocks();
            responses(planCollection, { ...planResult, record: { ...planResult.record, ...change } });
            await expect(getWorkerActivationRuntimePlan(parentAdmission)).rejects.toThrow();
        }
        for (const change of [{ lifecycle: "expired" }, { evaluated_at: "2099-08-27T12:00:42Z" }, { admission_id: "foreign" }, { blockers: [] }, { recorded_at: "2099-08-27T12:00:45Z" }]) {
            vi.resetAllMocks();
            responses(planCollection, { ...planResult, status: { ...planResult.status, ...change } });
            await expect(getWorkerActivationRuntimePlan(parentAdmission)).rejects.toThrow();
        }
    });
    it("rejects foreign, malformed, oversized or ambiguous collections before item reads", async () => {
        for (const change of [
            { operator_id: "foreign" }, { candidate_record_id: "foreign" }, { schema: "other" },
            { count: 0 }, { items: {} }, { count: 17, items: Array(17).fill(planResult.record) },
            { count: 2, items: [planResult.record, planResult.record] },
            { count: 2, items: [planResult.record, { ...planResult.record, runtime_plan_id: "00000000-0000-5000-8000-000000000056" }] },
            { items: [{ ...planResult.record, operator_id: "foreign" }] },
        ]) {
            vi.resetAllMocks();
            responses({ ...planCollection, ...change });
            await expect(getWorkerActivationRuntimePlan(parentAdmission)).rejects.toThrow();
            expect(atlas.get).toHaveBeenCalledTimes(1);
        }
    });
    it("binds exact parent evidence while allowing a newer Core status", async () => {
        responses();
        await expect(getWorkerActivationRuntimePlan({ ...parentAdmission, evaluatedAt: parentAdmission.validUntil, lifecycle: "expired" })).resolves.not.toBeNull();
        vi.resetAllMocks();
        responses();
        await expect(getWorkerActivationRuntimePlan({ ...parentAdmission, exactRecord: { ...planResult.record.worker_activation_runtime_admission, subject_fingerprint: { ...planResult.record.subject_fingerprint, value: "b".repeat(64) } } })).rejects.toThrow();
        expect(atlas.get).toHaveBeenCalledTimes(1);
    });
    it("rejects invalid request paths before network access", async () => {
        await expect(getWorkerActivationRuntimePlan({ ...parentAdmission, candidateId: "../other" })).rejects.toThrow();
        expect(atlas.get).not.toHaveBeenCalled();
    });
});

describe("v0.55 immutable evidence boundary", () => {
    beforeEach(() => vi.resetAllMocks());
    it("rejects changed immutable list/item evidence even with an unchanged record fingerprint", async () => {
        responses(planCollection, { ...planResult, record: { ...planResult.record, subject_fingerprint: { ...planResult.record.subject_fingerprint, value: "b".repeat(64) } } });
        await expect(getWorkerActivationRuntimePlan(parentAdmission)).rejects.toThrow(/unavailable/);
    });
    it("accepts reordered object keys without rewriting lineage", async () => {
        const result = { ...planResult, record: Object.fromEntries(Object.entries(planResult.record).reverse()) };
        responses(planCollection, result);
        expect(await getWorkerActivationRuntimePlan(parentAdmission)).toMatchObject({ lineage: { record: planResult.record.worker_activation_runtime_admission, status: planResult.record.worker_activation_runtime_admission_status } });
    });
    it("rejects oversized models before exposing lineage", async () => {
        responses({ ...planCollection, padding: "x".repeat(192 * 1024) });
        await expect(getWorkerActivationRuntimePlan(parentAdmission)).rejects.toThrow(/unavailable/);
        expect(atlas.get).toHaveBeenCalledTimes(1);
    });
    // Give every key/field pair its own timeout while retaining the full hostile matrix.
    describe.each(["worker_activation_runtime_admission", "worker_activation_runtime_admission_status"] as const)("nested v0.54 authority in %s", (field) => {
        it.each(CLOSED_RUNTIME_AUTHORITY)("rejects elevated %s", async (key) => {
            // Copy the mutated path only; the reader does not mutate shared lineage.
            const result = {
                ...planResult,
                record: {
                    ...planResult.record,
                    [field]: { ...planResult.record[field], [key]: true },
                },
            };
            responses(planCollection, result);
            await expect(getWorkerActivationRuntimePlan(parentAdmission)).rejects.toThrow();
        });
    });
    it("rejects mismatched admission status fingerprints and IDs", async () => {
        for (const change of [
            { runtime_admission_record_fingerprint: { ...planResult.record.worker_activation_runtime_admission_status.runtime_admission_record_fingerprint, value: "b".repeat(64) } },
            { runtime_admission_id: "00000000-0000-5000-8000-000000000055" },
        ]) {
            vi.resetAllMocks();
            const result = structuredClone(planResult);
            Object.assign(result.record.worker_activation_runtime_admission_status, change);
            responses(planCollection, result);
            await expect(getWorkerActivationRuntimePlan(parentAdmission)).rejects.toThrow();
        }
    });
});

describe("v0.55 closed reference-only design", () => {
    beforeEach(() => vi.resetAllMocks());
    it.each(Object.keys(planResult.record.design))("rejects altered or missing design field %s", async (key) => {
        for (const value of [undefined, "caller-designed"]) {
            vi.resetAllMocks();
            const record = { ...planResult.record, design: { ...planResult.record.design, [key]: value } };
            responses({ ...planCollection, items: [record] }, { ...planResult, record });
            await expect(getWorkerActivationRuntimePlan(parentAdmission)).rejects.toThrow();
        }
    });
});

describe("v0.55 envelope and scope binding", () => {
    beforeEach(() => vi.resetAllMocks());
    it.each(["record", "status", "result"] as const)("rejects absent or false plan markers in %s", async (section) => {
        for (const marker of [undefined, false, 1, "true"]) {
            vi.resetAllMocks();
            const result = structuredClone(planResult);
            Object.assign(section === "result" ? result : result[section], { worker_activation_runtime_plan_recorded: marker });
            responses(planCollection, result);
            await expect(getWorkerActivationRuntimePlan(parentAdmission)).rejects.toThrow();
        }
    });
    it("returns missing for a different exact admission, without selecting the latest plan", async () => {
        responses();
        expect(await getWorkerActivationRuntimePlan({ ...parentAdmission, runtimeAdmissionId: "00000000-0000-5000-8000-000000000056" })).toBeNull();
        expect(atlas.get).toHaveBeenCalledTimes(1);
    });
    it("rejects unknown design fields and oversized item responses", async () => {
        responses(planCollection, { ...planResult, record: { ...planResult.record, design: { ...planResult.record.design, endpoint: "secret" } } });
        await expect(getWorkerActivationRuntimePlan(parentAdmission)).rejects.toThrow();
        vi.resetAllMocks();
        responses(planCollection, { ...planResult, padding: "x".repeat(192 * 1024) });
        await expect(getWorkerActivationRuntimePlan(parentAdmission)).rejects.toThrow();
    });
});
