import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { ServiceHealth } from "../types/health";
import { HealthCard } from "./HealthCard";
import { SectionHeader } from "./SectionHeader";
import { ServiceHealthCard } from "./ServiceHealthCard";
import { StatusBadge } from "./StatusBadge";

describe("Mission Control visual foundation", () => {
    it.each([
        ["healthy", "success"],
        ["degraded", "warning"],
        ["failed", "error"],
        ["running", "info"],
        ["unavailable", "disabled"],
        ["unexpected", "neutral"],
    ])("maps %s to the semantic %s status treatment", (status, variant) => {
        render(<StatusBadge status={status} />);

        expect(screen.getByText(status)).toHaveAttribute(
            "data-mc-status",
            variant,
        );
    });

    it("uses shared heading and panel primitives", () => {
        const health: ServiceHealth = {
            provider_id: "atlas-core",
            status: "healthy",
            latency_ms: 12,
            http_status: 200,
            message: "Policy cache is warm.",
            details: {},
        };

        render(
            <>
                <SectionHeader
                    title="Runtime Health"
                    description="Current operator-facing service state."
                />
                <HealthCard
                    score={98}
                    status="healthy"
                    summary="All presentation checks are healthy."
                />
                <ServiceHealthCard
                    name="Atlas Core"
                    health={health}
                    onSelect={() => undefined}
                />
            </>,
        );

        expect(screen.getByText("Runtime Health")).toHaveClass(
            "mc-section-heading",
        );
        expect(screen.getByText("98").closest("section")).toHaveClass(
            "mc-surface",
        );
        expect(
            screen.getByRole("button", {
                name: "View details for Atlas Core",
            }),
        ).toHaveClass("mc-panel-interactive", "mc-focusable");
        expect(screen.getByText("Policy cache is warm.")).toHaveClass(
            "mc-status-warning",
        );
    });
});
