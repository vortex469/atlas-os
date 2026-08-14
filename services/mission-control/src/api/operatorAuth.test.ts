import { beforeEach, describe, expect, it, vi } from "vitest";

import { atlas } from "./atlas";
import { loginOperator, logoutOperator, restoreOperatorSession } from "./operatorAuth";

vi.mock("./atlas", () => ({ atlas: { get: vi.fn(), post: vi.fn() } }));

const session = {
    authenticated: true as const,
    principal: {
        operator_id: "kenny",
        authenticated_at: "2026-08-14T00:00:00Z",
        permissions: ["operational_intent:create"],
        auth_method: "core_session" as const,
    },
    expires_at: "2026-08-14T01:00:00Z",
};

describe("operator auth API", () => {
    beforeEach(() => vi.resetAllMocks());

    it("logs in with only credentials and captures CSRF", async () => {
        vi.mocked(atlas.post).mockResolvedValue({ data: session, headers: { "x-atlas-csrf-token": "csrf-one" } });
        await expect(loginOperator("kenny", "secret")).resolves.toEqual({ session, csrfToken: "csrf-one" });
        expect(atlas.post).toHaveBeenCalledWith(
            "/operator-auth/login",
            { operator_id: "kenny", password: "secret" },
            { withCredentials: true },
        );
    });

    it("restores the cookie session with rotated CSRF", async () => {
        vi.mocked(atlas.get).mockResolvedValue({ data: session, headers: { "x-atlas-csrf-token": "csrf-two" } });
        await expect(restoreOperatorSession()).resolves.toEqual({ session, csrfToken: "csrf-two" });
        expect(atlas.get).toHaveBeenCalledWith("/operator-auth/session", { withCredentials: true });
    });

    it("logs out with in-memory CSRF and credentials", async () => {
        vi.mocked(atlas.post).mockResolvedValue({ data: { authenticated: false } });
        await logoutOperator("csrf-three");
        expect(atlas.post).toHaveBeenCalledWith(
            "/operator-auth/logout",
            {},
            { withCredentials: true, headers: { "X-Atlas-CSRF-Token": "csrf-three" } },
        );
    });
});
