import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { IntelligenceTelemetrySnapshot } from "../../types/ace";
import { IntelligenceTrendSection } from "./IntelligenceTrendSection";

const snapshots: IntelligenceTelemetrySnapshot[] = [
    {
        id: "newest",
        collected_at: "2026-07-25T19:01:00Z",
        telemetry: {
            provider_collection_duration_ms: 200,
            provider_timeout_seconds: 10,
            providers: [
                {
                    provider_id: "qdrant",
                    provider_name: "Qdrant",
                    status: "timed_out",
                    duration_ms: 10000,
                    finding_count: 1,
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
            providers: [],
        },
    },
];

describe("IntelligenceTrendSection", () => {
    it("summarizes duration history and highlights issues", () => {
        render(
            <IntelligenceTrendSection snapshots={snapshots} />,
        );

        expect(screen.getByText("2")).toBeInTheDocument();
        expect(screen.getByText("150 ms")).toBeInTheDocument();
        expect(screen.getByText("1")).toBeInTheDocument();
        expect(
            screen.getByRole("img", {
                name: "Provider intelligence collection duration trend",
            }),
        ).toBeInTheDocument();
        expect(
            screen.getByLabelText("200 ms, provider issue"),
        ).toBeInTheDocument();
    });

    it("does not render without history", () => {
        const { container } = render(
            <IntelligenceTrendSection snapshots={[]} />,
        );

        expect(container).toBeEmptyDOMElement();
    });
});
