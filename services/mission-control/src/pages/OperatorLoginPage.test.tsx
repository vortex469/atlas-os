import { act, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { createMemoryRouter, MemoryRouter, Route, RouterProvider, Routes, useLocation } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import { useOperatorSession } from "../hooks/operatorSessionContext";
import { OperatorLoginPage } from "./OperatorLoginPage";

vi.mock("../hooks/operatorSessionContext", () => ({ useOperatorSession: vi.fn() }));

function session(login: (id: string, password: string) => Promise<boolean>, error: string | null = null, authenticated = false) {
    vi.mocked(useOperatorSession).mockReturnValue({
        authenticated,
        principal: null,
        csrfToken: null,
        loading: false,
        error,
        login,
        logout: vi.fn(),
        invalidate: vi.fn(),
    });
}

function Destination() {
    return <><p>Maintenance destination</p><output data-testid="return-context">{JSON.stringify(useLocation().state)}</output></>;
}

function renderPage(state: unknown = { returnTo: "/operations/request" }) {
    render(<MemoryRouter initialEntries={[{ pathname: "/operator/login", state }]}><Routes><Route path="/operator/login" element={<OperatorLoginPage />} /><Route path="/operations/request" element={<Destination />} /></Routes></MemoryRouter>);
}

describe("OperatorLoginPage", () => {
    it("preserves only a valid advisory proposal reference after sign-in", async () => {
        session(vi.fn().mockResolvedValue(true));
        const user = userEvent.setup();
        const proposalId = `discovery-operator-proposal-${"a".repeat(64)}`;
        renderPage({ proposalId, returnTo: "https://example.invalid", resourceId: "999", approved: true });
        expect(screen.getByText(/maintenance will reload the proposal/)).toBeInTheDocument();
        await user.type(screen.getByLabelText("Operator ID"), "kenny");
        await user.type(screen.getByLabelText("Password"), "secret");
        await user.click(screen.getByRole("button", { name: "Sign in" }));
        await screen.findByText("Maintenance destination");
        expect(JSON.parse(screen.getByTestId("return-context").textContent!)).toEqual({ proposalId });
    });

    it.each(["/operator/login", "//example.invalid", "/missing", null, 42])("uses the supported maintenance destination instead of returnTo %s", async (returnTo) => {
        session(vi.fn(), null, true);
        renderPage({ returnTo, proposalId: "../../invalid", resourceId: "999", approved: true });
        await screen.findByText("Maintenance destination");
        expect(screen.getByTestId("return-context")).toHaveTextContent("null");
    });

    it("clears the password and offers retry when the login call unexpectedly rejects", async () => {
        session(vi.fn().mockRejectedValueOnce(new Error("private diagnostic" )).mockResolvedValue(false));
        const user = userEvent.setup();
        renderPage();
        await user.type(screen.getByLabelText("Operator ID"), "kenny");
        await user.type(screen.getByLabelText("Password"), "secret");
        await user.click(screen.getByRole("button", { name: "Sign in" }));
        const alert = await screen.findByRole("alert");
        expect(alert).toHaveTextContent("Sign-in could not be completed.");
        expect(alert).not.toHaveTextContent("Try again");
        expect(screen.getByLabelText("Password")).toHaveValue("");
        expect(screen.getByRole("button", { name: "Sign in" })).toBeEnabled();
        expect(screen.queryByText(/private diagnostic/)).not.toBeInTheDocument();
    });

    it("does not pull the operator back after they leave a pending sign-in", async () => {
        let resolveLogin!: (value: boolean) => void;
        session(vi.fn(() => new Promise<boolean>((resolve) => { resolveLogin = resolve; })));
        const router = createMemoryRouter([
            { path: "/operator/login", element: <OperatorLoginPage /> },
            { path: "/", element: <p>Home destination</p> },
            { path: "/operations/request", element: <Destination /> },
        ], { initialEntries: ["/operator/login"] });
        render(<RouterProvider router={router} />);
        const user = userEvent.setup();
        await user.type(screen.getByLabelText("Operator ID"), "kenny");
        await user.type(screen.getByLabelText("Password"), "secret");
        await user.click(screen.getByRole("button", { name: "Sign in" }));
        await user.click(screen.getByRole("link", { name: "← Mission Control" }));
        await act(async () => resolveLogin(true));
        expect(router.state.location.pathname).toBe("/");
        expect(screen.getByText("Home destination")).toBeInTheDocument();
    });

    it("submits credentials, clears password, and returns to maintenance", async () => {
        const login = vi.fn().mockResolvedValue(true);
        session(login);
        const user = userEvent.setup();
        renderPage();
        await user.type(screen.getByLabelText("Operator ID"), "kenny");
        const password = screen.getByLabelText("Password");
        await user.type(password, "secret");
        await user.click(screen.getByRole("button", { name: "Sign in" }));
        expect(login).toHaveBeenCalledWith("kenny", "secret");
        expect(await screen.findByText("Maintenance destination")).toBeInTheDocument();
        expect(password).toHaveValue("");
        expect(localStorage.length).toBe(0);
        expect(sessionStorage.length).toBe(0);
    });

    it("shows a generic failure and clears password", async () => {
        session(vi.fn().mockResolvedValue(false), "Operator credentials were rejected.");
        const user = userEvent.setup();
        renderPage();
        const password = screen.getByLabelText("Password");
        await user.type(screen.getByLabelText("Operator ID"), "kenny");
        await user.type(password, "wrong");
        await user.click(screen.getByRole("button", { name: "Sign in" }));
        expect(screen.getByRole("alert")).toHaveTextContent("Operator credentials were rejected.");
        expect(password).toHaveValue("");
    });
});
