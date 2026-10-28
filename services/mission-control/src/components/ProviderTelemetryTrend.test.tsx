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
            screen.getByText("Checks over limit"),
        ).toBeInTheDocument();
        expect(
            screen.getByLabelText("Time limit 150 ms"),
        ).toHaveStyle({ bottom: "75%" });
        expect(
            screen.getByRole("img", {
                name: "Qdrant check time trend. Each bar is one check; taller bars took longer, green bars finished, and amber bars timed out or failed.",
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
                "Atlas has no check history for this provider yet.",
            ),
        ).toBeInTheDocument();
    });

    it("describes check problems when no time limit is configured", () => {
        render(
            <ProviderTelemetryTrend
                providerId="qdrant"
                snapshots={snapshots}
            />,
        );

        expect(screen.getByText("Checks with issues")).toBeInTheDocument();
        expect(screen.queryByText("Checks over limit")).not.toBeInTheDocument();
        expect(screen.queryByText("limit")).not.toBeInTheDocument();
    });
});
