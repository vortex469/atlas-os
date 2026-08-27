import { beforeEach, describe, expect, it, vi } from "vitest";

import { atlas } from "./atlas";
import {
    getInstallationApprovalIntent,
    listInstallationApprovalIntents,
    parseInstallationApprovalIntent,
    recordInstallationApprovalIntent,
} from "./installationApprovalIntent";

vi.mock("./atlas", () => ({ atlas: { get: vi.fn(), post: vi.fn() } }));

const fingerprint = "a".repeat(64);
const intent = {
    schema: "installation-approval-intent-v1",
    approval_intent_id: "00000000-0000-4000-8000-000000000001",
    operator_id: "operator-a",
    recorded_at: "2026-08-27T12:00:00Z",
    approved_subject: {
        candidate_record_id: "00000000-0000-4000-8000-000000000002",
        candidate_envelope_fingerprint: fingerprint,
        admission_fingerprint: "b".repeat(64),
        candidate_record_fingerprint: "c".repeat(64),
    },
    statement: "operator_approved_exact_non_executable_candidate",
    intent_fingerprint: "d".repeat(64),
};

describe("installation approval intent API", () => {
    beforeEach(() => vi.resetAllMocks());

    it("parses the exact closed evidence shape and rejects leaks or altered statements", () => {
        expect(parseInstallationApprovalIntent(intent)).toEqual(intent);
        expect(() => parseInstallationApprovalIntent({ ...intent, provider: "secret-provider" })).toThrow(/invalid/i);
        expect(() => parseInstallationApprovalIntent({ ...intent, statement: "approved" })).toThrow(/invalid/i);
        expect(() => parseInstallationApprovalIntent({ ...intent, recorded_at: "2026-08-27T12:00:00.123Z" })).toThrow(/invalid/i);
        expect(() => parseInstallationApprovalIntent({ ...intent, approved_subject: { ...intent.approved_subject, address: "10.0.0.1" } })).toThrow(/invalid/i);
    });

    it("uses only guarded list, get, and explicit append calls", async () => {
        vi.mocked(atlas.get).mockResolvedValueOnce({ data: { approval_intents: [intent] } }).mockResolvedValueOnce({ data: intent });
        vi.mocked(atlas.post).mockResolvedValueOnce({ data: intent });
        await expect(listInstallationApprovalIntents()).resolves.toEqual([intent]);
        await getInstallationApprovalIntent("intent/id");
        await recordInstallationApprovalIntent(intent.approved_subject.candidate_record_id, "csrf", "key");
        expect(atlas.get).toHaveBeenNthCalledWith(1, "/installation/candidate-approval-intents", { withCredentials: true });
        expect(atlas.get).toHaveBeenNthCalledWith(2, "/installation/candidate-approval-intents/intent%2Fid", { withCredentials: true });
        expect(atlas.post).toHaveBeenCalledWith("/installation/candidate-approval-intents", {
            candidate_record_id: intent.approved_subject.candidate_record_id,
        }, { withCredentials: true, headers: { "X-Atlas-CSRF-Token": "csrf", "Idempotency-Key": "key" } });
        const body = vi.mocked(atlas.post).mock.calls[0][1] as Record<string, unknown>;
        expect(Object.keys(body)).toEqual(["candidate_record_id"]);
    });
});
