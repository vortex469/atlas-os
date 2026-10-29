import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { AtlasPolicies } from "../../types/policies";
import { PolicyVisibilitySection } from "./PolicyVisibilitySection";

const policies: AtlasPolicies = {
    proxmox: { guests: {} },
    docker: { containers: {} },
    homeassistant: { ignored_entities: [] },
    opnsense: {
        pending_update_warning_threshold: 3,
        reboot_required_severity: "critical",
    },
    frigate: {
        cameras: {
            front: {
                expected: "active",
                minimum_camera_fps: 5,
                minimum_process_fps: 5,
            },
        },
        stalled_camera_severity: "warning",
    },
    obsidian: {
        minimum_note_count: 10,
        stale_after_days: 30,
        insufficient_notes_severity: "warning",
        stale_severity: "info",
        scan_truncated_severity: "warning",
    },
    qdrant: {
        expected_collections: ["memory", "documents"],
        missing_collection_severity: "critical",
        empty_instance_severity: "info",
    },
    n8n: {
        expected_active_workflows: ["Backup"],
        inactive_workflow_severity: "warning",
        scan_truncated_severity: "warning",
        empty_instance_severity: "info",
    },
    intelligence: {
        providers: {
            qdrant: {
                maximum_collection_duration_ms: 250,
                severity: "critical",
            },
        },
    },
};

const health = {
    status: "healthy" as const,
    source_exists: true,
    checked_at: "2026-07-25T19:00:00Z",
    loaded_at: "2026-07-25T19:00:00Z",
    duration_ms: 1.25,
    error: null,
    diagnostics: [],
};

describe("PolicyVisibilitySection", () => {
    it.each([null, [], {}, { status: {}, duration_ms: "1", diagnostics: [null, { path: {}, message: [] }] }])("renders malformed policy evidence without claiming success: %j", (payload) => {
        render(<PolicyVisibilitySection policies={null} health={payload} />);
        expect(screen.getByText("Policy file check")).toBeInTheDocument();
        expect(screen.getByText("Status unknown")).toBeInTheDocument();
        expect(screen.getByText(/Validation duration unknown/)).toBeInTheDocument();
        expect(screen.getByText(/Policy source unknown/)).toBeInTheDocument();
        expect(screen.queryByText(/Safe defaults active/)).not.toBeInTheDocument();
    });

    it.each(["healthy", "degraded", "unavailable", "blocked", "unknown"])("uses the shared health state for policy status %s", (status) => {
        render(<PolicyVisibilitySection policies={null} health={{ ...health, checked_at: new Date().toISOString(), status, error: "Source-reported reason" }} />);
        expect(screen.getByText("Policy file check")).toBeInTheDocument();
        expect(screen.getByText(status === "unknown" ? "Status unknown" : status.charAt(0).toUpperCase() + status.slice(1))).toBeInTheDocument();
        expect(screen.getByText("Source-reported reason")).toBeInTheDocument();
    });

    it("shows live provider expectations and severities", () => {
        render(
            <PolicyVisibilitySection
                policies={policies}
                health={health}
            />,
        );

        const rows = screen.getAllByRole("row").slice(1);
        expect(rows).toHaveLength(12);
        expect(
            screen.getByText("Policy file check"),
        ).toBeInTheDocument();
        expect(
            screen.getByText("This page shows the rules Atlas uses to check connected providers and their resources."),
        ).toBeInTheDocument();
        expect(
            screen.getByText(/Validated in 1.25 ms/),
        ).toBeInTheDocument();
        expect(
            within(rows[0]).getByText(
                "Warn at 3 pending update(s)",
            ),
        ).toBeInTheDocument();
        expect(
            within(rows[2]).getByText(
                "1 camera expectation(s)",
            ),
        ).toBeInTheDocument();
        expect(
            within(rows[4]).getByText("30-day freshness"),
        ).toBeInTheDocument();
        expect(
            within(rows[6]).getByText(
                "2 expected collection(s)",
            ),
        ).toBeInTheDocument();
        expect(
            within(rows[6]).getByText("Critical"),
        ).toBeInTheDocument();
        expect(
            within(rows[8]).getByText(
                "1 expected active workflow(s)",
            ),
        ).toBeInTheDocument();
        expect(
            within(rows[11]).getByText("250 ms maximum"),
        ).toBeInTheDocument();
    });

    it("shows degraded policy status and keeps technical diagnostics collapsed", () => {
        render(
            <PolicyVisibilitySection
                policies={null}
                health={{
                    status: "degraded",
                    source_exists: true,
                    checked_at: "2026-07-25T19:00:00Z",
                    loaded_at: null,
                    duration_ms: 0.5,
                    error: (
                        "Policy reload failed with 1 diagnostic(s)."
                    ),
                    diagnostics: [
                        {
                            path: "n8n.scan_truncated_severity",
                            error_type: "literal_error",
                            message: (
                                "Input should be 'info', 'warning' " +
                                "or 'critical'"
                            ),
                            line: null,
                            column: null,
                        },
                    ],
                }}
            />,
        );

        expect(
            screen.getByText("Policy file check"),
        ).toBeInTheDocument();
        expect(
            screen.getByText("The policy file has 1 issue to fix. Open Technical details to review it."),
        ).toBeInTheDocument();
        expect(screen.queryByText("Policy reload failed with 1 diagnostic(s).")).not.toBeInTheDocument();
        expect(screen.getByText("Technical details (1)")).toBeInTheDocument();
        expect(screen.getByText("n8n.scan_truncated_severity")).not.toBeVisible();
        expect(
            screen.getByText("Policy settings are unavailable. After correcting the policy file, refresh Mission Control to check it again."),
        ).toBeInTheDocument();
        expect(screen.queryByRole("table")).not.toBeInTheDocument();

        fireEvent.click(screen.getByText("Technical details (1)"));

        expect(screen.getByText("n8n.scan_truncated_severity")).toBeVisible();
        expect(screen.getByText("Input should be 'info', 'warning' or 'critical'")).toBeVisible();
    });

    it("labels unavailable technical diagnostic fields in plain language", () => {
        render(<PolicyVisibilitySection policies={null} health={{
            ...health,
            status: "degraded",
            diagnostics: [{ path: {}, error_type: [], message: [] }],
        }} />);

        fireEvent.click(screen.getByText("Technical details (1)"));

        expect(screen.getByText("Path unavailable")).toBeVisible();
        expect(screen.getByText("Issue type unavailable")).toBeVisible();
        expect(screen.getByText("No diagnostic message provided.")).toBeVisible();
    });

    it("explains when last loaded policy settings remain available", () => {
        render(
            <PolicyVisibilitySection
                policies={policies}
                health={{ ...health, status: "degraded", error: "Source-reported reason" }}
            />,
        );

        expect(screen.getByText("The last loaded policy settings remain visible. After correcting the policy file, refresh Mission Control to check it again.")).toBeInTheDocument();
        expect(screen.getByRole("table")).toBeInTheDocument();
    });
});
