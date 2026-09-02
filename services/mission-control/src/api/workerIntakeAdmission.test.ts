import { beforeEach, describe, expect, it, vi } from "vitest";

import { atlas } from "./atlas";
import { getWorkerIntakeAdmission, listWorkerIntakeAdmissions, parseWorkerIntakeAdmissionCollection, parseWorkerIntakeAdmissionResult } from "./workerIntakeAdmission";
import { workerIntakeAdmissionCollectionFixture } from "../test/workerIntakeAdmission";

vi.mock("./atlas", () => ({ atlas: { get: vi.fn() } }));

const fp = { algorithm: "sha256", canonicalization: "atlas-jcs-nfc-v1", value: "a".repeat(64) } as const;
const authority = { evidence_only: true, live_enqueue_allowed: false, dequeue_allowed: false, queue_polling_allowed: false, worker_contact_allowed: false, worker_start_allowed: false, execution_start_allowed: false, runner_binding_allowed: false, dispatch_allowed: false, retry_allowed: false, resend_allowed: false, agent_invocation_allowed: false, workflow_start_allowed: false, docker_execution_allowed: false, podman_execution_allowed: false, shell_execution_allowed: false, process_execution_allowed: false, provider_mutation_allowed: false, repository_mutation_allowed: false, in_guest_mutation_allowed: false, installation_allowed: false, deployment_allowed: false, rollback_allowed: false, replay_bypass_allowed: false } as const;
const blocked = { schema: "worker-intake-admission-result-v1", ok: false, admission: null, error: { schema: "worker-intake-admission-error-v1", error_code: "not_found", message: "worker intake admission request could not be completed", retryable: false, correlation_fingerprint: fp, redacted: true, ...authority }, correlation_fingerprint: fp, ...authority };

describe("worker intake admission API", () => {
    beforeEach(() => { vi.resetAllMocks(); vi.mocked(atlas.get).mockResolvedValueOnce({ data: workerIntakeAdmissionCollectionFixture }).mockResolvedValue({ data: blocked }); });

    it("uses only guarded list/get endpoints", async () => {
        await listWorkerIntakeAdmissions("candidate/id");
        await getWorkerIntakeAdmission("candidate/id", "admission/id");
        expect(atlas.get).toHaveBeenNthCalledWith(1, "/installation/candidate-records/candidate%2Fid/worker-intake-admissions", { withCredentials: true });
        expect(atlas.get).toHaveBeenNthCalledWith(2, "/installation/candidate-records/candidate%2Fid/worker-intake-admissions/admission%2Fid", { withCredentials: true });
    });

    it("parses redacted evidence and rejects effect authority", () => {
        expect(parseWorkerIntakeAdmissionCollection(workerIntakeAdmissionCollectionFixture).count).toBe(1);
        expect(parseWorkerIntakeAdmissionResult(blocked).error?.redacted).toBe(true);
        expect(() => parseWorkerIntakeAdmissionResult({ ...blocked, live_enqueue_allowed: true })).toThrow();
        expect(() => parseWorkerIntakeAdmissionCollection({ ...workerIntakeAdmissionCollectionFixture, count: 2 })).toThrow();
    });
});
