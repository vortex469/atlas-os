import { fireEvent, render, screen, within } from "@testing-library/react";
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

    it("provides local-time details for each plotted check", () => {
        const { container } = render(
            <ProviderTelemetryTrend providerId="qdrant" snapshots={snapshots} />,
        );
        const disclosure = screen.getByText("Check details");
        expect(disclosure.tagName).toBe("SUMMARY");
        const details = disclosure.closest("details");
        expect(details).not.toHaveAttribute("open");
        fireEvent.click(disclosure);
        const list = within(details as HTMLDetailsElement).getByRole("list", {
            name: "Provider check details",
        });
        expect(within(list).getAllByRole("listitem")).toHaveLength(2);
        expect(
            Array.from(list.querySelectorAll("time")).map((time) =>
                time.getAttribute("dateTime"),
            ),
        ).toEqual(["2026-07-25T19:00:00Z", "2026-07-25T19:01:00Z"]);
        expect(list).toHaveTextContent("local time");
        expect(container.querySelector('[role="img"]')).toBeInTheDocument();
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

    it("distinguishes unavailable history from an empty history", () => {
        render(
            <ProviderTelemetryTrend
                providerId="ollama"
                snapshots={snapshots}
                unavailable
            />,
        );
        expect(screen.getByText("Provider check history could not be loaded.")).toBeInTheDocument();
        expect(screen.queryByText("Atlas has no check history for this provider yet.")).not.toBeInTheDocument();
    });

    it("labels displayed checks as last-known after a failed refresh", () => {
        render(
            <ProviderTelemetryTrend
                providerId="qdrant"
                snapshots={snapshots}
                unavailable
            />,
        );
        expect(screen.getByRole("status")).toHaveTextContent("Showing the last available check history; current history may have changed.");
        expect(screen.getByText("Checks")).toBeInTheDocument();
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
