import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import type { IntelligenceTelemetrySnapshot } from "../../types/ace";
import { IntelligenceTrendSection } from "./IntelligenceTrendSection";

const { exportHistory, pruneHistory } = vi.hoisted(() => ({
    exportHistory: vi.fn(
        async () => new Blob(["history"]),
    ),
    pruneHistory: vi.fn(async () => ({
        deleted_entries: 2,
        remaining_entries: 3,
        retention_days: 30,
    })),
}));

vi.mock("../../api/atlas", () => ({
    exportIntelligenceTelemetryHistory: exportHistory,
    pruneIntelligenceTelemetryHistory: pruneHistory,
}));

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

    it("filters snapshots by provider and outcome", async () => {
        const user = userEvent.setup();
        render(
            <IntelligenceTrendSection snapshots={snapshots} />,
        );

        await user.selectOptions(
            screen.getByLabelText("Provider"),
            "qdrant",
        );
        await user.selectOptions(
            screen.getByLabelText("Outcome"),
            "completed",
        );

        expect(
            screen.getByText(
                "No telemetry snapshots match the selected filters.",
            ),
        ).toBeInTheDocument();

        await user.selectOptions(
            screen.getByLabelText("Outcome"),
            "timed_out",
        );
        expect(
            screen.getByLabelText("200 ms, provider issue"),
        ).toBeInTheDocument();
    });

    it("exports history with the active filters", async () => {
        const user = userEvent.setup();
        const createObjectURL = vi.fn(() => "blob:history");
        const revokeObjectURL = vi.fn();
        Object.defineProperty(URL, "createObjectURL", {
            value: createObjectURL,
            configurable: true,
        });
        Object.defineProperty(URL, "revokeObjectURL", {
            value: revokeObjectURL,
            configurable: true,
        });
        vi.spyOn(
            HTMLAnchorElement.prototype,
            "click",
        ).mockImplementation(() => undefined);
        render(
            <IntelligenceTrendSection snapshots={snapshots} />,
        );

        await user.selectOptions(
            screen.getByLabelText("Provider"),
            "qdrant",
        );
        await user.selectOptions(
            screen.getByLabelText("Outcome"),
            "timed_out",
        );
        await user.click(
            screen.getByRole("button", {
                name: "Export CSV",
            }),
        );

        expect(exportHistory).toHaveBeenCalledWith("csv", {
            providerId: "qdrant",
            status: "timed_out",
        });
        expect(createObjectURL).toHaveBeenCalled();
        expect(revokeObjectURL).toHaveBeenCalledWith(
            "blob:history",
        );
    });

    it("shows retention and confirms manual pruning", async () => {
        const user = userEvent.setup();
        vi.spyOn(window, "confirm").mockReturnValue(true);
        const onPruned = vi.fn(async () => undefined);
        render(
            <IntelligenceTrendSection
                snapshots={snapshots}
                retention={{
                    entry_count: 5,
                    max_entries: 100,
                    retention_days: 30,
                    oldest_snapshot_at:
                        "2026-07-24T19:00:00Z",
                    newest_snapshot_at:
                        "2026-07-25T19:00:00Z",
                }}
                onPruned={onPruned}
            />,
        );

        expect(
            screen.getByText("5 snapshot(s)"),
        ).toBeInTheDocument();
        expect(screen.getByText("5.0% capacity")).toBeInTheDocument();
        expect(
            screen.getByRole("progressbar", {
                name: "Telemetry history storage capacity",
            }),
        ).toHaveAttribute("aria-valuenow", "5");
        expect(
            screen.getByText(
                new Date(
                    "2026-07-24T19:00:00Z",
                ).toLocaleString(),
            ),
        ).toBeInTheDocument();
        await user.click(
            screen.getByRole("button", {
                name: "Prune now",
            }),
        );

        expect(window.confirm).toHaveBeenCalled();
        expect(pruneHistory).toHaveBeenCalled();
        expect(onPruned).toHaveBeenCalled();
        expect(
            screen.getByText(
                "Pruned 2 snapshot(s); 3 remain.",
            ),
        ).toBeInTheDocument();
    });
});
