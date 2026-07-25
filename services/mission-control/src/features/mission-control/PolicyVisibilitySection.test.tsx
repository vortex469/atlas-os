import { render, screen, within } from "@testing-library/react";
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
};

describe("PolicyVisibilitySection", () => {
    it("shows live provider expectations and severities", () => {
        render(<PolicyVisibilitySection policies={policies} />);

        const rows = screen.getAllByRole("row").slice(1);
        expect(rows).toHaveLength(11);
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
    });
});
