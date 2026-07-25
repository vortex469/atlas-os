import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import type { IntelligenceTelemetrySnapshot } from "../../types/ace";
import { IntelligenceTrendSection } from "./IntelligenceTrendSection";

const { exportHistory } = vi.hoisted(() => ({
    exportHistory: vi.fn(
        async () => new Blob(["history"]),
    ),
}));

vi.mock("../../api/atlas", () => ({
    exportIntelligenceTelemetryHistory: exportHistory,
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
});
