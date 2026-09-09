import { beforeEach, describe, expect, it, vi } from "vitest";
import { atlas } from "./atlas";
import { getWorkerActivationRuntimePlanReview } from "./workerActivationRuntimePlanReview";
import { reviewCollection, reviewResult, plan as parentAdmission } from "../test/workerActivationRuntimePlanReview";
import { CLOSED_RUNTIME_AUTHORITY } from "../types/workerActivationRuntimePrerequisite";
vi.mock("./atlas", () => ({ atlas: { get: vi.fn() } }));
function responses(collection: unknown = reviewCollection, result: unknown = reviewResult) {
    vi.mocked(atlas.get).mockResolvedValueOnce({ data: collection }).mockResolvedValueOnce({ data: result });
}
describe("v0.56 guarded runtime plan reader", () => {
    beforeEach(() => vi.resetAllMocks());
    it("lists owned evidence then reads the exact runtime plan status with credentials", async () => {
        responses();
        expect(await getWorkerActivationRuntimePlanReview(parentAdmission)).toMatchObject({ lifecycle: "active", runtimePlanReviewId: reviewResult.record.runtime_plan_review_id });
        const path = `/installation/candidate-records/${parentAdmission.candidateId}/worker-activation-runtime-plan-reviews`;
        expect(atlas.get).toHaveBeenNthCalledWith(1, path, { withCredentials: true });
        expect(atlas.get).toHaveBeenNthCalledWith(2, `${path}/${reviewResult.record.runtime_plan_review_id}`, { withCredentials: true });
    });
    it("returns missing without inventing a plan or fetching an item", async () => {
        responses({ ...reviewCollection, count: 0, items: [] });
        expect(await getWorkerActivationRuntimePlanReview(parentAdmission)).toBeNull();
        expect(atlas.get).toHaveBeenCalledTimes(1);
    });
    it("preserves historical Core expiry and duplicate evidence", async () => {
        responses(reviewCollection, { ...reviewResult, exact_duplicate: true, status: { ...reviewResult.status, lifecycle: "expired", evaluated_at: reviewResult.status.valid_until } });
        expect(await getWorkerActivationRuntimePlanReview(parentAdmission)).toMatchObject({ lifecycle: "expired", exactDuplicate: true });
    });
    it.each(CLOSED_RUNTIME_AUTHORITY)("fails closed for missing, coerced or elevated %s", async (key) => {
        for (const section of ["collection", "record", "result", "status", "listedRecord"] as const) {
            for (const invalid of [true, undefined, 0, "false"]) {
                vi.resetAllMocks();
                const collection = structuredClone(reviewCollection), result = structuredClone(reviewResult);
                const target = section === "collection" ? collection : section === "listedRecord" ? collection.items[0] : section === "result" ? result : result[section];
                Object.assign(target, { [key]: invalid });
                responses(collection, result);
                await expect(getWorkerActivationRuntimePlanReview(parentAdmission)).rejects.toThrow(/unavailable/);
            }
        }
    });
    it("rejects scope, lineage, schema, lifecycle, fingerprint and unknown-field tampering", async () => {
        const changes = [
            { operator_id: "foreign" }, { candidate_record_id: "foreign" }, { admission_id: "foreign" },
            { runtime_plan_id: "../escape" }, { schema: "other" }, { blockers: [] },
            { worker_activation_runtime_plan_recorded: false }, { payload_bytes: 1 },
            { recorded_at: "2099-02-30T12:00:44Z" }, { valid_until: "2099-08-27T12:01:44Z" },
            { subject_fingerprint: { algorithm: "sha1", value: "a".repeat(64), canonicalization: "atlas-jcs-nfc-v1" } },
            { runtime_plan_review_record_fingerprint: { ...reviewResult.record.runtime_plan_review_record_fingerprint, value: "b".repeat(64) } },
            { endpoint: "secret" },
            { worker_activation_runtime_plan: { ...reviewResult.record.worker_activation_runtime_plan, worker_started: true } },
            { worker_activation_runtime_plan_status: { ...reviewResult.record.worker_activation_runtime_plan_status, lifecycle: "expired" } },
        ];
        for (const change of changes) {
            vi.resetAllMocks();
            responses(reviewCollection, { ...reviewResult, record: { ...reviewResult.record, ...change } });
            await expect(getWorkerActivationRuntimePlanReview(parentAdmission)).rejects.toThrow();
        }
        for (const change of [{ lifecycle: "expired" }, { evaluated_at: "2099-08-27T12:00:42Z" }, { admission_id: "foreign" }, { blockers: [] }, { recorded_at: "2099-08-27T12:00:45Z" }]) {
            vi.resetAllMocks();
            responses(reviewCollection, { ...reviewResult, status: { ...reviewResult.status, ...change } });
            await expect(getWorkerActivationRuntimePlanReview(parentAdmission)).rejects.toThrow();
        }
    });
    it("rejects foreign, malformed, oversized or ambiguous collections before item reads", async () => {
        for (const change of [
            { operator_id: "foreign" }, { candidate_record_id: "foreign" }, { schema: "other" },
            { count: 0 }, { items: {} }, { count: 17, items: Array(17).fill(reviewResult.record) },
            { count: 2, items: [reviewResult.record, reviewResult.record] },
            { count: 2, items: [reviewResult.record, { ...reviewResult.record, runtime_plan_review_id: "00000000-0000-5000-8000-000000000057" }] },
            { items: [{ ...reviewResult.record, operator_id: "foreign" }] },
        ]) {
            vi.resetAllMocks();
            responses({ ...reviewCollection, ...change });
            await expect(getWorkerActivationRuntimePlanReview(parentAdmission)).rejects.toThrow();
            expect(atlas.get).toHaveBeenCalledTimes(1);
        }
    });
    it("binds exact parent evidence while allowing a newer Core status", async () => {
        responses();
        await expect(getWorkerActivationRuntimePlanReview({ ...parentAdmission, evaluatedAt: parentAdmission.validUntil, lifecycle: "expired" })).resolves.not.toBeNull();
        vi.resetAllMocks();
        responses();
        await expect(getWorkerActivationRuntimePlanReview({ ...parentAdmission, exactRecord: { ...reviewResult.record.worker_activation_runtime_plan, subject_fingerprint: { ...reviewResult.record.subject_fingerprint, value: "b".repeat(64) } } })).rejects.toThrow();
        expect(atlas.get).toHaveBeenCalledTimes(1);
    });
    it("rejects invalid request paths before network access", async () => {
        await expect(getWorkerActivationRuntimePlanReview({ ...parentAdmission, candidateId: "../other" })).rejects.toThrow();
        expect(atlas.get).not.toHaveBeenCalled();
    });
});

describe("v0.56 immutable evidence boundary", () => {
    beforeEach(() => vi.resetAllMocks());
    it("rejects changed immutable list/item evidence even with an unchanged record fingerprint", async () => {
        responses(reviewCollection, { ...reviewResult, record: { ...reviewResult.record, subject_fingerprint: { ...reviewResult.record.subject_fingerprint, value: "b".repeat(64) } } });
        await expect(getWorkerActivationRuntimePlanReview(parentAdmission)).rejects.toThrow(/unavailable/);
    });
    it("accepts reordered object keys without rewriting lineage", async () => {
        const result = { ...reviewResult, record: Object.fromEntries(Object.entries(reviewResult.record).reverse()) };
        responses(reviewCollection, result);
        expect(await getWorkerActivationRuntimePlanReview(parentAdmission)).toMatchObject({ lineage: { record: reviewResult.record.worker_activation_runtime_plan, status: reviewResult.record.worker_activation_runtime_plan_status } });
    });
    it("rejects oversized models before exposing lineage", async () => {
        responses({ ...reviewCollection, padding: "x".repeat(192 * 1024) });
        await expect(getWorkerActivationRuntimePlanReview(parentAdmission)).rejects.toThrow(/unavailable/);
        expect(atlas.get).toHaveBeenCalledTimes(1);
    });
    // Give every key/field pair its own timeout while retaining the full hostile matrix.
    describe.each(["worker_activation_runtime_plan", "worker_activation_runtime_plan_status"] as const)("nested v0.55 authority in %s", (field) => {
        it.each(CLOSED_RUNTIME_AUTHORITY)("rejects elevated %s", async (key) => {
            // Copy the mutated path only; the reader does not mutate shared lineage.
            const result = {
                ...reviewResult,
                record: {
                    ...reviewResult.record,
                    [field]: { ...reviewResult.record[field], [key]: true },
                },
            };
            responses(reviewCollection, result);
            await expect(getWorkerActivationRuntimePlanReview(parentAdmission)).rejects.toThrow();
        });
    });
    it("rejects mismatched admission status fingerprints and IDs", async () => {
        for (const change of [
            { runtime_plan_record_fingerprint: { ...reviewResult.record.worker_activation_runtime_plan_status.runtime_plan_record_fingerprint, value: "b".repeat(64) } },
            { runtime_plan_id: "00000000-0000-5000-8000-000000000057" },
        ]) {
            vi.resetAllMocks();
            const result = structuredClone(reviewResult);
            Object.assign(result.record.worker_activation_runtime_plan_status, change);
            responses(reviewCollection, result);
            await expect(getWorkerActivationRuntimePlanReview(parentAdmission)).rejects.toThrow();
        }
    });
});

describe("v0.56 envelope and scope binding", () => {
    beforeEach(() => vi.resetAllMocks());
    it.each(["record", "status", "result"] as const)("rejects absent or false plan markers in %s", async (section) => {
        for (const marker of [undefined, false, 1, "true"]) {
            vi.resetAllMocks();
            const result = structuredClone(reviewResult);
            Object.assign(section === "result" ? result : result[section], { worker_activation_runtime_plan_review_recorded: marker });
            responses(reviewCollection, result);
            await expect(getWorkerActivationRuntimePlanReview(parentAdmission)).rejects.toThrow();
        }
    });
    it("returns missing for a different exact admission, without selecting the latest plan", async () => {
        responses();
        expect(await getWorkerActivationRuntimePlanReview({ ...parentAdmission, runtimePlanId: "00000000-0000-5000-8000-000000000057" })).toBeNull();
        expect(atlas.get).toHaveBeenCalledTimes(1);
    });
    it("rejects unknown design fields and oversized item responses", async () => {
        responses(reviewCollection, { ...reviewResult, record: { ...reviewResult.record, profile: "caller-defined" } });
        await expect(getWorkerActivationRuntimePlanReview(parentAdmission)).rejects.toThrow();
        vi.resetAllMocks();
        responses(reviewCollection, { ...reviewResult, padding: "x".repeat(192 * 1024) });
        await expect(getWorkerActivationRuntimePlanReview(parentAdmission)).rejects.toThrow();
    });
});

describe("v0.56 fixed consistency findings", () => {
    beforeEach(() => vi.resetAllMocks());
    it.each([
        { profile: "approved" }, { findings: [] },
        { findings: [...reviewResult.record.findings].reverse() },
        { findings: [...reviewResult.record.findings, "runtime_ready"] },
        { runtime_admission_id: "00000000-0000-5000-8000-000000000057" },
        { worker_activation_runtime_plan_review_recorded: false },
    ])("rejects altered listed and item evidence: %j", async (change) => {
        const record = { ...reviewResult.record, ...change };
        responses({ ...reviewCollection, items: [record] }, { ...reviewResult, record });
        await expect(getWorkerActivationRuntimePlanReview(parentAdmission)).rejects.toThrow();
        expect(atlas.get).toHaveBeenCalledTimes(1);
    });
});
