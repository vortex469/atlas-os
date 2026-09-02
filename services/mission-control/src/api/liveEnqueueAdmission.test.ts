import { beforeEach, describe, expect, it, vi } from "vitest";

import { atlas } from "./atlas";
import { createLiveEnqueueAdmission, getLiveEnqueueAdmission, listLiveEnqueueAdmissions, parseLiveEnqueueAdmissionCollection, parseLiveEnqueueAdmissionCreate, parseLiveEnqueueAdmissionResult } from "./liveEnqueueAdmission";
import { blockedLiveEnqueueAdmissionResultFixture, liveEnqueueAdmissionCollectionFixture, liveEnqueueAdmissionFixture } from "../test/liveEnqueueAdmission";

vi.mock("./atlas", () => ({ atlas: { get: vi.fn(), post: vi.fn() } }));

const create = {
    schema: "live-enqueue-admission-create-v1",
    worker_intake_admission_id: liveEnqueueAdmissionFixture.linkage.worker_intake_admission_id,
    worker_intake_admission_fingerprint: liveEnqueueAdmissionFixture.linkage.worker_intake_admission_fingerprint,
    worker_intake_admission_valid_until: "2099-08-27T12:00:45Z",
    worker_queue_reservation_id: liveEnqueueAdmissionFixture.linkage.queue_reservation_id,
    worker_queue_reservation_fingerprint: liveEnqueueAdmissionFixture.linkage.queue_reservation_fingerprint,
    queue_item_reference_id: liveEnqueueAdmissionFixture.linkage.queue_item_reference_id,
    queue_item_reference_fingerprint: liveEnqueueAdmissionFixture.linkage.queue_item_reference_fingerprint,
    worker_identity_id: liveEnqueueAdmissionFixture.linkage.worker_identity_id,
    worker_identity_fingerprint: liveEnqueueAdmissionFixture.linkage.worker_identity_fingerprint,
    worker_intake_reference_id: liveEnqueueAdmissionFixture.linkage.worker_intake_reference_id,
    worker_intake_reference_fingerprint: liveEnqueueAdmissionFixture.linkage.worker_intake_reference_fingerprint,
    inherited_limits_fingerprint: liveEnqueueAdmissionFixture.inherited_limits.limits_fingerprint,
    requested_scope: "installation_live_enqueue_admission_only",
    evidence_only: true,
    enqueue_operation_defined: false,
    payload_constructed: false,
    payload_serialized: false,
    live_enqueue_allowed: false,
    dequeue_allowed: false,
    worker_start_allowed: false,
    execution_authorized: false,
    replay_allowed: false,
} as const;

describe("live enqueue admission API", () => {
    beforeEach(() => {
        vi.resetAllMocks();
        vi.mocked(atlas.get).mockResolvedValueOnce({ data: liveEnqueueAdmissionCollectionFixture }).mockResolvedValue({ data: blockedLiveEnqueueAdmissionResultFixture });
        vi.mocked(atlas.post).mockResolvedValue({ data: blockedLiveEnqueueAdmissionResultFixture });
    });

    it("uses only guarded create/list/get endpoints", async () => {
        await listLiveEnqueueAdmissions("candidate/id");
        await getLiveEnqueueAdmission("candidate/id", "admission/id");
        await createLiveEnqueueAdmission("candidate/id", create, "csrf", "visible-stable-key");
        expect(atlas.get).toHaveBeenNthCalledWith(1, "/installation/candidate-records/candidate%2Fid/live-enqueue-admissions", { withCredentials: true });
        expect(atlas.get).toHaveBeenNthCalledWith(2, "/installation/candidate-records/candidate%2Fid/live-enqueue-admissions/admission%2Fid", { withCredentials: true });
        expect(atlas.post).toHaveBeenCalledTimes(1);
    });

    it("rejects contrary authority, malformed records, unknown states, excess collections, and sensitive fields", () => {
        expect(parseLiveEnqueueAdmissionCreate(create).requested_scope).toBe("installation_live_enqueue_admission_only");
        expect(parseLiveEnqueueAdmissionCollection(liveEnqueueAdmissionCollectionFixture).count).toBe(1);
        expect(parseLiveEnqueueAdmissionResult(blockedLiveEnqueueAdmissionResultFixture).error?.redacted).toBe(true);
        expect(() => parseLiveEnqueueAdmissionCollection({ ...liveEnqueueAdmissionCollectionFixture, live_enqueue_allowed: true })).toThrow();
        expect(() => parseLiveEnqueueAdmissionCollection({ ...liveEnqueueAdmissionCollectionFixture, items: [{ ...liveEnqueueAdmissionFixture, lifecycle: "enqueued" }] })).toThrow();
        expect(() => parseLiveEnqueueAdmissionResult({ ...blockedLiveEnqueueAdmissionResultFixture, status: { schema: "live-enqueue-admission-status-v1", lifecycle: "leased" } })).toThrow();
        expect(() => parseLiveEnqueueAdmissionCollection({ ...liveEnqueueAdmissionCollectionFixture, items: Array.from({ length: 101 }, () => liveEnqueueAdmissionFixture), count: 101 })).toThrow();
        expect(() => parseLiveEnqueueAdmissionCollection({ ...liveEnqueueAdmissionCollectionFixture, items: [{ ...liveEnqueueAdmissionFixture, endpoint: "https://example.invalid" }] })).toThrow();
    });
});
