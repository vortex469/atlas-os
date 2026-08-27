import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { getInstallationCapabilityAssessment } from "../../api/installationCapability";
import type { InstallationCapabilityAssessmentV1, InstallationCapabilityResult } from "../../types/installationCapability";
import { InstallationCapabilityAssessment } from "./InstallationCapabilityAssessment";

vi.mock("../../api/installationCapability", () => ({ getInstallationCapabilityAssessment: vi.fn() }));

function fixture(result: InstallationCapabilityResult = "satisfied"): InstallationCapabilityAssessmentV1 {
    return {
        schema_version: "installation-capability-assessment-v1",
        plan: { application: { item_id: "home-assistant" }, fingerprint: { value: "plan-fingerprint" } } as InstallationCapabilityAssessmentV1["plan"],
        selection: { selection_id: "selection-1", resource_id: "101", selected_destination_fingerprint: "selected-fingerprint" } as InstallationCapabilityAssessmentV1["selection"],
        current_destination: { destination_fingerprint: "current-fingerprint" } as InstallationCapabilityAssessmentV1["current_destination"],
        provider_facts: {
            schema_version: "provider-installation-capability-facts-v1", provider: "proxmox", resource_type: "qemu", placement_kind: "existing-guest",
            resource_id: "101", destination_fingerprint: "current-fingerprint", observed_at: "2026-08-27T12:00:00Z", fresh_until: "2026-08-27T12:05:00Z",
            facts: [
                { code: "current_destination_identity", state: "observed", value: true, source: "proxmox-qemu-control-plane", observed_at: "2026-08-27T12:00:00Z", destination_fingerprint: "current-fingerprint" },
                { code: "current_lifecycle_state", state: "observed", value: "running", source: "proxmox-qemu-control-plane", observed_at: "2026-08-27T12:00:00Z", destination_fingerprint: "current-fingerprint" },
                { code: "configured_cpu_cores", state: "observed", value: 4, source: "proxmox-qemu-control-plane", observed_at: "2026-08-27T12:00:00Z", destination_fingerprint: "current-fingerprint" },
                { code: "configured_memory_bytes", state: "observed", value: 8589934592, source: "proxmox-qemu-control-plane", observed_at: "2026-08-27T12:00:00Z", destination_fingerprint: "current-fingerprint" },
                { code: "configured_disk_capacity_bytes", state: "observed", value: 68719476736, source: "proxmox-qemu-control-plane", observed_at: "2026-08-27T12:00:00Z", destination_fingerprint: "current-fingerprint" },
                { code: "guest_agent_configured", state: "observed", value: false, source: "proxmox-qemu-control-plane", observed_at: "2026-08-27T12:00:00Z", destination_fingerprint: "current-fingerprint" },
            ],
        },
        comparisons: [{ prerequisite_id: "p1", prerequisite_kind: "storage", requirement_kind: result === "not_assessable" ? "unsupported" : "storage", requirement: "Requires at least 32 GB storage.", fact_code: result === "not_assessable" ? null : "configured_disk_capacity_bytes", fact_state: result === "not_assessable" ? null : result === "unknown" ? "unavailable" : "observed", observed_value: result === "not_assessable" || result === "unknown" ? null : result === "not_satisfied" ? 1073741824 : 68719476736, result }],
        assessment_status: result === "not_satisfied" ? "blocked" : result === "satisfied" ? "requirements_satisfied_but_non_authorizing" : "insufficient_provider_facts",
        reason_codes: ["installation_plan_blocked", "provider_facts_unknown", "requirement_not_satisfied", "agent_install_container_unsupported"],
        evaluated_at: "2026-08-27T12:00:00Z",
        candidate_eligibility_evaluated: false, candidate_creation_allowed: false, agent_execution_supported: false, provider_mutation_allowed: false,
        assessment_fingerprint: "assessment-fingerprint",
    };
}

describe("installation capability assessment", () => {
    beforeEach(() => vi.resetAllMocks());

    it.each(["satisfied", "not_satisfied", "unknown", "not_assessable"] as const)("renders the %s comparison state", async (result) => {
        vi.mocked(getInstallationCapabilityAssessment).mockResolvedValueOnce(fixture(result));
        render(<InstallationCapabilityAssessment itemId="home-assistant" selectionId="selection-1" />);
        expect(await screen.findByText(new RegExp(`^${result.replaceAll("_", " ")}`, "i"))).toBeInTheDocument();
        expect(screen.getByRole("heading", { name: /sanitized provider configuration facts/i })).toBeInTheDocument();
        expect(screen.getByText(/does not inspect actual in-guest or runtime capability/i)).toBeInTheDocument();
    });

    it("keeps the Home Assistant golden blocked and reasons in server order", async () => {
        vi.mocked(getInstallationCapabilityAssessment).mockResolvedValueOnce(fixture("not_satisfied"));
        render(<InstallationCapabilityAssessment itemId="home-assistant" selectionId="selection-1" />);
        expect(await screen.findByText(/status: blocked — non-authorizing/i)).toBeInTheDocument();
        const reasons = screen.getByRole("list", { name: /installation capability reasons/i });
        expect(reasons.textContent).toMatch(/plan is blocked.*configuration facts are unavailable.*below a stated requirement.*does not support installation execution/i);
    });

    it("renders empty, loading, error, and no-response states", async () => {
        const empty = render(<InstallationCapabilityAssessment itemId="home-assistant" selectionId={null} />);
        expect(screen.getByText(/no prospective destination selection/i)).toBeInTheDocument();
        empty.unmount();

        let rejectRequest: (reason: Error) => void = () => undefined;
        vi.mocked(getInstallationCapabilityAssessment).mockReturnValueOnce(new Promise((_, reject) => { rejectRequest = reject; }));
        render(<InstallationCapabilityAssessment itemId="home-assistant" selectionId="selection-1" />);
        expect(await screen.findByText(/loading installation capability/i)).toBeInTheDocument();
        rejectRequest(new Error("secret provider address 10.0.0.1"));
        await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent(/currently unavailable/i));
    });

    it("does not render raw provider data or prohibited controls and navigation", async () => {
        const value = fixture();
        (value as unknown as Record<string, unknown>).raw_provider_payload = { address: "10.0.0.1", credential: "secret" };
        vi.mocked(getInstallationCapabilityAssessment).mockResolvedValueOnce(value);
        const { container } = render(<InstallationCapabilityAssessment itemId="home-assistant" selectionId="selection-1" />);
        await screen.findByText(/assessment-fingerprint/i);
        expect(container).not.toHaveTextContent(/10\.0\.0\.1|secret/);
        expect(container.querySelectorAll("button, a, form")).toHaveLength(0);
        expect(container.textContent).not.toMatch(/create candidate|start workflow|dispatch|retry action|Atlas Agent/i);
    });
});
