import { beforeEach, describe, expect, it, vi } from "vitest";

import { atlas } from "./atlas";
import {
    assessInstallationAdmission,
    listProspectiveInstallationDestinations,
    selectProspectiveInstallationDestination,
} from "./installationDestination";

vi.mock("./atlas", () => ({ atlas: { get: vi.fn(), post: vi.fn() } }));

describe("installation destination API", () => {
    beforeEach(() => vi.resetAllMocks());

    it("loads only the authenticated sanitized destination collection", async () => {
        const destinations = [{ resource_id: "101" }];
        vi.mocked(atlas.get).mockResolvedValueOnce({ data: { destinations } });
        await expect(listProspectiveInstallationDestinations()).resolves.toBe(destinations);
        expect(atlas.get).toHaveBeenCalledWith("/installation/destinations", { withCredentials: true });
    });

    it("uses session, CSRF, and bounded idempotency headers for selection", async () => {
        const selection = { selection_id: "selection" };
        vi.mocked(atlas.post).mockResolvedValueOnce({ data: selection });
        await expect(selectProspectiveInstallationDestination(
            { resource_id: "101", enumeration_token: "a".repeat(64) }, "csrf", "mission-control-key",
        )).resolves.toBe(selection);
        expect(atlas.post).toHaveBeenCalledWith(
            "/installation/destination-selections",
            { resource_id: "101", enumeration_token: "a".repeat(64) },
            { withCredentials: true, headers: { "X-Atlas-CSRF-Token": "csrf", "Idempotency-Key": "mission-control-key" } },
        );
    });

    it("binds an assessment to exact plan and selection identities", async () => {
        vi.mocked(atlas.post).mockResolvedValueOnce({ data: { assessment_status: "blocked" } });
        const request = { item_id: "home-assistant", catalog_entry_id: "d5-home-assistant", plan_fingerprint: "f".repeat(64), selection_id: "selection" };
        await assessInstallationAdmission(request, "csrf", "mission-control-key");
        expect(atlas.post).toHaveBeenCalledWith(
            "/installation/admission-assessments", request,
            { withCredentials: true, headers: { "X-Atlas-CSRF-Token": "csrf", "Idempotency-Key": "mission-control-key" } },
        );
    });
});
