import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import { useOperatorSession } from "../hooks/operatorSessionContext";
import { OperatorLoginPage } from "./OperatorLoginPage";

vi.mock("../hooks/operatorSessionContext", () => ({ useOperatorSession: vi.fn() }));

function session(login: (id: string, password: string) => Promise<boolean>, error: string | null = null) {
    vi.mocked(useOperatorSession).mockReturnValue({
        authenticated: false,
        principal: null,
        csrfToken: null,
        loading: false,
        error,
        login,
        logout: vi.fn(),
        invalidate: vi.fn(),
    });
}

function renderPage() {
    render(<MemoryRouter initialEntries={[{ pathname: "/operator/login", state: { returnTo: "/operations/request" } }]}><Routes><Route path="/operator/login" element={<OperatorLoginPage />} /><Route path="/operations/request" element={<p>Maintenance destination</p>} /></Routes></MemoryRouter>);
}

describe("OperatorLoginPage", () => {
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
