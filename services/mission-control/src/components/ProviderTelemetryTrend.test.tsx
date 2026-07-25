import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { IntelligenceTelemetrySnapshot } from "../types/ace";
import { ProviderTelemetryTrend } from "./ProviderTelemetryTrend";

const snapshots: IntelligenceTelemetrySnapshot[] = [
    {
        id: "newest",
        collected_at: "2026-07-25T19:01:00Z",
        telemetry: {
            provider_collection_duration_ms: 500,
            provider_timeout_seconds: 10,
            providers: [
                {
                    provider_id: "qdrant",
                    provider_name: "Qdrant",
                    status: "timed_out",
                    duration_ms: 200,
                    finding_count: 1,
                },
                {
                    provider_id: "n8n",
                    provider_name: "n8n",
                    status: "completed",
                    duration_ms: 20,
                    finding_count: 0,
                },
            ],
        },
    },
    {
        id: "oldest",
        collected_at: "2026-07-25T19:00:00Z",
        telemetry: {
            provider_collection_duration_ms: 100,
            provider_timeout_seconds: 10,
            providers: [
                {
                    provider_id: "qdrant",
                    provider_name: "Qdrant",
                    status: "completed",
                    duration_ms: 100,
                    finding_count: 0,
                },
            ],
        },
    },
];

describe("ProviderTelemetryTrend", () => {
    it("shows only the selected provider history", () => {
        render(
            <ProviderTelemetryTrend
                providerId="qdrant"
                snapshots={snapshots}
                performancePolicy={{
                    maximum_collection_duration_ms: 150,
                    severity: "critical",
                }}
            />,
        );

        expect(screen.getByText("150 ms")).toBeInTheDocument();
        expect(screen.getByText("Timed out")).toBeInTheDocument();
        expect(
            screen.getByText("Over threshold"),
        ).toBeInTheDocument();
        expect(
            screen.getByLabelText("Policy threshold 150 ms"),
        ).toHaveStyle({ bottom: "75%" });
        expect(
            screen.getByRole("img", {
                name: "Qdrant intelligence duration trend",
            }),
        ).toBeInTheDocument();
        expect(
            screen.getByLabelText("100 ms, Completed"),
        ).toBeInTheDocument();
        expect(
            screen.getByLabelText("200 ms, Timed out"),
        ).toBeInTheDocument();
        expect(screen.queryByText("20 ms")).not.toBeInTheDocument();
    });

    it("shows an empty state without provider history", () => {
        render(
            <ProviderTelemetryTrend
                providerId="ollama"
                snapshots={snapshots}
            />,
        );
        expect(
            screen.getByText(
                "No intelligence collection history is available for this provider yet.",
            ),
        ).toBeInTheDocument();
    });
});
