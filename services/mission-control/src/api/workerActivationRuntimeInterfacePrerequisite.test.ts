import coreGoldenJson from "../test/workerActivationRuntimeInterfacePrerequisite.core.json?raw";
import { parseWorkerActivationRuntimePlanReview } from "./workerActivationRuntimePlanReview";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { atlas } from "./atlas";
import { getWorkerActivationRuntimeInterfacePrerequisite } from "./workerActivationRuntimeInterfacePrerequisite";
import { inventoryCollection, inventoryResult, review as parentAdmission } from "../test/workerActivationRuntimeInterfacePrerequisite";
import { CLOSED_RUNTIME_AUTHORITY } from "../types/workerActivationRuntimePrerequisite";
const coreGolden = JSON.parse(coreGoldenJson) as { result: typeof inventoryResult; collection: Omit<typeof inventoryCollection, "items"> };
vi.mock("./atlas", () => ({ atlas: { get: vi.fn() } }));
function responses(collection: unknown = inventoryCollection, result: unknown = inventoryResult) {
    vi.mocked(atlas.get).mockResolvedValueOnce({ data: collection }).mockResolvedValueOnce({ data: result });
}
describe("v0.60 retained guarded interface prerequisite reader", () => {
    beforeEach(() => vi.resetAllMocks());
    describe.each(["collection", "listedRecord", "result", "record", "status", "review", "reviewStatus"] as const)("closed retained %s envelope", (section) => {
        it.each([
            { worker_activation_runtime_defined: true },
            { worker_activation_runtime_defined: false },
            { schema: "worker-activation-runtime-definition-result-v1" },
            { worker_activation_runtime_interface_admitted: true },
            { worker_activation_runtime_interface_admitted: false },
            { worker_activation_runtime_interface_definition_review_recorded: true },
            { worker_activation_runtime_interface_definition_review_recorded: false },
            { schema: "worker-activation-runtime-interface-definition-review-v1" },
        ])("rejects synthesized successor evidence: %j", async (change) => {
            const collection = structuredClone(inventoryCollection), result = structuredClone(inventoryResult);
            const target = section === "collection" ? collection
                : section === "listedRecord" ? collection.items[0]
                : section === "review" ? result.record.worker_activation_runtime_plan_review
                : section === "reviewStatus" ? result.record.worker_activation_runtime_plan_review_status
                : section === "result" ? result : result[section];
            Object.assign(target, change);
            responses(collection, result);
            await expect(getWorkerActivationRuntimeInterfacePrerequisite(parentAdmission)).rejects.toThrow(/unavailable/);
            expect(atlas.get).toHaveBeenCalledTimes(section === "collection" || section === "listedRecord" ? 1 : 2);
        });
    });
    it("lists owned evidence then reads the exact interface prerequisite status with credentials", async () => {
        responses();
        expect(await getWorkerActivationRuntimeInterfacePrerequisite(parentAdmission)).toMatchObject({ lifecycle: "active", runtimeInterfacePrerequisiteId: inventoryResult.record.runtime_interface_prerequisite_id });
        const path = `/installation/candidate-records/${parentAdmission.candidateId}/worker-activation-runtime-interface-prerequisites`;
        expect(atlas.get).toHaveBeenNthCalledWith(1, path, { withCredentials: true });
        expect(atlas.get).toHaveBeenNthCalledWith(2, `${path}/${inventoryResult.record.runtime_interface_prerequisite_id}`, { withCredentials: true });
    });
    it("returns missing without inventing a plan or fetching an item", async () => {
        responses({ ...inventoryCollection, count: 0, items: [] });
        expect(await getWorkerActivationRuntimeInterfacePrerequisite(parentAdmission)).toBeNull();
        expect(atlas.get).toHaveBeenCalledTimes(1);
    });
    it("preserves historical Core expiry and duplicate evidence", async () => {
        responses(inventoryCollection, { ...inventoryResult, exact_duplicate: true, status: { ...inventoryResult.status, lifecycle: "expired", evaluated_at: inventoryResult.status.valid_until } });
        expect(await getWorkerActivationRuntimeInterfacePrerequisite(parentAdmission)).toMatchObject({ lifecycle: "expired", exactDuplicate: true });
    });
    it.each(CLOSED_RUNTIME_AUTHORITY)("fails closed for missing, coerced or elevated %s", async (key) => {
        for (const section of ["collection", "record", "result", "status", "listedRecord"] as const) {
            for (const invalid of [true, undefined, 0, "false"]) {
                vi.resetAllMocks();
                const collection = structuredClone(inventoryCollection), result = structuredClone(inventoryResult);
                const target = section === "collection" ? collection : section === "listedRecord" ? collection.items[0] : section === "result" ? result : result[section];
                Object.assign(target, { [key]: invalid });
                responses(collection, result);
                await expect(getWorkerActivationRuntimeInterfacePrerequisite(parentAdmission)).rejects.toThrow(/unavailable/);
            }
        }
    });
    it("rejects scope, lineage, schema, lifecycle, fingerprint and unknown-field tampering", async () => {
        const changes = [
            { operator_id: "foreign" }, { candidate_record_id: "foreign" }, { admission_id: "foreign" },
            { runtime_plan_review_id: "../escape" }, { schema: "other" }, { blockers: [] },
            { worker_activation_runtime_plan_review_recorded: false }, { payload_bytes: 1 },
            { recorded_at: "2099-02-30T12:00:44Z" }, { valid_until: "2099-08-27T12:01:44Z" },
            { subject_fingerprint: { algorithm: "sha1", value: "a".repeat(64), canonicalization: "atlas-jcs-nfc-v1" } },
            { runtime_interface_prerequisite_record_fingerprint: { ...inventoryResult.record.runtime_interface_prerequisite_record_fingerprint, value: "b".repeat(64) } },
            { endpoint: "secret" },
            { worker_activation_runtime_plan_review: { ...inventoryResult.record.worker_activation_runtime_plan_review, worker_started: true } },
            { worker_activation_runtime_plan_review_status: { ...inventoryResult.record.worker_activation_runtime_plan_review_status, lifecycle: "expired" } },
        ];
        for (const change of changes) {
            vi.resetAllMocks();
            responses(inventoryCollection, { ...inventoryResult, record: { ...inventoryResult.record, ...change } });
            await expect(getWorkerActivationRuntimeInterfacePrerequisite(parentAdmission)).rejects.toThrow();
        }
        for (const change of [{ lifecycle: "expired" }, { evaluated_at: "2099-08-27T12:00:42Z" }, { admission_id: "foreign" }, { blockers: [] }, { recorded_at: "2099-08-27T12:00:45Z" }]) {
            vi.resetAllMocks();
            responses(inventoryCollection, { ...inventoryResult, status: { ...inventoryResult.status, ...change } });
            await expect(getWorkerActivationRuntimeInterfacePrerequisite(parentAdmission)).rejects.toThrow();
        }
    });
    it("rejects foreign, malformed, oversized or ambiguous collections before item reads", async () => {
        for (const change of [
            { operator_id: "foreign" }, { candidate_record_id: "foreign" }, { schema: "other" },
            { count: 0 }, { items: {} }, { count: 17, items: Array(17).fill(inventoryResult.record) },
            { count: 2, items: [inventoryResult.record, inventoryResult.record] },
            { count: 2, items: [inventoryResult.record, { ...inventoryResult.record, runtime_interface_prerequisite_id: "00000000-0000-5000-8000-000000000058" }] },
            { items: [{ ...inventoryResult.record, operator_id: "foreign" }] },
        ]) {
            vi.resetAllMocks();
            responses({ ...inventoryCollection, ...change });
            await expect(getWorkerActivationRuntimeInterfacePrerequisite(parentAdmission)).rejects.toThrow();
            expect(atlas.get).toHaveBeenCalledTimes(1);
        }
    });
    it("binds exact parent evidence while allowing a newer Core status", async () => {
        responses();
        await expect(getWorkerActivationRuntimeInterfacePrerequisite({ ...parentAdmission, evaluatedAt: parentAdmission.validUntil, lifecycle: "expired" })).resolves.not.toBeNull();
        vi.resetAllMocks();
        responses();
        await expect(getWorkerActivationRuntimeInterfacePrerequisite({ ...parentAdmission, exactRecord: { ...inventoryResult.record.worker_activation_runtime_plan_review, subject_fingerprint: { ...inventoryResult.record.subject_fingerprint, value: "b".repeat(64) } } })).rejects.toThrow();
        expect(atlas.get).toHaveBeenCalledTimes(1);
    });
    it("rejects invalid request paths before network access", async () => {
        await expect(getWorkerActivationRuntimeInterfacePrerequisite({ ...parentAdmission, candidateId: "../other" })).rejects.toThrow();
        expect(atlas.get).not.toHaveBeenCalled();
    });
});

describe("v0.57 immutable evidence boundary", () => {
    beforeEach(() => vi.resetAllMocks());
    it("rejects changed immutable list/item evidence even with an unchanged record fingerprint", async () => {
        responses(inventoryCollection, { ...inventoryResult, record: { ...inventoryResult.record, subject_fingerprint: { ...inventoryResult.record.subject_fingerprint, value: "b".repeat(64) } } });
        await expect(getWorkerActivationRuntimeInterfacePrerequisite(parentAdmission)).rejects.toThrow(/unavailable/);
    });
    it("accepts reordered object keys without rewriting lineage", async () => {
        const result = { ...inventoryResult, record: Object.fromEntries(Object.entries(inventoryResult.record).reverse()) };
        responses(inventoryCollection, result);
        expect(await getWorkerActivationRuntimeInterfacePrerequisite(parentAdmission)).toMatchObject({ lineage: { record: inventoryResult.record.worker_activation_runtime_plan_review, status: inventoryResult.record.worker_activation_runtime_plan_review_status } });
    });
    it("rejects oversized models before exposing lineage", async () => {
        responses({ ...inventoryCollection, padding: "x".repeat(192 * 1024) });
        await expect(getWorkerActivationRuntimeInterfacePrerequisite(parentAdmission)).rejects.toThrow(/unavailable/);
        expect(atlas.get).toHaveBeenCalledTimes(1);
    });
    // Give every key/field pair its own timeout while retaining the full hostile matrix.
    describe.each(["worker_activation_runtime_plan_review", "worker_activation_runtime_plan_review_status"] as const)("nested v0.56 authority in %s", (field) => {
        it.each(CLOSED_RUNTIME_AUTHORITY)("rejects elevated %s", async (key) => {
            // Copy the mutated path only; the reader does not mutate shared lineage.
            const result = {
                ...inventoryResult,
                record: {
                    ...inventoryResult.record,
                    [field]: { ...inventoryResult.record[field], [key]: true },
                },
            };
            responses(inventoryCollection, result);
            await expect(getWorkerActivationRuntimeInterfacePrerequisite(parentAdmission)).rejects.toThrow();
        });
    });
    it("rejects mismatched admission status fingerprints and IDs", async () => {
        for (const change of [
            { runtime_plan_review_record_fingerprint: { ...inventoryResult.record.worker_activation_runtime_plan_review_status.runtime_plan_review_record_fingerprint, value: "b".repeat(64) } },
            { runtime_plan_review_id: "00000000-0000-5000-8000-000000000058" },
        ]) {
            vi.resetAllMocks();
            const result = structuredClone(inventoryResult);
            Object.assign(result.record.worker_activation_runtime_plan_review_status, change);
            responses(inventoryCollection, result);
            await expect(getWorkerActivationRuntimeInterfacePrerequisite(parentAdmission)).rejects.toThrow();
        }
    });
});

describe("v0.57 envelope and scope binding", () => {
    beforeEach(() => vi.resetAllMocks());
    it.each(["record", "status", "result"] as const)("rejects absent or false plan markers in %s", async (section) => {
        for (const marker of [undefined, false, 1, "true"]) {
            vi.resetAllMocks();
            const result = structuredClone(inventoryResult);
            Object.assign(section === "result" ? result : result[section], { worker_activation_runtime_interface_prerequisite_recorded: marker });
            responses(inventoryCollection, result);
            await expect(getWorkerActivationRuntimeInterfacePrerequisite(parentAdmission)).rejects.toThrow();
        }
    });
    it("returns missing for a different exact admission, without selecting the latest plan", async () => {
        responses();
        expect(await getWorkerActivationRuntimeInterfacePrerequisite({ ...parentAdmission, runtimePlanReviewId: "00000000-0000-5000-8000-000000000058" })).toBeNull();
        expect(atlas.get).toHaveBeenCalledTimes(1);
    });
    it("rejects unknown design fields and oversized item responses", async () => {
        responses(inventoryCollection, { ...inventoryResult, record: { ...inventoryResult.record, profile: "caller-defined" } });
        await expect(getWorkerActivationRuntimeInterfacePrerequisite(parentAdmission)).rejects.toThrow();
        vi.resetAllMocks();
        responses(inventoryCollection, { ...inventoryResult, padding: "x".repeat(192 * 1024) });
        await expect(getWorkerActivationRuntimeInterfacePrerequisite(parentAdmission)).rejects.toThrow();
    });
});

describe("v0.57 fixed interface prerequisite inventory", () => {
    beforeEach(() => vi.resetAllMocks());
    it.each([
        { profile: "approved" }, { inventory: [] },
        { inventory: [...inventoryResult.record.inventory].reverse() },
        { inventory: [...inventoryResult.record.inventory, "runtime_ready"] },
        { runtime_admission_id: "00000000-0000-5000-8000-000000000058" },
        { worker_activation_runtime_interface_prerequisite_recorded: false },
    ])("rejects altered listed and item evidence: %j", async (change) => {
        const record = { ...inventoryResult.record, ...change };
        responses({ ...inventoryCollection, items: [record] }, { ...inventoryResult, record });
        await expect(getWorkerActivationRuntimeInterfacePrerequisite(parentAdmission)).rejects.toThrow();
        expect(atlas.get).toHaveBeenCalledTimes(1);
    });
});

describe("v0.57 exact inventory and durable review status", () => {
    beforeEach(() => vi.resetAllMocks());
    it.each(inventoryResult.record.inventory.map((_, index) => index))("rejects altered owner/proof and extra fields at row %s", async (index) => {
        for (const change of [{ owner: "agent_authority" + "_forged" }, { required_proof: "already_satisfied" }, { satisfied: true }, { blocker: "worker_started" }]) {
            vi.resetAllMocks();
            const record = structuredClone(inventoryResult.record);
            Object.assign(record.inventory[index], change);
            responses({ ...inventoryCollection, items: [record] });
            await expect(getWorkerActivationRuntimeInterfacePrerequisite(parentAdmission)).rejects.toThrow();
            expect(atlas.get).toHaveBeenCalledTimes(1);
        }
    });
    it("accepts reordered inventory object keys in current status", async () => {
        const status = { ...inventoryResult.status, inventory: inventoryResult.status.inventory.map((entry) => Object.fromEntries(Object.entries(entry).reverse())) };
        responses(inventoryCollection, { ...inventoryResult, status });
        await expect(getWorkerActivationRuntimeInterfacePrerequisite(parentAdmission)).resolves.not.toBeNull();
    });
    it("rejects a later item-GET projection substituted for stable recorded-at review status", async () => {
        const record = structuredClone(inventoryResult.record);
        record.worker_activation_runtime_plan_review_status.evaluated_at = new Date(Date.parse(record.recorded_at) + 1000).toISOString().replace(".000Z", "Z");
        record.recorded_at = record.worker_activation_runtime_plan_review_status.evaluated_at;
        responses({ ...inventoryCollection, items: [record] });
        await expect(getWorkerActivationRuntimeInterfacePrerequisite(parentAdmission)).rejects.toThrow();
        expect(atlas.get).toHaveBeenCalledTimes(1);
    });
    it.each(["worker_activation_runtime_plan_recorded", "worker_activation_runtime_plan_review_recorded", "worker_activation_runtime_interface_prerequisite_recorded"])("requires strict %s in every envelope", async (marker) => {
        for (const section of ["record", "status", "result"] as const) {
            for (const value of [undefined, false, 1, "true"]) {
                vi.resetAllMocks();
                const result = structuredClone(inventoryResult);
                Object.assign(section === "result" ? result : result[section], { [marker]: value });
                responses(inventoryCollection, result);
                await expect(getWorkerActivationRuntimeInterfacePrerequisite(parentAdmission)).rejects.toThrow();
            }
        }
    });
});


it("displays complete authoritative Core evidence with distinct historical fingerprint domains", async () => {
    vi.resetAllMocks();
    const record = coreGolden.result.record;
    const parent = record.worker_activation_runtime_plan_review;
    const closed = Object.fromEntries(CLOSED_RUNTIME_AUTHORITY.map((key) => [key, parent[key as keyof typeof parent]]));
    const review = parseWorkerActivationRuntimePlanReview({
        ...closed, evidence_only: true, reference_only: true, payload_bytes: 0,
        schema: "worker-activation-runtime-plan-review-result-v1", exact_duplicate: false,
        worker_activation_runtime_plan_recorded: true, worker_activation_runtime_plan_review_recorded: true,
        record: parent, status: record.worker_activation_runtime_plan_review_status,
    }, parent.candidate_record_id, parent.operator_id);
    responses({ ...coreGolden.collection, items: [record] }, coreGolden.result);
    const evidence = await getWorkerActivationRuntimeInterfacePrerequisite(review);
    expect(evidence?.exactRecord).toEqual(record);
    expect(evidence?.inventory).toEqual(record.inventory);
    expect(evidence?.lineage).toEqual({ record: parent, status: record.worker_activation_runtime_plan_review_status });
});
