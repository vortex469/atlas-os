import { act, render, screen, within } from "@testing-library/react";
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

    it("runs health checks and displays their report in plain language", async () => {
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

        expect(screen.getByRole("region", { name: "Additional health checks" })).toBeVisible();
        await user.click(
            screen.getByRole("button", { name: "Run health checks" }),
        );

        expect(
            await screen.findByText("Health score: 95/100"),
        ).toBeInTheDocument();
        expect(screen.getByText("Degraded")).toBeInTheDocument();
        expect(screen.getByText("1 of 2 checks passed")).toBeInTheDocument();
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
            new Error("Doctor unavailable: Bearer canary-secret-value"),
        );
        render(<AtlasDoctorPanel />);

        await user.click(
            screen.getByRole("button", { name: "Run health checks" }),
        );

        const alert = await screen.findByRole("alert");
        expect(alert).toHaveTextContent("Health checks could not finish");
        expect(alert).toHaveTextContent("No new health report is available. Run the checks again to get current results.");
        const technicalDetails = within(alert).getByText("Technical details").closest("details");
        expect(technicalDetails).not.toHaveAttribute("open");
        const safeError = within(technicalDetails as HTMLDetailsElement).getByText("[Sensitive text withheld]");
        expect(safeError).not.toBeVisible();
        expect(within(alert).queryByText(/canary-secret-value/)).not.toBeInTheDocument();
        await user.click(within(technicalDetails as HTMLDetailsElement).getByText("Technical details"));
        expect(safeError).toBeVisible();
    });

    it("clears the previous health report while rerunning and after failure", async () => {
        const user = userEvent.setup();
        mockedGetAtlasDoctorReport.mockResolvedValueOnce({
            status: "healthy", score: 100, checked_at: "2026-10-26T00:00:00Z",
            configuration_ok: true, checks: [], critical: [], warnings: [], information: [],
        });
        render(<AtlasDoctorPanel />);
        await user.click(screen.getByRole("button", { name: "Run health checks" }));
        await screen.findByText("Health score: 100/100");
        let rejectRead!: (reason: Error) => void;
        mockedGetAtlasDoctorReport.mockReturnValueOnce(new Promise((_, reject) => { rejectRead = reject; }));
        await user.click(screen.getByRole("button", { name: "Run health checks" }));
        expect(screen.getByRole("status")).toHaveTextContent("Checking current health");
        expect(screen.queryByText("Health score: 100/100")).not.toBeInTheDocument();
        expect(screen.queryByText("Healthy")).not.toBeInTheDocument();
        expect(screen.getByRole("button", { name: "Checking health…" })).toBeDisabled();
        await act(async () => { rejectRead(new Error("Doctor unavailable.")); });
        const alert = await screen.findByRole("alert");
        expect(alert).toHaveTextContent("Health checks could not finish");
        expect(alert).toHaveTextContent("No new health report is available.");
        expect(screen.queryByText("No critical issues or warnings detected.")).not.toBeInTheDocument();
        expect(screen.getByRole("button", { name: "Run health checks" })).toBeEnabled();
    });
});
