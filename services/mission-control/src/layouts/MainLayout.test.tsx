import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { atlas } from "../api/atlas";
import { MainLayout } from "./MainLayout";

vi.mock("../api/atlas", () => ({
    atlas: {
        get: vi.fn(),
    },
}));

describe("MainLayout", () => {
    beforeEach(() => {
        vi.mocked(atlas.get).mockResolvedValue({
            data: {
                release: "Foundry",
            },
        });
    });

    it("displays the release reported by Atlas Core", async () => {
        render(
            <MemoryRouter>
                <Routes>
                    <Route element={<MainLayout />}>
                        <Route index element={<p>Dashboard</p>} />
                    </Route>
                </Routes>
            </MemoryRouter>,
        );

        expect(await screen.findByText("Foundry")).toBeInTheDocument();
        expect(atlas.get).toHaveBeenCalledWith("");
    });
});
