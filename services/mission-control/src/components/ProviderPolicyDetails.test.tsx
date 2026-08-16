import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { AtlasPolicies } from "../types/policies";
import { ProviderPolicyDetails } from "./ProviderPolicyDetails";

const policies: AtlasPolicies = {
    proxmox: {
        guests: {
            "101": { expected: "running" },
        },
    },
    docker: {
        containers: {
            atlas: { expected: "running" },
        },
    },
    homeassistant: {
        ignored_entities: ["sensor.intentional_offline"],
    },
    opnsense: {
        pending_update_warning_threshold: 3,
        reboot_required_severity: "critical",
    },
    frigate: {
        cameras: {
            front: {
                expected: "active",
                minimum_camera_fps: 5,
                minimum_process_fps: 4,
            },
        },
        stalled_camera_severity: "warning",
    },
    obsidian: {
        minimum_note_count: 10,
        stale_after_days: 30,
        insufficient_notes_severity: "critical",
        stale_severity: "warning",
        scan_truncated_severity: "info",
    },
    qdrant: {
        expected_collections: ["memory", "documents"],
        missing_collection_severity: "critical",
        empty_instance_severity: "warning",
    },
    n8n: {
        expected_active_workflows: ["Daily backup", "Sync"],
        inactive_workflow_severity: "critical",
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

describe("ProviderPolicyDetails", () => {
    it("presents Proxmox YAML guest values only as non-authoritative legacy evidence", () => {
        render(
            <ProviderPolicyDetails
                providerId="proxmox"
                policies={{
                    ...policies,
                    proxmox: { guests: { "110": { expected: "stopped" } } },
                }}
            />,
        );

        expect(screen.getByRole("heading", { name: "Legacy policy evidence" })).toBeInTheDocument();
        expect(screen.getByText("110: stopped")).toBeInTheDocument();
        expect(screen.getByText(/non-authoritative review context/i)).toBeInTheDocument();
        expect(screen.getByText(/do not automatically apply to current resource identities/i)).toBeInTheDocument();
        expect(screen.queryByText(/currently enforced/i)).not.toBeInTheDocument();
        expect(screen.queryByText(/current Atlas expectations/i)).not.toBeInTheDocument();
    });

    it("shows complete Frigate camera policy details", () => {
        render(
            <ProviderPolicyDetails
                providerId="frigate"
                policies={policies}
            />,
        );

        expect(
            screen.getByText(
                "front: active, capture ≥ 5 FPS, process ≥ 4 FPS",
            ),
        ).toBeInTheDocument();
        expect(screen.getByText("Warning")).toBeInTheDocument();
    });

    it("shows named Qdrant and n8n expectations", () => {
        const { rerender } = render(
            <ProviderPolicyDetails
                providerId="qdrant"
                policies={policies}
            />,
        );

        expect(
            screen.getByText("memory, documents"),
        ).toBeInTheDocument();
        expect(screen.getByText("250 ms")).toBeInTheDocument();

        rerender(
            <ProviderPolicyDetails
                providerId="n8n"
                policies={policies}
            />,
        );
        expect(
            screen.getByText("Daily backup, Sync"),
        ).toBeInTheDocument();
    });

    it("supports existing provider policies and empty policy states", () => {
        const { rerender } = render(
            <ProviderPolicyDetails
                providerId="home_assistant"
                policies={policies}
            />,
        );

        expect(
            screen.getByText("sensor.intentional_offline"),
        ).toBeInTheDocument();

        rerender(
            <ProviderPolicyDetails
                providerId="ollama"
                policies={policies}
            />,
        );
        expect(
            screen.getByText(
                "No provider-specific operational policy is configured.",
            ),
        ).toBeInTheDocument();
    });
});
