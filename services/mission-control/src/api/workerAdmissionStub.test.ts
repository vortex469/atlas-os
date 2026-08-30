import { beforeEach, describe, expect, it, vi } from "vitest";

import { atlas } from "./atlas";
import { createWorkerAdmissionStub, getWorkerAdmissionStub, listWorkerAdmissionStubs, parseWorkerAdmissionStubCollection, parseWorkerAdmissionStubResult } from "./workerAdmissionStub";
import { workerAdmissionStubResultFixture } from "../test/workerAdmissionStub";
import type { WorkerAdmissionStubCreateV1 } from "../types/workerAdmissionStub";

vi.mock("./atlas", () => ({ atlas: { get: vi.fn(), post: vi.fn() } }));
const stub = workerAdmissionStubResultFixture.stub!;
const body: WorkerAdmissionStubCreateV1 = { schema: "worker-admission-stub-create-v1", runner_binding_plan_id: stub.linkage.runner_binding_plan_id, runner_binding_plan_fingerprint: stub.linkage.runner_binding_plan_fingerprint, runner_binding_plan_valid_until: stub.valid_until, worker_reference_id: stub.worker_reference.worker_reference_id, worker_reference_fingerprint: stub.worker_reference.reference_fingerprint, inherited_limits_fingerprint: stub.inherited_limits.limits_fingerprint, requested_scope: "installation_worker_admission_stub_only", evidence_only: true, worker_start_allowed: false, queue_allowed: false, dispatch_allowed: false, execution_authorized: false, replay_allowed: false };
const collection = { schema: "worker-admission-stub-collection-v1", stubs: [workerAdmissionStubResultFixture], evidence_only: true, worker_start_allowed: false, enqueue_allowed: false, execution_authorized: false, mutation_allowed: false } as const;

describe("worker admission stub API", () => {
    beforeEach(() => { vi.resetAllMocks(); });
    it("uses only exact encoded list/get/create routes", async () => {
        vi.mocked(atlas.get).mockResolvedValueOnce({ data: collection }).mockResolvedValueOnce({ data: workerAdmissionStubResultFixture });
        vi.mocked(atlas.post).mockResolvedValue({ data: workerAdmissionStubResultFixture });
        await listWorkerAdmissionStubs("candidate/id"); await getWorkerAdmissionStub("candidate/id", "stub/id"); await createWorkerAdmissionStub("candidate/id", body, "csrf", "stable-visible-key");
        expect(atlas.get).toHaveBeenNthCalledWith(1, "/installation/candidate-records/candidate%2Fid/worker-admission-stubs", { withCredentials: true });
        expect(atlas.get).toHaveBeenNthCalledWith(2, "/installation/candidate-records/candidate%2Fid/worker-admission-stubs/stub%2Fid", { withCredentials: true });
        expect(atlas.post).toHaveBeenCalledTimes(1);
    });
    it("strictly parses closed evidence and rejects authority expansion", () => {
        expect(parseWorkerAdmissionStubResult(workerAdmissionStubResultFixture).stub?.eligibility).toBe("worker_admission_stubbed");
        expect(parseWorkerAdmissionStubCollection(collection).stubs).toHaveLength(1);
        expect(() => parseWorkerAdmissionStubResult({ ...workerAdmissionStubResultFixture, enqueue: true })).toThrow();
        expect(() => parseWorkerAdmissionStubResult({ ...workerAdmissionStubResultFixture, worker_start_allowed: true })).toThrow();
        expect(() => parseWorkerAdmissionStubResult({ ...workerAdmissionStubResultFixture, stub: { ...stub, eligibility: "started" } })).toThrow();
        expect(() => parseWorkerAdmissionStubResult({ ...workerAdmissionStubResultFixture, stub: { ...stub, inherited_limits: { ...stub.inherited_limits, network: { ...stub.inherited_limits.network, egress_allowed: true } } } })).toThrow();
        expect(() => parseWorkerAdmissionStubCollection({ ...collection, mutation_allowed: true })).toThrow();
    });
    it("accepts only sanitized redacted failures", () => {
        const error = { schema: "worker-admission-stub-result-v1", disposition: "blocked", stub: null, status: null, audit_evidence: null, error: { schema: "worker-admission-stub-redacted-error-v1", error_code: "not_found", message: "worker admission stub request could not be completed", correlation_fingerprint: stub.stub_fingerprint, retryable: false, redacted: true, evidence_only: true, worker_start_allowed: false, enqueue_allowed: false, dispatch_allowed: false, execution_authorized: false, mutation_allowed: false, replay_allowed: false }, evidence_only: true, worker_registration_allowed: false, worker_contact_allowed: false, worker_reservation_allowed: false, worker_binding_allowed: false, worker_start_allowed: false, queue_allowed: false, enqueue_allowed: false, dispatch_allowed: false, execution_start_allowed: false, execution_authorized: false, installation_allowed: false, agent_invocation_allowed: false, workflow_allowed: false, mutation_allowed: false, deployment_allowed: false, rollback_allowed: false, retry_allowed: false, replay_allowed: false };
        expect(parseWorkerAdmissionStubResult(error).error?.redacted).toBe(true);
        expect(() => parseWorkerAdmissionStubResult({ ...error, error: { ...error.error, message: "secret /internal/path 10.0.0.1" } })).toThrow();
    });
});
