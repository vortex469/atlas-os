import { beforeEach, describe, expect, it, vi } from "vitest";

import { atlas } from "./atlas";
import { getInstallationReadinessReview, parseInstallationReadinessReview } from "./installationReadinessReview";
import { blockedFixture, readinessGatedFixture } from "../test/installationReadinessReview";

vi.mock("./atlas", () => ({ atlas: { get: vi.fn(), post: vi.fn(), put: vi.fn(), patch: vi.fn(), delete: vi.fn() } }));

describe("installation readiness review API", () => {
    beforeEach(() => vi.resetAllMocks());

    it("strictly parses only the closed P3 response", () => {
        expect(parseInstallationReadinessReview(readinessGatedFixture)).toEqual(readinessGatedFixture);
        expect(parseInstallationReadinessReview(blockedFixture)).toEqual(blockedFixture);
        expect(() => parseInstallationReadinessReview({ ...readinessGatedFixture, credential: "secret" })).toThrow(/invalid/i);
        expect(() => parseInstallationReadinessReview({ ...readinessGatedFixture, review: { ...readinessGatedFixture.review, installation_allowed: true } })).toThrow(/invalid/i);
        expect(() => parseInstallationReadinessReview({ ...readinessGatedFixture, review: { ...readinessGatedFixture.review, evidence: [...readinessGatedFixture.review.evidence].reverse() } })).toThrow(/invalid/i);
        expect(() => parseInstallationReadinessReview({ ...readinessGatedFixture, review: { ...readinessGatedFixture.review, blockers: ["execution_admission_not_defined", "stale_evidence"] } })).toThrow(/invalid/i);
        expect(() => parseInstallationReadinessReview({ ...readinessGatedFixture, review: { ...readinessGatedFixture.review, linkage: { ...readinessGatedFixture.review.linkage, endpoint: "https://agent.invalid" } } })).toThrow(/invalid/i);
    });

    it("uses only the exact credentialed Core GET", async () => {
        vi.mocked(atlas.get).mockResolvedValue({ data: readinessGatedFixture });
        await getInstallationReadinessReview("record/id");
        expect(atlas.get).toHaveBeenCalledWith(
            "/installation/candidate-records/record%2Fid/readiness-review",
            { withCredentials: true },
        );
        expect(atlas.post).not.toHaveBeenCalled();
        expect(atlas.put).not.toHaveBeenCalled();
        expect(atlas.patch).not.toHaveBeenCalled();
        expect(atlas.delete).not.toHaveBeenCalled();
    });
});
