import { act, fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { getAtlasDoctorReport } from "../api/atlas";
import type { DoctorReport } from "../types/doctor";
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

function diagnostic(patch: Partial<DoctorReport> = {}): DoctorReport {
    return { status: "healthy", score: 100, checked_at: new Date(Date.now()).toISOString(), configuration_ok: true,
        checks: [{ name: "Docker", passed: true, error: null }], critical: [], warnings: [], information: [], ...patch };
}
afterEach(() => { vi.useRealTimers(); vi.restoreAllMocks(); });

describe("AtlasDoctorPanel", () => {
    beforeEach(() => {
        mockedGetAtlasDoctorReport.mockReset();
    });

    it("runs Doctor and displays its structured report", async () => {
        const user = userEvent.setup();
        mockedGetAtlasDoctorReport.mockResolvedValue({
            status: "degraded",
            score: 95,
            checked_at: new Date(Date.now()).toISOString(),
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

    it("clears the previous health report while rerunning and after failure", async () => {
        const user = userEvent.setup();
        mockedGetAtlasDoctorReport.mockResolvedValueOnce({
            status: "healthy", score: 100, checked_at: new Date(Date.now()).toISOString(),
            configuration_ok: true, checks: [], critical: [], warnings: [], information: [],
        });
        render(<AtlasDoctorPanel />);
        await user.click(screen.getByRole("button", { name: "Run Doctor" }));
        await screen.findByText("100/100");
        let rejectRead!: (reason: Error) => void;
        mockedGetAtlasDoctorReport.mockReturnValueOnce(new Promise((_, reject) => { rejectRead = reject; }));
        await user.click(screen.getByRole("button", { name: "Run Doctor" }));
        expect(screen.getByRole("status")).toHaveTextContent("Checking the latest health");
        expect(screen.queryByText("100/100")).not.toBeInTheDocument();
        expect(screen.queryByText("healthy")).not.toBeInTheDocument();
        expect(screen.getByRole("button", { name: "Running Doctor..." })).toBeDisabled();
        await act(async () => { rejectRead(new Error("Doctor unavailable.")); });
        expect(await screen.findByRole("alert")).toHaveTextContent("Doctor unavailable.");
        expect(screen.queryByText("No findings were included in this report.")).not.toBeInTheDocument();
        expect(screen.getByRole("button", { name: "Run Doctor" })).toBeEnabled();
    });
    it("shows old reports as last-known evidence without making another read", async () => {
        mockedGetAtlasDoctorReport.mockResolvedValue(diagnostic({ checked_at: new Date(Date.now() - 120_000).toISOString() }));
        const user = userEvent.setup(); render(<AtlasDoctorPanel />);
        await user.click(screen.getByRole("button", { name: "Run Doctor" }));
        expect(await screen.findByText("Needs refresh")).toBeVisible();
        expect(screen.getByText("Last reported status: healthy. Current health is unknown.")).toBeVisible();
        expect(screen.queryByText("healthy", { exact: true })).not.toBeInTheDocument();
        expect(screen.getByText("100/100")).toBeVisible();
        expect(document.querySelector("time")).toHaveAttribute("dateTime");
        expect(mockedGetAtlasDoctorReport).toHaveBeenCalledTimes(1);
    });

    it("expires a fresh report locally even after the device clock moves backwards", async () => {
        vi.useFakeTimers(); vi.setSystemTime(new Date("2026-10-26T12:00:00Z"));
        mockedGetAtlasDoctorReport.mockResolvedValue(diagnostic());
        const view = render(<AtlasDoctorPanel />);
        await act(async () => { fireEvent.click(screen.getByRole("button", { name: "Run Doctor" })); });
        expect(screen.getByText("healthy", { exact: true })).toBeVisible();
        vi.setSystemTime(new Date("2026-10-26T11:00:00Z"));
        await act(async () => { vi.advanceTimersByTime(60_001); });
        expect(screen.getByText("Needs refresh")).toBeVisible();
        expect(screen.queryByText("healthy", { exact: true })).not.toBeInTheDocument();
        expect(mockedGetAtlasDoctorReport).toHaveBeenCalledTimes(1);
        view.unmount();
    });

    it("does not let the previous report's expiry age a refreshed report", async () => {
        vi.useFakeTimers(); vi.setSystemTime(new Date("2026-10-26T12:00:00Z"));
        mockedGetAtlasDoctorReport.mockResolvedValueOnce(diagnostic());
        const view = render(<AtlasDoctorPanel />);
        await act(async () => { fireEvent.click(screen.getByRole("button", { name: "Run Doctor" })); });
        await act(async () => { vi.advanceTimersByTime(30_000); });
        mockedGetAtlasDoctorReport.mockResolvedValueOnce(diagnostic({ status: "degraded", score: 95, warnings: ["Reported warning."] }));
        await act(async () => { fireEvent.click(screen.getByRole("button", { name: "Run Doctor" })); });
        await act(async () => { vi.advanceTimersByTime(30_001); });
        expect(screen.getByText("degraded", { exact: true })).toBeVisible();
        expect(screen.queryByText("Needs refresh")).not.toBeInTheDocument();
        await act(async () => { vi.advanceTimersByTime(30_000); });
        expect(screen.getByText("Needs refresh")).toBeVisible();
        expect(screen.getByText("Last reported status: degraded. Current health is unknown.")).toBeVisible();
        expect(mockedGetAtlasDoctorReport).toHaveBeenCalledTimes(2);
        view.unmount();
    });

    it("keeps future timestamps unverified until a new report is read", async () => {
        vi.useFakeTimers(); vi.setSystemTime(new Date("2026-10-26T12:00:00Z"));
        mockedGetAtlasDoctorReport.mockResolvedValueOnce(diagnostic({ checked_at: "2026-10-26T12:05:00Z" }));
        const view = render(<AtlasDoctorPanel />);
        await act(async () => { fireEvent.click(screen.getByRole("button", { name: "Run Doctor" })); });
        expect(screen.getByText("Report time unverified")).toBeVisible();
        await act(async () => { vi.advanceTimersByTime(600_000); });
        expect(screen.getByText("Report time unverified")).toBeVisible();
        expect(screen.queryByText("healthy", { exact: true })).not.toBeInTheDocument();
        expect(mockedGetAtlasDoctorReport).toHaveBeenCalledTimes(1);
        mockedGetAtlasDoctorReport.mockResolvedValueOnce(diagnostic());
        await act(async () => { fireEvent.click(screen.getByRole("button", { name: "Run Doctor" })); });
        expect(screen.getByText("healthy", { exact: true })).toBeVisible();
        expect(mockedGetAtlasDoctorReport).toHaveBeenCalledTimes(2);
        view.unmount();
    });

    it("keeps health findings visible while collection facts and notes stay collapsed", async () => {
        mockedGetAtlasDoctorReport.mockResolvedValue(diagnostic({ status: "critical", score: 80,
            checks: [{ name: "Docker", passed: false, error: "Check unavailable. Review configuration." }],
            critical: ["Reported connection concern."], information: ["Native report note."] }));
        const user = userEvent.setup(); render(<AtlasDoctorPanel />);
        expect(mockedGetAtlasDoctorReport).not.toHaveBeenCalled();
        await user.click(screen.getByRole("button", { name: "Run Doctor" }));
        expect(await screen.findByText("critical", { exact: true })).toBeVisible();
        expect(screen.getByText("Reported connection concern.")).toBeVisible();
        expect(screen.getByText("Results collected: 0 of 1 checks")).toBeVisible();
        expect(screen.getByText("Native report note.")).not.toBeVisible();
        await user.click(screen.getByText("Check details", { exact: true }));
        expect(screen.getByText("Check unavailable. Review configuration.")).toBeVisible();
        expect(screen.getByText("Native report note.")).toBeVisible();
        expect(mockedGetAtlasDoctorReport).toHaveBeenCalledTimes(1);
    });

    it("does not turn missing individual coverage into a claim that all services passed", async () => {
        mockedGetAtlasDoctorReport.mockResolvedValue(diagnostic({ checks: [] }));
        const user = userEvent.setup(); render(<AtlasDoctorPanel />);
        await user.click(screen.getByRole("button", { name: "Run Doctor" }));
        expect(await screen.findByText("No individual checks were reported.")).toBeVisible();
        expect(screen.getByText("No findings were included in this report.")).toBeVisible();
        expect(screen.queryByText("No critical issues or warnings detected.")).not.toBeInTheDocument();
    });

});
