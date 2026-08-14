import { render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { restoreOperatorSession } from "../api/operatorAuth";
import { useOperatorSession } from "./operatorSessionContext";
import { OperatorSessionProvider } from "./useOperatorSession";

vi.mock("../api/operatorAuth", () => ({
    loginOperator: vi.fn(),
    logoutOperator: vi.fn(),
    restoreOperatorSession: vi.fn(),
}));

function Probe() {
    const session = useOperatorSession();
    return <p>{session.loading ? "loading" : session.authenticated ? `${session.principal?.operator_id}:${session.csrfToken}` : session.error ?? "anonymous"}</p>;
}

describe("OperatorSessionProvider", () => {
    it("restores sanitized principal and rotated CSRF in memory", async () => {
        vi.mocked(restoreOperatorSession).mockResolvedValue({
            session: {
                authenticated: true,
                principal: {
                    operator_id: "kenny",
                    authenticated_at: "2026-08-14T00:00:00Z",
                    permissions: ["operational_intent:create"],
                    auth_method: "core_session",
                },
                expires_at: "2026-08-14T01:00:00Z",
            },
            csrfToken: "rotated-csrf",
        });
        render(<OperatorSessionProvider><Probe /></OperatorSessionProvider>);
        expect(await screen.findByText("kenny:rotated-csrf")).toBeInTheDocument();
        expect(localStorage.length).toBe(0);
        expect(sessionStorage.length).toBe(0);
    });

    it("treats an expired session as unauthenticated", async () => {
        vi.mocked(restoreOperatorSession).mockRejectedValue({ isAxiosError: true, response: { status: 401 } });
        render(<OperatorSessionProvider><Probe /></OperatorSessionProvider>);
        await waitFor(() => expect(screen.getByText("anonymous")).toBeInTheDocument());
    });
});
