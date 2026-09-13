import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import {
    HealthStatusBadge,
    HealthStatusCard,
} from "./HealthStatusPrimitive";

describe("mapServiceStatusToHealthState", () => {
    it("maps healthy states correctly", () => {
        expect(mapServiceStatusToHealthState("healthy")).toBe("healthy");
        expect(mapServiceStatusToHealthState("online")).toBe("healthy");
        expect(mapServiceStatusToHealthState("success")).toBe("healthy");
        expect(mapServiceStatusToHealthState("HEALTHY")).toBe("healthy");
    });

    it("maps degraded states correctly", () => {
        expect(mapServiceStatusToHealthState("degraded")).toBe("degraded");
        expect(mapServiceStatusToHealthState("warning")).toBe("degraded");
        expect(mapServiceStatusToHealthState("critical")).toBe("degraded");
        expect(mapServiceStatusToHealthState("error")).toBe("degraded");
    });

    it("maps unavailable states correctly", () => {
        expect(mapServiceStatusToHealthState("unavailable")).toBe(
            "unavailable",
        );
        expect(mapServiceStatusToHealthState("offline")).toBe("unavailable");
    });

    it("maps blocked state correctly", () => {
        expect(mapServiceStatusToHealthState("blocked")).toBe("blocked");
    });

    it("maps unknown/null/missing to unknown", () => {
        expect(mapServiceStatusToHealthState(null)).toBe("unknown");
        expect(mapServiceStatusToHealthState(undefined)).toBe("unknown");
        expect(mapServiceStatusToHealthState("")).toBe("unknown");
        expect(mapServiceStatusToHealthState("invalid_status")).toBe("unknown");
    });
});

describe("isEvidenceStale", () => {
    it("returns true for null timestamp", () => {
        expect(isEvidenceStale(null)).toBe(true);
        expect(isEvidenceStale(undefined)).toBe(true);
    });

    it("returns false for recent timestamp", () => {
        const now = new Date();
        expect(isEvidenceStale(now)).toBe(false);

        const recent = new Date(Date.now() - 1000); // 1 second ago
        expect(isEvidenceStale(recent)).toBe(false);
    });

    it("returns true for old timestamp (default 5min threshold)", () => {
        const old = new Date(Date.now() - 6 * 60 * 1000); // 6 minutes ago
        expect(isEvidenceStale(old)).toBe(true);
    });

    it("respects custom stale threshold", () => {
        const timestamp = new Date(Date.now() - 30 * 1000); // 30 seconds ago
        expect(isEvidenceStale(timestamp, 60 * 1000)).toBe(false); // 1 min threshold
        expect(isEvidenceStale(timestamp, 10 * 1000)).toBe(true); // 10 sec threshold
    });
});

describe("HealthStatusBadge", () => {
    it("renders healthy status", () => {
        render(
            <HealthStatusBadge
                state="healthy"
                title="API"
            />,
        );
        expect(screen.getByText("API")).toBeInTheDocument();
        expect(screen.getByText("API").className).toContain("mc-status-success");
    });

    it("renders degraded status", () => {
        render(
            <HealthStatusBadge
                state="degraded"
                reason="High latency detected"
            />,
        );
        expect(screen.getByText("High latency detected")).toBeInTheDocument();
    });

    it("renders unavailable status", () => {
        render(
            <HealthStatusBadge
                state="unavailable"
            />,
        );
        expect(screen.getByText("Unavailable")).toBeInTheDocument();
    });

    it("renders unknown status", () => {
        render(
            <HealthStatusBadge
                state="unknown"
            />,
        );
        expect(screen.getByText("Unknown")).toBeInTheDocument();
    });

    it("renders last updated timestamp", () => {
        const now = new Date();
        const { container } = render(
            <HealthStatusBadge
                state="healthy"
                lastUpdated={now}
            />,
        );
        // The timestamp should be rendered in the badge
        const timeText = container.textContent;
        expect(
            timeText?.includes("ago") ||
                timeText?.includes("just now"),
        ).toBe(true);
    });

    it("indicates stale evidence", () => {
        const old = new Date(Date.now() - 10 * 60 * 1000);
        render(
            <HealthStatusBadge
                state="healthy"
                lastUpdated={old}
                isStale={true}
            />,
        );
        expect(screen.getByText(/ago \(stale\)/)).toBeInTheDocument();
    });
});

describe("HealthStatusCard", () => {
    it("renders compact variant as badge", () => {
        render(
            <HealthStatusCard
                state="healthy"
                title="Database"
                compact={true}
            />,
        );
        expect(screen.getByText("Database")).toBeInTheDocument();
    });

    it("renders full card variant", () => {
        render(
            <HealthStatusCard
                state="degraded"
                title="Worker Queue"
                reason="2 workers offline"
            />,
        );
        expect(screen.getByText("Worker Queue")).toBeInTheDocument();
        // reason appears twice: once in reason badge and once in description
        const reasons = screen.getAllByText("2 workers offline");
        expect(reasons.length).toBeGreaterThanOrEqual(1);
    });

    it("displays stale warning when evidence is old", () => {
        const old = new Date(Date.now() - 10 * 60 * 1000);
        render(
            <HealthStatusCard
                state="unknown"
                title="Resource"
                isStale={true}
                lastUpdated={old}
            />,
        );
        expect(
            screen.getByText(/This evidence is stale/),
        ).toBeInTheDocument();
    });

    it("renders custom details", () => {
        render(
            <HealthStatusCard
                state="healthy"
                title="Service"
                details={
                    <div data-testid="custom-details">
                        Custom detail content
                    </div>
                }
            />,
        );
        expect(
            screen.getByTestId("custom-details"),
        ).toBeInTheDocument();
        expect(
            screen.getByText("Custom detail content"),
        ).toBeInTheDocument();
    });

    it("renders blocked state", () => {
        render(
            <HealthStatusCard
                state="blocked"
                title="Execution"
                reason="Awaiting approval"
            />,
        );
        expect(screen.getByText("Blocked")).toBeInTheDocument();
        const reasons = screen.getAllByText("Awaiting approval");
        expect(reasons.length).toBeGreaterThanOrEqual(1);
    });
});

import { isEvidenceStale, mapServiceStatusToHealthState } from "./healthPresentation";

describe('stale status authority', () => {
    it.each(['healthy', 'degraded', 'unavailable', 'blocked', 'unknown'] as const)('does not present stale %s as current', state => {
        const { container } = render(<HealthStatusBadge state={state} isStale />);
        expect(screen.getByText('Unknown · Stale evidence')).toBeInTheDocument();
        expect(container.querySelector('[data-mc-status="success"]')).toBeNull();
    });
});

it('preserves authoritative update timing on full health cards', () => {
    render(<HealthStatusCard state="healthy" lastUpdated={new Date(Date.now() - 120_000)} />);
    expect(screen.getByText('2m ago')).toBeInTheDocument();
});
