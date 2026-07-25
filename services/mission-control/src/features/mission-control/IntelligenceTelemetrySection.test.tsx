import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { IntelligenceTelemetry } from "../../types/ace";
import { IntelligenceTelemetrySection } from "./IntelligenceTelemetrySection";

const telemetry: IntelligenceTelemetry = {
    provider_collection_duration_ms: 1200,
    provider_timeout_seconds: 10,
    providers: [
        {
            provider_id: "frigate",
            provider_name: "Frigate",
            status: "completed",
            duration_ms: 42.4,
            finding_count: 1,
        },
        {
            provider_id: "qdrant",
            provider_name: "Qdrant",
            status: "timed_out",
            duration_ms: 10000,
            finding_count: 1,
        },
        {
            provider_id: "n8n",
            provider_name: "n8n",
            status: "failed",
            duration_ms: 0.4,
            finding_count: 1,
        },
    ],
};

describe("IntelligenceTelemetrySection", () => {
    it("shows collection budget and sorts unhealthy outcomes first", () => {
        render(
            <IntelligenceTelemetrySection telemetry={telemetry} />,
        );

        expect(screen.getByText("1.20 s")).toBeInTheDocument();
        expect(screen.getAllByText("10.00 s")).toHaveLength(2);
        expect(
            screen.getByText("Within budget"),
        ).toBeInTheDocument();

        const rows = screen.getAllByRole("row").slice(1);
        expect(within(rows[0]).getAllByText("n8n")).toHaveLength(2);
        expect(
            within(rows[0]).getByText("Failed"),
        ).toBeInTheDocument();
        expect(
            within(rows[0]).getByText("<1 ms"),
        ).toBeInTheDocument();
        expect(
            within(rows[1]).getByText("Qdrant"),
        ).toBeInTheDocument();
        expect(
            within(rows[1]).getByText("Timed out"),
        ).toBeInTheDocument();
        expect(
            within(rows[2]).getByText("Frigate"),
        ).toBeInTheDocument();
    });

    it("reports when total collection exceeds the provider budget", () => {
        render(
            <IntelligenceTelemetrySection
                telemetry={{
                    ...telemetry,
                    provider_collection_duration_ms: 11000,
                }}
            />,
        );

        expect(
            screen.getByText("Budget exceeded"),
        ).toBeInTheDocument();
    });

    it("does not render an empty telemetry panel", () => {
        const { container } = render(
            <IntelligenceTelemetrySection
                telemetry={{
                    provider_collection_duration_ms: 0,
                    provider_timeout_seconds: 10,
                    providers: [],
                }}
            />,
        );

        expect(container).toBeEmptyDOMElement();
    });
});
