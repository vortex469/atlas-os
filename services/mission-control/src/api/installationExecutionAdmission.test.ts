import { beforeEach, describe, expect, it, vi } from "vitest";

import { atlas } from "./atlas";
import { createInstallationExecutionAdmission, getInstallationExecutionAdmission, listInstallationExecutionAdmissions, parseInstallationExecutionAdmissionCollection, parseInstallationExecutionAdmissionResult } from "./installationExecutionAdmission";
import { admissionResultFixture } from "../test/installationExecutionAdmission";
import type { InstallationExecutionAdmissionCreateV1 } from "../types/installationExecutionAdmission";

vi.mock("./atlas", () => ({ atlas: { get: vi.fn(), post: vi.fn() } }));

const body: InstallationExecutionAdmissionCreateV1 = {
    schema: "installation-execution-admission-create-v1",
    permission_grant_id: admissionResultFixture.admission!.linkage.v035_grant_id,
    permission_grant_fingerprint: admissionResultFixture.admission!.linkage.v035_grant_fingerprint,
    grant_valid_until: "2026-08-27T12:00:30Z",
    requested_scope: "future_installation_runner_consideration_only",
    runner_eligibility_claim: "evidence_chain_only_no_runner_selected",
    execution_authorized: false, installation_allowed: false,
    dispatch_allowed: false, worker_allowed: false,
    mutation_allowed: false, replay_allowed: false,
};

const collection = {
    admissions: [admissionResultFixture], evidence_only: true,
    execution_start_allowed: false, runner_binding_allowed: false,
    execution_authorized: false, installation_allowed: false,
    dispatch_allowed: false, mutation_allowed: false, replay_allowed: false,
} as const;

describe("installation execution admission API", () => {
    beforeEach(() => vi.resetAllMocks());

    it("uses only guarded create/list/get calls", async () => {
        vi.mocked(atlas.get).mockResolvedValueOnce({ data: collection }).mockResolvedValueOnce({ data: admissionResultFixture });
        vi.mocked(atlas.post).mockResolvedValue({ data: admissionResultFixture });
        await listInstallationExecutionAdmissions("candidate/id");
        await getInstallationExecutionAdmission("candidate/id", "admission/id");
        await createInstallationExecutionAdmission("candidate/id", body, "csrf", "stable-key");
        expect(atlas.get).toHaveBeenNthCalledWith(1, "/installation/candidate-records/candidate%2Fid/execution-admissions", { withCredentials: true });
        expect(atlas.get).toHaveBeenNthCalledWith(2, "/installation/candidate-records/candidate%2Fid/execution-admissions/admission%2Fid", { withCredentials: true });
        expect(atlas.post).toHaveBeenCalledWith("/installation/candidate-records/candidate%2Fid/execution-admissions", body, { withCredentials: true, headers: { "X-Atlas-CSRF-Token": "csrf", "Idempotency-Key": "stable-key" } });
    });

    it("strictly parses admission-gated evidence", () => {
        expect(parseInstallationExecutionAdmissionResult(admissionResultFixture).admission?.readiness).toBe("admission_gated");
        expect(parseInstallationExecutionAdmissionCollection(collection).admissions).toHaveLength(1);
        expect(() => parseInstallationExecutionAdmissionResult({ ...admissionResultFixture, execute: true })).toThrow();
        expect(() => parseInstallationExecutionAdmissionResult({ ...admissionResultFixture, admission: { ...admissionResultFixture.admission!, readiness: "ready" } })).toThrow();
        expect(() => parseInstallationExecutionAdmissionResult({ ...admissionResultFixture, admission: { ...admissionResultFixture.admission!, execution_start_allowed: true } })).toThrow();
        expect(() => parseInstallationExecutionAdmissionCollection({ ...collection, runner_binding_allowed: true })).toThrow();
    });

    it("rejects invalid linkage, blocker ordering, expiry, and redaction", () => {
        expect(() => parseInstallationExecutionAdmissionResult({ ...admissionResultFixture, admission: { ...admissionResultFixture.admission!, linkage: { ...admissionResultFixture.admission!.linkage, v035_grant_fingerprint: { ...admissionResultFixture.admission!.linkage.v035_grant_fingerprint, value: "secret" } } } })).toThrow();
        expect(() => parseInstallationExecutionAdmissionResult({ ...admissionResultFixture, admission: { ...admissionResultFixture.admission!, blockers: ["execution_start_boundary_not_defined", "runner_binding_not_defined"] } })).toThrow();
        expect(() => parseInstallationExecutionAdmissionResult({ ...admissionResultFixture, admission: { ...admissionResultFixture.admission!, valid_until: admissionResultFixture.admission!.recorded_at } })).toThrow();
        const error = { disposition: "rejected", admission: null, status: null, audit_evidence: null, error: { schema: "installation-execution-admission-error-v1", error_code: "not_found", safe_message: "Installation execution admission evidence could not be recorded.", blocker_codes: [], correlation_id: "admission-error-1", redacted: true, retryable: false, evidence_only: true, execution_authorized: false, installation_allowed: false, mutation_allowed: false, replay_allowed: false }, evidence_only: true, execution_authorized: false, installation_allowed: false, dispatch_allowed: false, agent_invocation_allowed: false, worker_allowed: false, workflow_allowed: false, mutation_allowed: false, deployment_allowed: false, rollback_allowed: false, retry_allowed: false, replay_allowed: false };
        expect(parseInstallationExecutionAdmissionResult(error).error?.redacted).toBe(true);
        expect(() => parseInstallationExecutionAdmissionResult({ ...error, error: { ...error.error, safe_message: "secret /internal/path" } })).toThrow();
    });
});
