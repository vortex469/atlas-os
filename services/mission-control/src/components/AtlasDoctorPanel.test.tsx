import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { getAtlasDoctorReport } from "../api/atlas";
import { AtlasDoctorPanel } from "./AtlasDoctorPanel";

vi.mock("../api/atlas", () => ({
    getAtlasDoctorReport: vi.fn(),
    getAtlasErrorMessage: (
        error: unknown,
        fallback: string,
    ) => (error instanceof Error ? error.message : fallback),
}));

const mockedGetAtlasDoctorReport = vi.mocked(
    getAtlasDoctorReport,
);

describe("AtlasDoctorPanel", () => {
    beforeEach(() => {
        vi.clearAllMocks();
    });

    it("runs Doctor and displays its structured report", async () => {
        const user = userEvent.setup();
        mockedGetAtlasDoctorReport.mockResolvedValue({
            status: "degraded",
            score: 95,
            checked_at: "2026-07-25T18:00:00Z",
            configuration_ok: true,
            checks: [
                {
                    name: "Docker",
                    passed: true,
                    error: null,
                },
                {
                    name: "Optional service",
                    passed: false,
                    error: "Offline",
                },
            ],
            critical: [],
            warnings: ["Optional service offline."],
            information: [],
        });
        render(<AtlasDoctorPanel />);

        await user.click(
            screen.getByRole("button", { name: "Run Doctor" }),
        );

        expect(
            await screen.findByText("95/100"),
        ).toBeInTheDocument();
        expect(screen.getByText("degraded")).toBeInTheDocument();
        expect(
            screen.getByText("Optional service offline."),
        ).toBeInTheDocument();
        expect(
            mockedGetAtlasDoctorReport,
        ).toHaveBeenCalledOnce();
    });

    it("shows a diagnostic request failure", async () => {
        const user = userEvent.setup();
        mockedGetAtlasDoctorReport.mockRejectedValue(
            new Error("Doctor unavailable."),
        );
        render(<AtlasDoctorPanel />);

        await user.click(
            screen.getByRole("button", { name: "Run Doctor" }),
        );

        expect(await screen.findByRole("alert")).toHaveTextContent(
            "Doctor unavailable.",
        );
    });
});
