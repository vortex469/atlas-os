import { beforeEach, describe, expect, it, vi } from "vitest";
import { atlas } from "./atlas";
import { getControlledWorkerQueueReceipt, parseControlledWorkerQueueReceipt } from "./controlledWorkerQueueReceipt";
import fixture from "../test/controlledWorkerQueueReceipt";
import { CLOSED_QUEUE_AUTHORITY } from "../types/controlledWorkerQueueReceipt";

vi.mock("./atlas", () => ({ atlas: { get: vi.fn() } }));
const { candidate_record_id: candidate, admission_id: admission, operator_id: operator } = fixture.record;
const parse = (value: unknown) => parseControlledWorkerQueueReceipt(value, candidate, admission, operator);

describe("v0.52 Core receipt reader", () => {
    beforeEach(() => vi.resetAllMocks());
    it("reads the guarded detail endpoint with credentials", async () => {
        vi.mocked(atlas.get).mockResolvedValue({ data: fixture });
        expect(await getControlledWorkerQueueReceipt(candidate, admission, operator)).toMatchObject({ lifecycle: "active", reservationBeforeEffect: true });
        expect(atlas.get).toHaveBeenCalledWith(`/installation/candidate-records/${candidate}/controlled-worker-queue-claim-lease-acknowledgements/${admission}`, { withCredentials: true });
    });
    it("uses Core status, including passive expiry", () => {
        const value = structuredClone(fixture);
        value.status.lifecycle = "expired";
        value.status.evaluated_at = value.status.valid_until;
        expect(parse(value).lifecycle).toBe("expired");
    });
    it.each(CLOSED_QUEUE_AUTHORITY)("rejects missing or elevated authority: %s", (field) => {
        for (const section of ["record", "status", "result"] as const) {
            for (const invalid of [true, undefined]) {
                const value = structuredClone(fixture);
                const target = section === "result" ? value : value[section];
                Object.assign(target, { [field]: invalid });
                expect(() => parse(value)).toThrow(/unavailable/);
            }
        }
    });
    it.each(["record", "status", "controlled_worker_queue_claim_lease_acknowledgement_admission", "controlled_worker_queue_claim_lease_acknowledgement_admission_status"])("rejects cross-owner and cross-candidate %s", (section) => {
        for (const field of ["operator_id", "candidate_record_id", "admission_id"]) {
            const value = structuredClone(fixture);
            const target = section === "record" || section === "status" ? value[section] : (value.record as unknown as Record<string, object>)[section];
            Object.assign(target, { [field]: "other" });
            expect(() => parse(value)).toThrow(/unavailable/);
        }
    });
    it("rejects malformed facts, missing receipts, and broken fingerprints", () => {
        for (const change of [
            { controlled_queue_claim_recorded: false }, { receipt_state: "blocked" }, { blockers: [] },
            { recorded_at: "2026-02-30T12:00:44Z" }, { receipt_record_fingerprint: {} },
            { adapter_receipt: { ...fixture.record.adapter_receipt, reservation_before_effect: false } },
            { claim_receipt_fingerprint: { ...fixture.record.claim_receipt_fingerprint, value: "b".repeat(64) } },
        ]) expect(() => parse({ ...fixture, record: { ...fixture.record, ...change } })).toThrow(/unavailable/);
        expect(() => parse({ ...fixture, outcome: "indeterminate" })).toThrow(/unavailable/);
    });
    it("never renders raw unknown fields or propagates sensitive response material", () => {
        const result = parse({ ...fixture, record: { ...fixture.record, claim_token: "secret", endpoint: "internal" } });
        expect(JSON.stringify(result)).not.toMatch(/secret|internal|claim_token":"/);
    });
    it("rejects invalid paths before requesting Core", async () => {
        await expect(getControlledWorkerQueueReceipt("../other", admission, operator)).rejects.toThrow();
        expect(atlas.get).not.toHaveBeenCalled();
    });
});
