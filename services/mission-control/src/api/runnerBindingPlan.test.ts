import { beforeEach, describe, expect, it, vi } from "vitest";

import { atlas } from "./atlas";
import { createRunnerBindingPlan, getRunnerBindingPlan, listRunnerBindingPlans, parseRunnerBindingPlanCollection, parseRunnerBindingPlanResult } from "./runnerBindingPlan";
import { runnerBindingPlanResultFixture } from "../test/runnerBindingPlan";
import type { RunnerBindingPlanCreateV1 } from "../types/runnerBindingPlan";

vi.mock("./atlas", () => ({ atlas: { get: vi.fn(), post: vi.fn() } }));
const plan = runnerBindingPlanResultFixture.plan!;
const body: RunnerBindingPlanCreateV1 = { schema: "runner-binding-plan-create-v1", admission_id: plan.linkage.execution_admission_id, admission_fingerprint: plan.linkage.execution_admission_fingerprint, admission_valid_until: plan.valid_until, runner_reference_id: plan.runner_reference.runner_reference_id, runner_reference_fingerprint: plan.runner_reference.reference_fingerprint, limits_fingerprint: plan.limits.limits_fingerprint, requested_scope: "installation_runner_binding_plan_only", evidence_only: true, runner_binding_allowed: false, execution_authorized: false, worker_start_allowed: false, dispatch_allowed: false, replay_allowed: false };
const collection = { schema: "runner-binding-plan-collection-v1", plans: [runnerBindingPlanResultFixture], evidence_only: true, execution_authorized: false, mutation_allowed: false };

describe("runner binding plan API", () => {
    beforeEach(() => {
        vi.resetAllMocks();
        vi.mocked(atlas.get)
            .mockResolvedValueOnce({ data: collection })
            .mockResolvedValueOnce({ data: runnerBindingPlanResultFixture });
        vi.mocked(atlas.post).mockResolvedValue({ data: runnerBindingPlanResultFixture });
    });
    it("uses only exact guarded create/list/get requests", async () => {
        await listRunnerBindingPlans("candidate/id"); await getRunnerBindingPlan("candidate/id", "plan/id"); await createRunnerBindingPlan("candidate/id", body, "csrf", "stable-key");
        expect(atlas.get).toHaveBeenNthCalledWith(1, "/installation/candidate-records/candidate%2Fid/runner-binding-plans", { withCredentials: true });
        expect(atlas.get).toHaveBeenNthCalledWith(2, "/installation/candidate-records/candidate%2Fid/runner-binding-plans/plan%2Fid", { withCredentials: true });
        expect(atlas.post).toHaveBeenCalledWith("/installation/candidate-records/candidate%2Fid/runner-binding-plans", body, { withCredentials: true, headers: { "X-Atlas-CSRF-Token": "csrf", "Idempotency-Key": "stable-key" } });
    });
    it("strictly parses closed plans, limits, authority, and collections", () => {
        expect(parseRunnerBindingPlanResult(runnerBindingPlanResultFixture).plan?.eligibility).toBe("binding_planned");
        expect(parseRunnerBindingPlanCollection(collection).plans).toHaveLength(1);
        expect(() => parseRunnerBindingPlanResult({ ...runnerBindingPlanResultFixture, bind: true })).toThrow();
        expect(() => parseRunnerBindingPlanResult({ ...runnerBindingPlanResultFixture, runner_binding_allowed: true })).toThrow();
        expect(() => parseRunnerBindingPlanResult({ ...runnerBindingPlanResultFixture, plan: { ...plan, eligibility: "bound" } })).toThrow();
        expect(() => parseRunnerBindingPlanResult({ ...runnerBindingPlanResultFixture, plan: { ...plan, linkage: { ...plan.linkage, execution_admission_linkage: { ...plan.linkage.execution_admission_linkage, unexpected: "secret" } } } })).toThrow();
        expect(() => parseRunnerBindingPlanResult({ ...runnerBindingPlanResultFixture, plan: { ...plan, limits: { ...plan.limits, network: { ...plan.limits.network, egress_allowed: true } } } })).toThrow();
        expect(() => parseRunnerBindingPlanCollection({ ...collection, mutation_allowed: true })).toThrow();
    });
    it("accepts only the fixed redacted error", () => {
        const error = { schema: "runner-binding-plan-result-v1", disposition: "blocked", plan: null, status: null, audit_evidence: null, error: { schema: "runner-binding-plan-redacted-error-v1", error_code: "not_found", message: "runner binding plan request could not be completed", correlation_fingerprint: plan.plan_fingerprint, retryable: false, redacted: true, evidence_only: true, runner_binding_allowed: false, execution_authorized: false, mutation_allowed: false, replay_allowed: false }, evidence_only: true, runner_registration_allowed: false, runner_contact_allowed: false, runner_reservation_allowed: false, runner_binding_allowed: false, runner_bound: false, execution_start_allowed: false, execution_authorized: false, installation_allowed: false, dispatch_allowed: false, agent_invocation_allowed: false, worker_allowed: false, workflow_allowed: false, mutation_allowed: false, deployment_allowed: false, rollback_allowed: false, retry_allowed: false, replay_allowed: false };
        expect(parseRunnerBindingPlanResult(error).error?.redacted).toBe(true);
        expect(() => parseRunnerBindingPlanResult({ ...error, error: { ...error.error, message: "secret /internal/path 10.0.0.1" } })).toThrow();
    });
});
