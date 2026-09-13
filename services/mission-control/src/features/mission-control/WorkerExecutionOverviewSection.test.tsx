import { render, screen } from "@testing-library/react";
import { BrowserRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";

import { WorkerExecutionOverviewSection } from "./WorkerExecutionOverviewSection";

const renderWithRouter = (component: React.ReactNode) => {
    return render(
        <BrowserRouter>{component}</BrowserRouter>
    );
};

describe("WorkerExecutionOverviewSection", () => {
    it("renders worker and execution section", () => {
        renderWithRouter(<WorkerExecutionOverviewSection />);
        expect(screen.getByText("Worker & Execution")).toBeInTheDocument();
    });

    it("displays execution metrics", () => {
        renderWithRouter(
            <WorkerExecutionOverviewSection
                eligibleCount={5}
                notEligibleCount={2}
                runningCount={1}
                blockedCount={0}
                queuedCount={3}
            />,
        );
        expect(screen.getByText("Eligible")).toBeInTheDocument();
        expect(screen.getByText("Not Eligible")).toBeInTheDocument();
        expect(screen.getByText("Active")).toBeInTheDocument();
    });

    it("shows healthy status when execution is running", () => {
        renderWithRouter(
            <WorkerExecutionOverviewSection
                eligibleCount={5}
                notEligibleCount={0}
                runningCount={2}
                blockedCount={0}
                queuedCount={0}
            />,
        );
        expect(screen.getByText("Execution Status")).toBeInTheDocument();
        expect(screen.getByText(/2 active/)).toBeInTheDocument();
    });

    it("shows blocked status when work is blocked", () => {
        renderWithRouter(
            <WorkerExecutionOverviewSection
                eligibleCount={5}
                notEligibleCount={0}
                runningCount={0}
                blockedCount={2}
                queuedCount={0}
            />,
        );
        expect(screen.getByText("Execution Status")).toBeInTheDocument();
        expect(screen.getByText(/2 work item.*blocked/)).toBeInTheDocument();
    });

    it("shows degraded status when work is queued but not running", () => {
        renderWithRouter(
            <WorkerExecutionOverviewSection
                eligibleCount={5}
                notEligibleCount={0}
                runningCount={0}
                blockedCount={0}
                queuedCount={3}
            />,
        );
        expect(screen.getByText("Execution Status")).toBeInTheDocument();
        expect(screen.getByText(/3 item.*queued/)).toBeInTheDocument();
    });

    it("shows warning alert for blocked executions", () => {
        renderWithRouter(
            <WorkerExecutionOverviewSection
                eligibleCount={5}
                notEligibleCount={0}
                runningCount={0}
                blockedCount={1}
                queuedCount={0}
            />,
        );
        expect(
            screen.getByText(/1 execution.*blocked from proceeding/),
        ).toBeInTheDocument();
    });

    it("handles empty/zero counts", () => {
        renderWithRouter(
            <WorkerExecutionOverviewSection
                eligibleCount={0}
                notEligibleCount={0}
                runningCount={0}
                blockedCount={0}
                queuedCount={0}
            />,
        );
        const zeroElements = screen.queryAllByText("0");
        expect(zeroElements.length).toBeGreaterThan(0);
    });
});
