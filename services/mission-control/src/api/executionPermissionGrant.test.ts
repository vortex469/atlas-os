import { beforeEach, describe, expect, it, vi } from "vitest";
import { atlas } from "./atlas";
import { createExecutionPermissionGrant, getExecutionPermissionGrant, listExecutionPermissionGrants, parseExecutionPermissionGrantCollection, parseExecutionPermissionGrantResult } from "./executionPermissionGrant";
import { grantResultFixture } from "../test/executionPermissionGrant";
import { EXECUTION_PERMISSION_CONFIRMATION, type ExecutionPermissionGrantCreateV1 } from "../types/executionPermissionGrant";
import { readinessGatedFixture, uuid4 } from "../test/installationReadinessReview";

vi.mock("./atlas", () => ({ atlas: { get: vi.fn(), post: vi.fn(), put: vi.fn(), patch: vi.fn(), delete: vi.fn() } }));
const collection = { grants: [grantResultFixture], evidence_only: true, execution_authorized: false, installation_allowed: false, mutation_allowed: false, replay_allowed: false };
const body: ExecutionPermissionGrantCreateV1 = { schema: "execution-permission-grant-create-v1", readiness_review_id: readinessGatedFixture.review.review_id, readiness_review_fingerprint: readinessGatedFixture.review.review_fingerprint, review_observed_at: readinessGatedFixture.review.observed_at, confirmation_text: EXECUTION_PERMISSION_CONFIRMATION, permission_scope: "future_execution_admission_consideration_only", execution_admission_granted: false, execution_authorized: false, installation_allowed: false, dispatch_allowed: false, mutation_allowed: false, replay_allowed: false };

describe("execution permission grant API", () => {
    beforeEach(() => vi.resetAllMocks());
    it("strictly parses closed create/read responses", () => {
        expect(parseExecutionPermissionGrantResult(grantResultFixture)).toEqual(grantResultFixture);
        expect(parseExecutionPermissionGrantCollection(collection).grants).toHaveLength(1);
        expect(() => parseExecutionPermissionGrantResult({ ...grantResultFixture, credential: "secret" })).toThrow(/invalid/i);
        expect(() => parseExecutionPermissionGrantResult({ ...grantResultFixture, execution_authorized: true })).toThrow(/invalid/i);
        expect(() => parseExecutionPermissionGrantResult({ ...grantResultFixture, grant: { ...grantResultFixture.grant!, confirmation_text: "yes" } })).toThrow(/invalid/i);
        expect(() => parseExecutionPermissionGrantResult({ ...grantResultFixture, status: { ...grantResultFixture.status!, grant_id: "00000000-0000-4000-8000-000000000002" } })).toThrow(/invalid/i);
    });
    it("uses only P3 create/list/get with session security", async () => {
        vi.mocked(atlas.get).mockResolvedValueOnce({ data: collection }).mockResolvedValueOnce({ data: grantResultFixture });
        vi.mocked(atlas.post).mockResolvedValue({ data: grantResultFixture });
        await listExecutionPermissionGrants("candidate/id"); await getExecutionPermissionGrant("candidate/id", "grant/id"); await createExecutionPermissionGrant("candidate/id", body, "csrf", "stable-key");
        expect(atlas.get).toHaveBeenNthCalledWith(1, "/installation/candidate-records/candidate%2Fid/execution-permission-grants", { withCredentials: true });
        expect(atlas.get).toHaveBeenNthCalledWith(2, "/installation/candidate-records/candidate%2Fid/execution-permission-grants/grant%2Fid", { withCredentials: true });
        expect(atlas.post).toHaveBeenCalledWith("/installation/candidate-records/candidate%2Fid/execution-permission-grants", body, { withCredentials: true, headers: { "X-Atlas-CSRF-Token": "csrf", "Idempotency-Key": "stable-key" } });
        expect(atlas.put).not.toHaveBeenCalled(); expect(atlas.patch).not.toHaveBeenCalled(); expect(atlas.delete).not.toHaveBeenCalled();
        expect(uuid4).toMatch(/-/);
    });
});
